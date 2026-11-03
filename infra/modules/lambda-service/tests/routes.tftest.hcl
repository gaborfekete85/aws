mock_provider "aws" {
  mock_data "aws_iam_policy_document" {
    defaults = { json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}" }
  }
  mock_resource "aws_iam_role" {
    defaults = { arn = "arn:aws:iam::123456789012:role/meeton-test-fn" }
  }
  mock_resource "aws_lambda_function" {
    defaults = {
      arn        = "arn:aws:lambda:eu-central-1:123456789012:function:meeton-test-fn"
      invoke_arn = "arn:aws:apigateway:eu-central-1:lambda:path/2015-03-31/functions/fn/invocations"
    }
  }
}

variables {
  name                     = "meeton-test-fn"
  package_path             = "tests/fixture.zip"
  handler                  = "h.handle"
  permissions_boundary_arn = "arn:aws:iam::123456789012:policy/meeton-workload-boundary"
  api = {
    api_id        = "api123"
    execution_arn = "arn:aws:execute-api:eu-central-1:123456789012:api123"
    authorizer_id = "auth1"
  }
  routes = [
    { route_key = "GET /events", public = true },
    { route_key = "POST /events" },
  ]
}

run "protected_routes_use_jwt_public_routes_do_not" {
  command = apply

  assert {
    condition     = aws_apigatewayv2_route.this["POST /events"].authorization_type == "JWT"
    error_message = "routes default to JWT"
  }
  assert {
    condition     = aws_apigatewayv2_route.this["POST /events"].authorizer_id == "auth1"
    error_message = "protected route must use the authorizer"
  }
  assert {
    condition     = aws_apigatewayv2_route.this["GET /events"].authorization_type == "NONE"
    error_message = "public route must be explicitly NONE"
  }
}

run "runs_arm64_with_boundary_and_payload_v1" {
  command = apply

  assert {
    condition     = aws_lambda_function.this.architectures == tolist(["arm64"])
    error_message = "Lambdas run on arm64"
  }
  assert {
    condition     = aws_iam_role.this.permissions_boundary == var.permissions_boundary_arn
    error_message = "execution role must carry the workload boundary"
  }
  assert {
    condition     = aws_apigatewayv2_integration.this[0].payload_format_version == "1.0"
    error_message = "lbz needs payload format 1.0"
  }
}

run "protected_route_without_authorizer_fails_closed" {
  command = plan
  variables {
    api = {
      api_id        = "api123"
      execution_arn = "arn:aws:execute-api:eu-central-1:123456789012:api123"
      authorizer_id = null
    }
  }
  expect_failures = [aws_apigatewayv2_route.this]
}
