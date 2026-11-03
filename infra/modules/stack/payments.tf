# --- Stripe keys: placeholders only; filled by hand (see services/payments/README.md)
resource "aws_ssm_parameter" "stripe_secret_key" {
  name             = "/${var.project}/${var.env}/stripe/secret_key"
  type             = "SecureString"
  value_wo         = "CHANGE_ME" # write-only: the real key never enters state
  value_wo_version = 1
  description      = "Stripe secret key (test mode in dev)"
}

resource "aws_ssm_parameter" "stripe_webhook_secret" {
  name             = "/${var.project}/${var.env}/stripe/webhook_secret"
  type             = "SecureString"
  value_wo         = "CHANGE_ME"
  value_wo_version = 1
  description      = "Stripe webhook signing secret"
}

# --- Checkout records + processed webhook ids
resource "aws_dynamodb_table" "payments" {
  name         = "${local.name}-payments"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  range_key    = "sk"

  attribute {
    name = "pk"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }

  ttl {
    attribute_name = "expires_at_epoch"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }

  deletion_protection_enabled = var.env == "prod"
}

resource "aws_sqs_queue" "payments_dlq" {
  name                      = "${local.name}-payments-dlq"
  message_retention_seconds = 1209600
  sqs_managed_sse_enabled   = true
}

data "aws_region" "current" {}

locals {
  payments_env = merge(local.common_env, {
    PAYMENTS_TABLE              = aws_dynamodb_table.payments.name
    STRIPE_SECRET_KEY_PARAM     = aws_ssm_parameter.stripe_secret_key.name
    STRIPE_WEBHOOK_SECRET_PARAM = aws_ssm_parameter.stripe_webhook_secret.name
    WEB_URL                     = var.web_urls[0]
  })
}

data "aws_iam_policy_document" "payments" {
  statement {
    actions = [
      "dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:DeleteItem", "dynamodb:Query",
    ]
    resources = [aws_dynamodb_table.payments.arn]
  }
  statement {
    actions = ["ssm:GetParameter"]
    resources = [
      aws_ssm_parameter.stripe_secret_key.arn,
      aws_ssm_parameter.stripe_webhook_secret.arn,
    ]
  }
  statement {
    actions   = ["kms:Decrypt"]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "kms:ViaService"
      values   = ["ssm.${data.aws_region.current.region}.amazonaws.com"]
    }
  }
  statement {
    actions   = ["events:PutEvents"]
    resources = [module.eventbridge.bus_arn]
  }
}

module "payments_consumer" {
  source                   = "../lambda-service"
  name                     = "${local.name}-payments-consumer"
  description              = "Payments: create/expire Stripe Checkout sessions"
  package_path             = "${var.lambda_packages_dir}/payments.zip"
  handler                  = "payments.consumers.handle"
  memory_size              = 256
  timeout                  = 20
  permissions_boundary_arn = local.boundary_arn
  log_retention_days       = var.log_retention_days
  environment              = local.payments_env
  policy_json              = data.aws_iam_policy_document.payments.json
  bus_name                 = module.eventbridge.bus_name
  async_failure_queue_arn  = aws_sqs_queue.payments_dlq.arn
  event_rules = {
    booking = jsonencode({
      source        = ["localbini.booking"]
      "detail-type" = ["BookingRequested", "HoldExpired"]
    })
  }
}

module "payments_api" {
  source                   = "../lambda-service"
  name                     = "${local.name}-payments-api"
  description              = "Payments: Checkout URL for a Booking"
  package_path             = "${var.lambda_packages_dir}/payments.zip"
  handler                  = "payments.api.handle"
  memory_size              = 256
  permissions_boundary_arn = local.boundary_arn
  log_retention_days       = var.log_retention_days
  environment              = local.payments_env
  policy_json              = data.aws_iam_policy_document.payments.json
  api                      = local.api
  routes = [
    { route_key = "GET /bookings/{booking_id}/checkout" },
  ]
}
