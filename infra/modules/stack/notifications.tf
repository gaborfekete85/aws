# --- SES (sandbox: sender and recipients must be verified; see services/notifications/README.md)
resource "aws_sesv2_email_identity" "sender" {
  email_identity = var.sender_email
}

# --- Bus -> SQS -> Notifications Lambda, with a DLQ for poison messages
resource "aws_sqs_queue" "notifications_dlq" {
  name                      = "${local.name}-notifications-dlq"
  message_retention_seconds = 1209600
  sqs_managed_sse_enabled   = true
}

resource "aws_sqs_queue" "notifications" {
  name                       = "${local.name}-notifications"
  visibility_timeout_seconds = 6 * 60 # >= 6x the function timeout (AWS guidance)
  message_retention_seconds  = 345600
  sqs_managed_sse_enabled    = true

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.notifications_dlq.arn
    maxReceiveCount     = 5
  })
}

resource "aws_cloudwatch_event_rule" "notifications" {
  name           = "${local.name}-notifications"
  event_bus_name = module.eventbridge.bus_name
  event_pattern = jsonencode({
    source        = ["localbini.booking"]
    "detail-type" = ["BookingConfirmed", "EventBookingsCancelled"]
  })
}

resource "aws_cloudwatch_event_target" "notifications" {
  rule           = aws_cloudwatch_event_rule.notifications.name
  event_bus_name = module.eventbridge.bus_name
  arn            = aws_sqs_queue.notifications.arn
}

data "aws_iam_policy_document" "notifications_queue" {
  statement {
    actions   = ["sqs:SendMessage"]
    resources = [aws_sqs_queue.notifications.arn]
    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com"]
    }
    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values   = [aws_cloudwatch_event_rule.notifications.arn]
    }
  }
}

resource "aws_sqs_queue_policy" "notifications" {
  queue_url = aws_sqs_queue.notifications.id
  policy    = data.aws_iam_policy_document.notifications_queue.json
}

# --- sent markers (idempotency: no duplicate email on redelivery)
resource "aws_dynamodb_table" "notifications" {
  name         = "${local.name}-notifications"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"

  attribute {
    name = "pk"
    type = "S"
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  server_side_encryption {
    enabled = true
  }
}

data "aws_iam_policy_document" "notifications" {
  statement {
    actions   = ["ses:SendEmail"]
    resources = [aws_sesv2_email_identity.sender.arn, "arn:aws:ses:${data.aws_region.current.region}:${local.account_id}:identity/*"]
  }
  statement {
    actions   = ["dynamodb:PutItem", "dynamodb:DeleteItem", "dynamodb:GetItem"]
    resources = [aws_dynamodb_table.notifications.arn]
  }
}

module "notifications" {
  source                   = "../lambda-service"
  name                     = "${local.name}-notifications"
  description              = "Notifications: Attendee emails via SES"
  package_path             = "${var.lambda_packages_dir}/notifications.zip"
  handler                  = "notifications.app.handle"
  memory_size              = 256
  timeout                  = 60
  permissions_boundary_arn = local.boundary_arn
  log_retention_days       = var.log_retention_days
  environment = merge(local.common_env, {
    SENDER_EMAIL        = var.sender_email
    NOTIFICATIONS_TABLE = aws_dynamodb_table.notifications.name
    SES_MAX_SEND_RATE   = tostring(var.ses_max_send_rate)
  })
  policy_json = data.aws_iam_policy_document.notifications.json
  sqs_source = {
    queue_arn       = aws_sqs_queue.notifications.arn
    batch_size      = 5
    max_concurrency = 2
  }
}
