data "aws_region" "current" {}

output "user_pool_id" {
  description = "User pool id."
  value       = aws_cognito_user_pool.this.id
}

output "user_pool_arn" {
  description = "User pool ARN."
  value       = aws_cognito_user_pool.this.arn
}

output "web_client_id" {
  description = "App client id for the web app (JWT audience)."
  value       = aws_cognito_user_pool_client.web.id
}

output "issuer" {
  description = "JWT issuer URL."
  value       = "https://cognito-idp.${data.aws_region.current.region}.amazonaws.com/${aws_cognito_user_pool.this.id}"
}

output "hosted_ui_domain" {
  description = "Hosted UI domain (without https://)."
  value       = "${aws_cognito_user_pool_domain.this.domain}.auth.${data.aws_region.current.region}.amazoncognito.com"
}
