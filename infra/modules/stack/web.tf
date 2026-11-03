# Amplify Hosting for web/. No repository connection: that would need a long-lived
# GitHub token in Terraform state. GitHub Actions builds web/ from main after
# `terraform apply` (so Cognito/API outputs are baked in) and publishes the build
# with `amplify create-deployment` (scripts/deploy_web.sh).
resource "aws_amplify_app" "web" {
  name     = "${local.name}-web"
  platform = "WEB"

  # Single-page app: every non-asset path serves index.html.
  custom_rule {
    source = "</^[^.]+$|\\.(?!(css|gif|ico|jpg|jpeg|js|png|txt|svg|woff|woff2|ttf|map|json|webp)$)([^.]+$)/>"
    target = "/index.html"
    status = "200"
  }

  custom_headers = <<-YAML
    customHeaders:
      - pattern: '**/*'
        headers:
          - key: Strict-Transport-Security
            value: max-age=31536000; includeSubDomains
          - key: X-Content-Type-Options
            value: nosniff
          - key: X-Frame-Options
            value: DENY
          - key: Referrer-Policy
            value: strict-origin-when-cross-origin
  YAML
}

resource "aws_amplify_branch" "main" {
  app_id            = aws_amplify_app.web.id
  branch_name       = "main"
  stage             = var.env == "prod" ? "PRODUCTION" : "DEVELOPMENT"
  enable_auto_build = false
}

locals {
  amplify_url = "https://${aws_amplify_branch.main.branch_name}.${aws_amplify_app.web.default_domain}"
  # Where the web app is served from: Amplify plus any extra origins (e.g. localhost in dev).
  web_origins = distinct(concat([local.amplify_url], var.web_urls))
}
