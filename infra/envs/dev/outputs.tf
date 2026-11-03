output "vpc_id" {
  description = "VPC id."
  value       = module.stack.vpc_id
}

output "api_endpoint" {
  description = "Base URL of the HTTP API."
  value       = module.stack.api_endpoint
}

output "event_bus_name" {
  description = "Domain event bus."
  value       = module.stack.event_bus_name
}

output "user_pool_id" {
  description = "Cognito user pool id."
  value       = module.stack.user_pool_id
}

output "web_client_id" {
  description = "Cognito web app client id."
  value       = module.stack.web_client_id
}

output "hosted_ui_domain" {
  description = "Cognito Hosted UI domain."
  value       = module.stack.hosted_ui_domain
}

output "catalog_migrate_function" {
  description = "Lambda that runs Catalog migrations."
  value       = module.stack.catalog_migrate_function
}

output "web_url" {
  description = "URL of the web app."
  value       = module.stack.web_url
}

output "amplify_app_id" {
  description = "Amplify app id."
  value       = module.stack.amplify_app_id
}

output "bus_spy_queue_url" {
  description = "SQS queue receiving every domain event (integration tests)."
  value       = module.stack.bus_spy_queue_url
}

output "test_client_id" {
  description = "Cognito client for integration-test logins."
  value       = module.stack.test_client_id
}

output "egress_public_ip" {
  description = "Public IPv4 of the dev NAT (the address the existing database allowlists)."
  value       = module.stack.egress_public_ip
}
