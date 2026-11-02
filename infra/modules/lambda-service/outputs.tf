output "function_name" {
  description = "Function name."
  value       = aws_lambda_function.this.function_name
}

output "function_arn" {
  description = "Function ARN."
  value       = aws_lambda_function.this.arn
}

output "role_name" {
  description = "Execution role name."
  value       = aws_iam_role.this.name
}

output "role_arn" {
  description = "Execution role ARN."
  value       = aws_iam_role.this.arn
}
