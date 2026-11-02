# Two roles keep CI least-privilege:
#   - plan role:   assumable from pull requests; read-only on AWS + state lock/read.
#   - deploy role: assumable only from `main` and the dev/prod GitHub Environments.

resource "aws_iam_openid_connect_provider" "github" {
  count          = var.create_github_oidc_provider ? 1 : 0
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
}

data "aws_iam_openid_connect_provider" "github" {
  count = var.create_github_oidc_provider ? 0 : 1
  url   = "https://token.actions.githubusercontent.com"
}

locals {
  oidc_provider_arn = var.create_github_oidc_provider ? aws_iam_openid_connect_provider.github[0].arn : data.aws_iam_openid_connect_provider.github[0].arn
  repo              = "repo:${var.github_repository}"
  account_id        = data.aws_caller_identity.current.account_id
  name_prefix       = var.project
}

data "aws_iam_policy_document" "trust_plan" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [local.oidc_provider_arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values = [
        "${local.repo}:pull_request",
        "${local.repo}:ref:refs/heads/main",
      ]
    }
  }
}

data "aws_iam_policy_document" "trust_deploy" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [local.oidc_provider_arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values = [
        "${local.repo}:ref:refs/heads/main",
        "${local.repo}:environment:dev",
        "${local.repo}:environment:prod",
      ]
    }
    # Environment-scoped tokens must still come from main (pair with GitHub
    # Environment deployment-branch rules restricting dev/prod to main).
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:ref"
      values   = ["refs/heads/main"]
    }
  }
}

# --- state access --------------------------------------------------------------
# Plan may read state and manage only the lock file; deploy may write state.
data "aws_iam_policy_document" "state_read_and_lock" {
  statement {
    sid       = "StateBucketList"
    actions   = ["s3:ListBucket", "s3:GetBucketVersioning"]
    resources = [aws_s3_bucket.state.arn]
  }
  statement {
    sid       = "StateRead"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.state.arn}/envs/*"]
  }
  statement {
    sid       = "LockFileOnly"
    actions   = ["s3:PutObject", "s3:DeleteObject"]
    resources = ["${aws_s3_bucket.state.arn}/envs/*.tflock"]
  }
}

data "aws_iam_policy_document" "state_write" {
  statement {
    sid       = "StateBucketList"
    actions   = ["s3:ListBucket", "s3:GetBucketVersioning"]
    resources = [aws_s3_bucket.state.arn]
  }
  statement {
    sid       = "StateObjects"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = ["${aws_s3_bucket.state.arn}/envs/*"]
  }
}

resource "aws_iam_policy" "state_read_and_lock" {
  name   = "${local.name_prefix}-tfstate-read-lock"
  policy = data.aws_iam_policy_document.state_read_and_lock.json
}

resource "aws_iam_policy" "state_write" {
  name   = "${local.name_prefix}-tfstate-write"
  policy = data.aws_iam_policy_document.state_write.json
}

# --- plan role ----------------------------------------------------------------
# PRs from forks never receive an OIDC token (id-token permission is withheld),
# so only branches pushed to this repo can assume it.
resource "aws_iam_role" "plan" {
  name                 = "${local.name_prefix}-gha-plan"
  assume_role_policy   = data.aws_iam_policy_document.trust_plan.json
  max_session_duration = 3600
}

resource "aws_iam_role_policy_attachment" "plan_readonly" {
  role       = aws_iam_role.plan.name
  policy_arn = "arn:aws:iam::aws:policy/ReadOnlyAccess"
}

resource "aws_iam_role_policy_attachment" "plan_state" {
  role       = aws_iam_role.plan.name
  policy_arn = aws_iam_policy.state_read_and_lock.arn
}

# ReadOnlyAccess includes data-plane reads Terraform never needs; deny them so a
# PR workflow cannot exfiltrate application data. lambda:GetFunction (exposes
# env vars + code URL; no secrets live there by design) and
# ssm:GetParameter stay allowed because `terraform plan` refresh needs them;
# SecureString values stay unreadable because kms:Decrypt is denied, and secret
# parameters are written with value_wo so they never reach state.
data "aws_iam_policy_document" "plan_guardrails" {
  statement {
    sid    = "DenyDataPlaneReads"
    effect = "Deny"
    actions = [
      "dynamodb:GetItem", "dynamodb:BatchGetItem", "dynamodb:Query", "dynamodb:Scan",
      "dynamodb:GetRecords", "dynamodb:ExportTableToPointInTime",
      "sqs:ReceiveMessage",
      "secretsmanager:GetSecretValue",
      "rds:DownloadDBLogFilePortion", "rds:DownloadCompleteDBLogFile",
      "logs:GetLogEvents", "logs:FilterLogEvents", "logs:StartQuery",
      "logs:GetLogRecord", "logs:GetQueryResults", "logs:StartLiveTail",
      "dynamodb:PartiQLSelect", "dynamodb:ExecuteStatement", "dynamodb:BatchExecuteStatement",
      "cognito-idp:AdminGetUser", "cognito-idp:ListUsers", "cognito-idp:ListUsersInGroup",
      "cognito-idp:AdminListGroupsForUser", "cognito-idp:AdminListUserAuthEvents",
      "cognito-idp:AdminListDevices", "cognito-idp:AdminGetDevice",
      "ses:GetTemplate", "ses:GetEmailTemplate",
      "kms:Decrypt",
    ]
    resources = ["*"]
  }
  statement {
    sid           = "DenyObjectReadsOutsideState"
    effect        = "Deny"
    actions       = ["s3:GetObject", "s3:GetObjectVersion"]
    not_resources = ["${aws_s3_bucket.state.arn}/envs/*"]
  }
}

resource "aws_iam_role_policy" "plan_guardrails" {
  role   = aws_iam_role.plan.id
  policy = data.aws_iam_policy_document.plan_guardrails.json
}

locals {
  app_prefixes = [for env in ["dev", "prod"] : "${local.name_prefix}-${env}"]
  app_resource_arns = flatten([for p in local.app_prefixes : [
    "arn:aws:dynamodb:${var.region}:${local.account_id}:table/${p}-*",
    "arn:aws:events:${var.region}:${local.account_id}:event-bus/${p}",
    "arn:aws:sqs:${var.region}:${local.account_id}:${p}-*",
    "arn:aws:ssm:${var.region}:${local.account_id}:parameter/${var.project}/${trimprefix(p, "${local.name_prefix}-")}/*",
    "arn:aws:secretsmanager:${var.region}:${local.account_id}:secret:${p}-*",
    "arn:aws:secretsmanager:${var.region}:${local.account_id}:secret:rds!*",
    "arn:aws:s3:::${p}-*/*",
    "arn:aws:lambda:${var.region}:${local.account_id}:function:${p}-*",
  ]])
}

