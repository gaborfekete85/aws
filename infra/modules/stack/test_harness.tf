# Dev only: lets tests/integration assert which domain events reached the bus.
resource "aws_sqs_queue" "bus_spy" {
  count                      = var.enable_test_harness ? 1 : 0
  name                       = "${local.name}-bus-spy"
  message_retention_seconds  = 3600
  visibility_timeout_seconds = 5
  sqs_managed_sse_enabled    = true
}

resource "aws_cloudwatch_event_rule" "bus_spy" {
  count          = var.enable_test_harness ? 1 : 0
  name           = "${local.name}-bus-spy"
  event_bus_name = module.eventbridge.bus_name
  event_pattern  = jsonencode({ source = [{ prefix = "meeton." }] })
}

resource "aws_cloudwatch_event_target" "bus_spy" {
  count          = var.enable_test_harness ? 1 : 0
  rule           = aws_cloudwatch_event_rule.bus_spy[0].name
  event_bus_name = module.eventbridge.bus_name
  arn            = aws_sqs_queue.bus_spy[0].arn
}

data "aws_iam_policy_document" "bus_spy" {
  count = var.enable_test_harness ? 1 : 0
  statement {
    actions   = ["sqs:SendMessage"]
    resources = [aws_sqs_queue.bus_spy[0].arn]
    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com"]
    }
    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values   = [aws_cloudwatch_event_rule.bus_spy[0].arn]
    }
  }
}

resource "aws_sqs_queue_policy" "bus_spy" {
  count     = var.enable_test_harness ? 1 : 0
  queue_url = aws_sqs_queue.bus_spy[0].id
  policy    = data.aws_iam_policy_document.bus_spy[0].json
}
