# Dev cost saver: an RDS instance billed 13 h x 5 days instead of 24 x 7 (~60% less compute).
data "aws_iam_policy_document" "scheduler_assume" {
  count = var.office_hours_only ? 1 : 0
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "scheduler" {
  count                = var.office_hours_only ? 1 : 0
  name                 = "${var.name}-catalog-db-scheduler"
  assume_role_policy   = data.aws_iam_policy_document.scheduler_assume[0].json
  permissions_boundary = var.permissions_boundary_arn
}

data "aws_iam_policy_document" "scheduler" {
  count = var.office_hours_only ? 1 : 0
  statement {
    actions   = ["rds:StartDBInstance", "rds:StopDBInstance"]
    resources = [aws_db_instance.this.arn]
  }
}

resource "aws_iam_role_policy" "scheduler" {
  count  = var.office_hours_only ? 1 : 0
  name   = "start-stop-catalog-db"
  role   = aws_iam_role.scheduler[0].id
  policy = data.aws_iam_policy_document.scheduler[0].json
}

resource "aws_scheduler_schedule" "start" {
  count                        = var.office_hours_only ? 1 : 0
  name                         = "${var.name}-catalog-db-start"
  schedule_expression          = "cron(0 7 ? * MON-FRI *)"
  schedule_expression_timezone = "Europe/Zurich"
  flexible_time_window {
    mode = "OFF"
  }
  target {
    arn      = "arn:aws:scheduler:::aws-sdk:rds:startDBInstance"
    role_arn = aws_iam_role.scheduler[0].arn
    input    = jsonencode({ DbInstanceIdentifier = aws_db_instance.this.identifier })
  }
}

resource "aws_scheduler_schedule" "stop" {
  count                        = var.office_hours_only ? 1 : 0
  name                         = "${var.name}-catalog-db-stop"
  schedule_expression          = "cron(0 20 ? * MON-FRI *)"
  schedule_expression_timezone = "Europe/Zurich"
  flexible_time_window {
    mode = "OFF"
  }
  target {
    arn      = "arn:aws:scheduler:::aws-sdk:rds:stopDBInstance"
    role_arn = aws_iam_role.scheduler[0].arn
    input    = jsonencode({ DbInstanceIdentifier = aws_db_instance.this.identifier })
  }
}