# --- workload permissions boundary ---------------------------------------------
# Every role the deploy role creates must carry this boundary, so a compromised
# deploy cannot mint a role more powerful than an application Lambda needs.
data "aws_iam_policy_document" "workload_boundary" {
  statement {
    sid = "UnscopableWorkloadActions"
    actions = [
      "logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents",
      "xray:PutTraceSegments", "xray:PutTelemetryRecords",
      "ec2:CreateNetworkInterface", "ec2:DescribeNetworkInterfaces", "ec2:DeleteNetworkInterface",
      "ec2:AssignPrivateIpAddresses", "ec2:UnassignPrivateIpAddresses", "ec2:DescribeSubnets", "ec2:DescribeVpcs",
      "ses:SendEmail", "ses:SendRawEmail", "ses:SendTemplatedEmail",
      "cognito-idp:ListUsers", "cognito-idp:AdminAddUserToGroup", "cognito-idp:AdminRemoveUserFromGroup",
      "cognito-idp:AdminListGroupsForUser", "cognito-idp:ListUsersInGroup", "cognito-idp:AdminGetUser",
      "amplify:*",
    ]
    resources = ["*"]
  }

  statement {
    sid = "ProjectResources"
    actions = [
      "dynamodb:*",
      "events:PutEvents",
      "sqs:SendMessage", "sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes", "sqs:ChangeMessageVisibility",
      "ssm:GetParameter", "ssm:GetParameters",
      "secretsmanager:GetSecretValue",
      "s3:GetObject", "s3:PutObject",
      "lambda:InvokeFunction",
    ]
    resources = local.app_resource_arns
  }

  statement {
    sid       = "KmsViaProjectServices"
    actions   = ["kms:Decrypt", "kms:GenerateDataKey"]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "kms:ViaService"
      values = [
        "ssm.${var.region}.amazonaws.com",
        "secretsmanager.${var.region}.amazonaws.com",
        "sqs.${var.region}.amazonaws.com",
        "s3.${var.region}.amazonaws.com",
      ]
    }
  }

  statement {
    sid       = "NeverTheStateBucket"
    effect    = "Deny"
    actions   = ["s3:*"]
    resources = [aws_s3_bucket.state.arn, "${aws_s3_bucket.state.arn}/*"]
  }
}

