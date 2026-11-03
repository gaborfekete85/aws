locals {
  attach_api = var.api != null && length(var.routes) > 0
}

data "aws_iam_policy_document" "assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "this" {
  name                 = var.name
  assume_role_policy   = data.aws_iam_policy_document.assume.json
  permissions_boundary = var.permissions_boundary_arn
}

resource "aws_iam_role_policy_attachment" "basic" {
  role       = aws_iam_role.this.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "vpc" {
  count      = var.vpc == null ? 0 : 1
  role       = aws_iam_role.this.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

resource "aws_iam_role_policy" "extra" {
  count  = var.policy_json == null ? 0 : 1
  name   = "${var.name}-extra"
  role   = aws_iam_role.this.id
  policy = var.policy_json
}

resource "aws_cloudwatch_log_group" "this" {
  name              = "/aws/lambda/${var.name}"
  retention_in_days = var.log_retention_days
}

resource "aws_lambda_function" "this" {
  function_name                  = var.name
  description                    = var.description
  role                           = aws_iam_role.this.arn
  filename                       = var.package_path
  source_code_hash               = filebase64sha256(var.package_path)
  handler                        = var.handler
  runtime                        = var.runtime
  architectures                  = ["arm64"]
  memory_size                    = var.memory_size
  timeout                        = var.timeout
  reserved_concurrent_executions = var.reserved_concurrency

  environment {
    variables = merge({ SERVICE_NAME = var.name }, var.environment)
  }

  dynamic "vpc_config" {
    for_each = var.vpc == null ? [] : [var.vpc]
    content {
      subnet_ids         = vpc_config.value.subnet_ids
      security_group_ids = vpc_config.value.security_group_ids
    }
  }

  tracing_config {
    mode = "Active"
  }

  logging_config {
    log_format = "Text" # our handler already writes JSON lines
    log_group  = aws_cloudwatch_log_group.this.name
  }

  depends_on = [aws_iam_role_policy_attachment.basic]
}

# --- HTTP API routes --------------------------------------------------------
resource "aws_apigatewayv2_integration" "this" {
  count                  = local.attach_api ? 1 : 0
  api_id                 = var.api.api_id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.this.invoke_arn
  payload_format_version = "1.0" # lbz consumes the REST-style event shape
  timeout_milliseconds   = min(var.timeout * 1000, 30000)
}

resource "aws_apigatewayv2_route" "this" {
  for_each           = local.attach_api ? { for r in var.routes : r.route_key => r } : {}
  api_id             = var.api.api_id
  route_key          = each.key
  target             = "integrations/${aws_apigatewayv2_integration.this[0].id}"
  authorization_type = each.value.public ? "NONE" : "JWT"
  authorizer_id      = each.value.public ? null : var.api.authorizer_id

  lifecycle {
    # Fail closed: a protected route must never silently become public.
    precondition {
      condition     = each.value.public || var.api.authorizer_id != null
      error_message = "Route ${each.key} is not public but the API has no JWT authorizer."
    }
  }
}

resource "aws_lambda_permission" "api" {
  count         = local.attach_api ? 1 : 0
  statement_id  = "AllowApiGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.this.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${var.api.execution_arn}/*/*"
}

# --- EventBridge rules ------------------------------------------------------
resource "aws_cloudwatch_event_rule" "this" {
  for_each       = var.event_rules
  name           = "${var.name}-${each.key}"
  event_bus_name = var.bus_name
  event_pattern  = each.value
}

resource "aws_cloudwatch_event_target" "this" {
  for_each       = var.event_rules
  rule           = aws_cloudwatch_event_rule.this[each.key].name
  event_bus_name = var.bus_name
  arn            = aws_lambda_function.this.arn

  retry_policy {
    maximum_retry_attempts       = 8
    maximum_event_age_in_seconds = 3600
  }
}

resource "aws_lambda_permission" "events" {
  for_each      = var.event_rules
  statement_id  = "AllowEventBridge-${each.key}"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.this.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.this[each.key].arn
}

# --- schedule ---------------------------------------------------------------
resource "aws_cloudwatch_event_rule" "schedule" {
  count               = var.schedule_expression == null ? 0 : 1
  name                = "${var.name}-schedule"
  schedule_expression = var.schedule_expression
}

resource "aws_cloudwatch_event_target" "schedule" {
  count = var.schedule_expression == null ? 0 : 1
  rule  = aws_cloudwatch_event_rule.schedule[0].name
  arn   = aws_lambda_function.this.arn
}

resource "aws_lambda_permission" "schedule" {
  count         = var.schedule_expression == null ? 0 : 1
  statement_id  = "AllowSchedule"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.this.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.schedule[0].arn
}

# --- async failure handling (EventBridge consumers) ---------------------------
resource "aws_lambda_function_event_invoke_config" "this" {
  count                        = var.async_failure_queue_arn == null ? 0 : 1
  function_name                = aws_lambda_function.this.function_name
  maximum_retry_attempts       = var.async_max_retries
  maximum_event_age_in_seconds = 3600

  destination_config {
    on_failure {
      destination = var.async_failure_queue_arn
    }
  }
}

data "aws_iam_policy_document" "dlq" {
  count = var.async_failure_queue_arn == null ? 0 : 1
  statement {
    actions   = ["sqs:SendMessage"]
    resources = [var.async_failure_queue_arn]
  }
}

resource "aws_iam_role_policy" "dlq" {
  count  = var.async_failure_queue_arn == null ? 0 : 1
  name   = "${var.name}-dlq"
  role   = aws_iam_role.this.id
  policy = data.aws_iam_policy_document.dlq[0].json
}
