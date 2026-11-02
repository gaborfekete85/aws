output "api_id" {
  description = "HTTP API id."
  value       = aws_apigatewayv2_api.this.id
}

output "api_endpoint" {
  description = "Base URL of the API."
  value       = aws_apigatewayv2_api.this.api_endpoint
}

output "execution_arn" {
  description = "Execution ARN (for Lambda permissions)."
  value       = aws_apigatewayv2_api.this.execution_arn
}

output "authorizer_id" {
  description = "JWT authorizer id, or null."
  value       = try(aws_apigatewayv2_authorizer.jwt[0].id, null)
}
