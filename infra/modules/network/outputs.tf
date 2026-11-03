output "vpc_id" {
  description = "VPC id."
  value       = aws_vpc.this.id
}

output "vpc_cidr_block" {
  description = "VPC CIDR."
  value       = aws_vpc.this.cidr_block
}

output "private_subnet_ids" {
  description = "Private subnet ids (Lambdas, RDS)."
  value       = aws_subnet.private[*].id
}

output "lambda_security_group_id" {
  description = "Security group for in-VPC Lambdas."
  value       = aws_security_group.lambda.id
}

output "egress_public_ip" {
  description = "Public IPv4 that private-subnet traffic leaves from (NAT), or null without NAT."
  value = (
    var.nat == "gateway" ? aws_eip.nat[0].public_ip :
    var.nat == "instance" ? aws_eip.nat_instance[0].public_ip : null
  )
}