resource "aws_iam_policy" "workload_boundary" {
  name   = "${local.name_prefix}-workload-boundary"
  policy = data.aws_iam_policy_document.workload_boundary.json
}

# --- deploy role --------------------------------------------------------------
locals {
  protected_iam = [
    aws_iam_role.plan.arn,
    "arn:aws:iam::${local.account_id}:role/${local.name_prefix}-gha-*",
    "arn:aws:iam::${local.account_id}:policy/${local.name_prefix}-gha-*",
    "arn:aws:iam::${local.account_id}:policy/${local.name_prefix}-tfstate-*",
    aws_iam_policy.workload_boundary.arn,
  ]
  project_roles    = "arn:aws:iam::${local.account_id}:role/${local.name_prefix}-*"
  project_policies = "arn:aws:iam::${local.account_id}:policy/${local.name_prefix}-*"
}

data "aws_iam_policy_document" "deploy" {
  # Control-plane services whose ARNs are id-based (no name prefix to scope on).
  statement {
    sid = "IdScopedServices"
    actions = [
      "apigateway:*",
      "amplify:*",
      "budgets:*",
      "cloudfront:*",
      "cognito-idp:*",
      "rds:*",
      "ses:*",
      "acm:*",
      "cloudwatch:*",
      "ec2:*Vpc*", "ec2:*Subnet*", "ec2:*RouteTable*", "ec2:*Route", "ec2:*SecurityGroup*",
      "ec2:*InternetGateway*", "ec2:*Address*", "ec2:*NatGateway*",
      "ec2:RunInstances", "ec2:TerminateInstances", "ec2:ModifyInstanceAttribute",
      "ec2:*Tags", "ec2:Describe*", "ec2:*NetworkInterface*",
      "ssm:GetParameter", "ssm:DescribeParameters",
      "tag:GetResources",
      "logs:Describe*", "logs:ListTagsForResource",
      "lambda:List*", "lambda:GetAccountSettings", "lambda:*EventSourceMapping*",
      "events:List*", "events:Describe*",
      "sqs:ListQueues",
      "scheduler:*",
      "secretsmanager:ListSecrets",
    ]
    resources = ["*"]
  }

  # Name-scoped services: only resources carrying the project prefix.
  statement {
    sid     = "NameScopedServices"
    actions = ["lambda:*", "dynamodb:*", "sqs:*", "events:*", "logs:*", "ssm:*", "secretsmanager:*", "s3:*"]
    resources = [
      "arn:aws:lambda:${var.region}:${local.account_id}:function:${local.name_prefix}-*",
      "arn:aws:dynamodb:${var.region}:${local.account_id}:table/${local.name_prefix}-*",
      "arn:aws:sqs:${var.region}:${local.account_id}:${local.name_prefix}-*",
      "arn:aws:events:${var.region}:${local.account_id}:event-bus/${local.name_prefix}-*",
      "arn:aws:events:${var.region}:${local.account_id}:rule/${local.name_prefix}-*",
      "arn:aws:logs:${var.region}:${local.account_id}:log-group:/aws/lambda/${local.name_prefix}-*",
      "arn:aws:logs:${var.region}:${local.account_id}:log-group:/aws/apigateway/${local.name_prefix}-*",
      "arn:aws:ssm:${var.region}:${local.account_id}:parameter/${var.project}/*",
      "arn:aws:secretsmanager:${var.region}:${local.account_id}:secret:${local.name_prefix}-*",
      "arn:aws:secretsmanager:${var.region}:${local.account_id}:secret:rds!*",
      # Env-prefixed buckets only, so the state bucket (localbini-tfstate-*) never matches.
      "arn:aws:s3:::${local.name_prefix}-dev-*",
      "arn:aws:s3:::${local.name_prefix}-dev-*/*",
      "arn:aws:s3:::${local.name_prefix}-prod-*",
      "arn:aws:s3:::${local.name_prefix}-prod-*/*",
    ]
  }

  statement {
    sid       = "KmsForAwsResourcesOnly"
    actions   = ["kms:DescribeKey", "kms:ListAliases", "kms:CreateGrant"]
    resources = ["*"]
    condition {
      test     = "Bool"
      variable = "kms:GrantIsForAWSResource"
      values   = ["true"]
    }
  }

  # IAM reads and non-escalating changes on project roles/policies.
  statement {
    sid = "ProjectIamManage"
    actions = [
      "iam:GetRole", "iam:UpdateRole", "iam:TagRole", "iam:UntagRole", "iam:DeleteRole",
      "iam:ListRolePolicies", "iam:ListAttachedRolePolicies", "iam:ListInstanceProfilesForRole",
      "iam:GetRolePolicy", "iam:DeleteRolePolicy", "iam:DetachRolePolicy",
      "iam:CreatePolicy", "iam:DeletePolicy", "iam:GetPolicy", "iam:GetPolicyVersion",
      "iam:ListPolicyVersions", "iam:CreatePolicyVersion", "iam:DeletePolicyVersion", "iam:TagPolicy",
    ]
    resources = [local.project_roles, local.project_policies]
  }

  # Trust policies are set at CreateRole time only (UpdateAssumeRolePolicy is not
  # granted), and roles may be passed only to the services that run workloads.
  statement {
    sid       = "PassProjectRolesToWorkloadServices"
    actions   = ["iam:PassRole"]
    resources = [local.project_roles]
    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values = [
        "lambda.amazonaws.com",
        "apigateway.amazonaws.com",
        "amplify.amazonaws.com",
        "scheduler.amazonaws.com",
        "events.amazonaws.com",
        "cognito-idp.amazonaws.com",
        "rds.amazonaws.com",
        "monitoring.rds.amazonaws.com",
      ]
    }
  }

  # Creating roles or granting them permissions requires the workload boundary.
  statement {
    sid       = "ProjectIamGrantWithBoundary"
    actions   = ["iam:CreateRole", "iam:PutRolePolicy", "iam:AttachRolePolicy", "iam:PutRolePermissionsBoundary"]
    resources = [local.project_roles]
    condition {
      test     = "StringEquals"
      variable = "iam:PermissionsBoundary"
      values   = [aws_iam_policy.workload_boundary.arn]
    }
  }

  statement {
    sid       = "AttachOnlyProjectOrLambdaManagedPolicies"
    effect    = "Deny"
    actions   = ["iam:AttachRolePolicy"]
    resources = ["*"]
    condition {
      test     = "ArnNotLike"
      variable = "iam:PolicyARN"
      values = [
        local.project_policies,
        "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
        "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole",
        "arn:aws:iam::aws:policy/service-role/AWSLambdaSQSQueueExecutionRole",
        "arn:aws:iam::aws:policy/AdministratorAccess-Amplify",
      ]
    }
  }

  statement {
    sid       = "ServiceLinkedRoles"
    actions   = ["iam:CreateServiceLinkedRole"]
    resources = ["arn:aws:iam::${local.account_id}:role/aws-service-role/*"]
  }

  statement {
    sid       = "ProtectCiIdentityAndBoundary"
    effect    = "Deny"
    actions   = ["iam:*"]
    resources = local.protected_iam
  }

  statement {
    sid       = "NoBoundaryRemoval"
    effect    = "Deny"
    actions   = ["iam:DeleteRolePermissionsBoundary"]
    resources = ["*"]
  }

  statement {
    sid    = "ProtectStateBucket"
    effect = "Deny"
    actions = [
      "s3:DeleteBucket*", "s3:PutBucket*", "s3:PutLifecycleConfiguration",
      "s3:PutEncryptionConfiguration", "s3:PutReplicationConfiguration",
    ]
    resources = [aws_s3_bucket.state.arn]
  }

  statement {
    sid       = "ProtectStateHistory"
    effect    = "Deny"
    actions   = ["s3:DeleteObjectVersion", "s3:PutObjectAcl"]
    resources = ["${aws_s3_bucket.state.arn}/*"]
  }
}

resource "aws_iam_policy" "deploy" {
  name   = "${local.name_prefix}-gha-deploy"
  policy = data.aws_iam_policy_document.deploy.json
}

resource "aws_iam_role" "deploy" {
  name                 = "${local.name_prefix}-gha-deploy"
  assume_role_policy   = data.aws_iam_policy_document.trust_deploy.json
  max_session_duration = 3600
}

resource "aws_iam_role_policy_attachment" "deploy" {
  role       = aws_iam_role.deploy.name
  policy_arn = aws_iam_policy.deploy.arn
}

resource "aws_iam_role_policy_attachment" "deploy_state" {
  role       = aws_iam_role.deploy.name
  policy_arn = aws_iam_policy.state_write.arn
}
