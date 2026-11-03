output "vpc_id" {
  description = "VPC id."
  value       = module.network.vpc_id
}

output "api_endpoint" {
  description = "Base URL of the HTTP API."
  value       = module.api.api_endpoint
}

output "event_bus_name" {
  description = "Domain event bus."
  value       = module.eventbridge.bus_name
}

output "user_pool_id" {
  description = "Cognito user pool id."
  value       = module.cognito.user_pool_id
}

output "web_client_id" {
  description = "Cognito app client id for the web app."
  value       = module.cognito.web_client_id
}

output "hosted_ui_domain" {
  description = "Cognito Hosted UI domain."
  value       = module.cognito.hosted_ui_domain
}

output "catalog_migrate_function" {
  description = "Lambda that runs Catalog migrations."
  value       = module.catalog_migrate.function_name
}

output "media_cdn_domain" {
  description = "CloudFront domain for Cover pictures."
  value       = module.media.cdn_domain
}

output "web_url" {
  description = "URL of the web app (Amplify main branch)."
  value       = local.amplify_url
}

output "amplify_app_id" {
  description = "Amplify app id (for deployments)."
  value       = aws_amplify_app.web.id
}

output "bus_spy_queue_url" {
  description = "Dev only: SQS queue receiving every domain event (integration tests)."
  value       = try(aws_sqs_queue.bus_spy[0].url, null)
}

output "test_client_id" {
  description = "Dev only: Cognito client for integration-test logins."
  value       = module.cognito.test_client_id
}
