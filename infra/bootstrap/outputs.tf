output "state_bucket" {
  description = "Name of the Terraform state bucket (use in envs/*/backend.tf)."
  value       = aws_s3_bucket.state.bucket
}

output "plan_role_arn" {
  description = "Role assumed by pull-request workflows (set as AWS_PLAN_ROLE_ARN in GitHub)."
  value       = aws_iam_role.plan.arn
}

output "deploy_role_arn" {
  description = "Role assumed by deploy workflows (set as AWS_DEPLOY_ROLE_ARN in GitHub)."
  value       = aws_iam_role.deploy.arn
}

output "workload_boundary_arn" {
  description = "Permissions boundary every application role must carry."
  value       = aws_iam_policy.workload_boundary.arn
}
