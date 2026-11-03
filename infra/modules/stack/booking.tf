# Bookings: single-table design (see services/booking/src/booking/table.py).
resource "aws_dynamodb_table" "bookings" {
  name         = "${local.name}-bookings"
  billing_mode = "PAY_PER_REQUEST" # spiky, low baseline traffic: see docs/cost.md
  hash_key     = "pk"
  range_key    = "sk"

  dynamic "attribute" {
    for_each = toset(["pk", "sk", "gsi1pk", "gsi1sk", "gsi2pk", "gsi2sk"])
    content {
      name = attribute.value
      type = "S"
    }
  }

  global_secondary_index {
    name            = "gsi1" # Bookings by Attendee
    hash_key        = "gsi1pk"
    range_key       = "gsi1sk"
    projection_type = "ALL"
  }

  global_secondary_index {
    name            = "gsi2" # Bookings by Event
    hash_key        = "gsi2pk"
    range_key       = "gsi2sk"
    projection_type = "ALL"
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  stream_enabled   = true
  stream_view_type = "NEW_AND_OLD_IMAGES"

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }

  deletion_protection_enabled = var.env == "prod"
}

resource "aws_sqs_queue" "booking_dlq" {
  name                      = "${local.name}-booking-dlq"
  message_retention_seconds = 1209600 # 14 days
  sqs_managed_sse_enabled   = true
}

locals {
  booking_env = merge(local.common_env, {
    BOOKINGS_TABLE = aws_dynamodb_table.bookings.name
    HOLD_MINUTES   = tostring(var.hold_minutes)
  })
}

data "aws_iam_policy_document" "booking_table" {
  statement {
    actions = [
      "dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:DeleteItem",
      "dynamodb:Query", "dynamodb:ConditionCheckItem",
    ]
    resources = [aws_dynamodb_table.bookings.arn, "${aws_dynamodb_table.bookings.arn}/index/*"]
  }
  statement {
    actions   = ["events:PutEvents"]
    resources = [module.eventbridge.bus_arn]
  }
}

# Keeps the EventPlaces projection in sync with the Catalog.
module "booking_consumer" {
  source                   = "../lambda-service"
  name                     = "${local.name}-booking-consumer"
  description              = "Booking: consumes Catalog events into the Places counter"
  package_path             = "${var.lambda_packages_dir}/booking.zip"
  handler                  = "booking.consumers.handle"
  memory_size              = 256
  permissions_boundary_arn = local.boundary_arn
  log_retention_days       = var.log_retention_days
  environment              = local.booking_env
  policy_json              = data.aws_iam_policy_document.booking_table.json
  bus_name                 = module.eventbridge.bus_name
  async_failure_queue_arn  = aws_sqs_queue.booking_dlq.arn
  event_rules = {
    catalog = jsonencode({
      source        = ["localbini.catalog"]
      "detail-type" = ["EventPublished", "EventUpdated", "EventCancelled"]
    })
  }
}

module "booking_api" {
  source                   = "../lambda-service"
  name                     = "${local.name}-booking-api"
  description              = "Booking: request Bookings (Holds), list my Bookings, availability"
  package_path             = "${var.lambda_packages_dir}/booking.zip"
  handler                  = "booking.api.handle"
  memory_size              = 512
  permissions_boundary_arn = local.boundary_arn
  log_retention_days       = var.log_retention_days
  environment              = local.booking_env
  policy_json              = data.aws_iam_policy_document.booking_table.json
  api                      = local.api
  routes = [
    { route_key = "POST /events/{event_id}/bookings" },
    { route_key = "GET /me/bookings" },
    { route_key = "GET /bookings/{booking_id}" },
    { route_key = "GET /events/{event_id}/availability", public = true },
  ]
}
