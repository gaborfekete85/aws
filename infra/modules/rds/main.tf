resource "aws_db_subnet_group" "this" {
  name       = "${var.name}-catalog"
  subnet_ids = var.subnet_ids
}

resource "aws_security_group" "db" {
  name        = "${var.name}-catalog-db"
  description = "PostgreSQL from in-VPC Lambdas only"
  vpc_id      = var.vpc_id
}

resource "aws_vpc_security_group_ingress_rule" "postgres" {
  for_each                     = toset(var.client_security_group_ids)
  security_group_id            = aws_security_group.db.id
  referenced_security_group_id = each.value
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
  description                  = "PostgreSQL from Lambda"
}

resource "aws_db_parameter_group" "this" {
  name   = "${var.name}-catalog-pg${var.engine_version}"
  family = "postgres${var.engine_version}"

  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }

  parameter {
    name  = "log_min_duration_statement"
    value = "500" # log queries slower than 500 ms
  }
}

# Created up front so the exported PostgreSQL logs get a retention (RDS would create it without one).
resource "aws_cloudwatch_log_group" "postgresql" {
  name              = "/aws/rds/instance/${var.name}-catalog/postgresql"
  retention_in_days = var.log_retention_days
}

resource "aws_db_instance" "this" {
  identifier     = "${var.name}-catalog"
  engine         = "postgres"
  engine_version = var.engine_version
  instance_class = var.instance_class

  db_name  = var.db_name
  username = "catalog_admin"
  # RDS creates and rotates the password in Secrets Manager; it never enters Terraform state.
  manage_master_user_password = true

  allocated_storage     = var.allocated_storage
  max_allocated_storage = var.max_allocated_storage
  storage_type          = "gp3"
  storage_encrypted     = true

  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [aws_security_group.db.id]
  publicly_accessible    = false
  multi_az               = var.multi_az
  parameter_group_name   = aws_db_parameter_group.this.name

  backup_retention_period    = var.backup_retention_days
  backup_window              = "02:00-03:00"
  maintenance_window         = "sun:03:30-sun:04:30"
  copy_tags_to_snapshot      = true
  auto_minor_version_upgrade = true
  apply_immediately          = !var.deletion_protection

  deletion_protection       = var.deletion_protection
  skip_final_snapshot       = !var.deletion_protection
  final_snapshot_identifier = var.deletion_protection ? "${var.name}-catalog-final" : null

  enabled_cloudwatch_logs_exports = ["postgresql"]

  depends_on = [aws_cloudwatch_log_group.postgresql]
}

output "address" {
  description = "Hostname of the instance."
  value       = aws_db_instance.this.address
}

output "port" {
  description = "Port."
  value       = aws_db_instance.this.port
}

output "db_name" {
  description = "Database name."
  value       = aws_db_instance.this.db_name
}

output "secret_arn" {
  description = "Secrets Manager ARN of the RDS-managed master credentials."
  value       = aws_db_instance.this.master_user_secret[0].secret_arn
}

output "instance_id" {
  description = "DB instance identifier."
  value       = aws_db_instance.this.identifier
}

output "instance_arn" {
  description = "DB instance ARN."
  value       = aws_db_instance.this.arn
}
