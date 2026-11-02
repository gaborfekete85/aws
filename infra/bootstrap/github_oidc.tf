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
  }
}

# --- state access shared by both roles -------------------------------------
data "aws_iam_policy_document" "state_access" {
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

resource "aws_iam_policy" "state_access" {
  name   = "${local.name_prefix}-tfstate-access"
  policy = data.aws_iam_policy_document.state_access.json
}

# --- plan role ----------------------------------------------------------------
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
  policy_arn = aws_iam_policy.state_access.arn
}

# Plan needs to decrypt SSM SecureString placeholders it reads as data sources.
data "aws_iam_policy_document" "plan_extra" {
  statement {
    actions   = ["ssm:GetParameter", "ssm:GetParameters", "ssm:GetParametersByPath"]
    resources = ["arn:aws:ssm:${var.region}:${local.account_id}:parameter/${var.project}/*"]
  }
}

resource "aws_iam_role_policy" "plan_extra" {
  role   = aws_iam_role.plan.id
  policy = data.aws_iam_policy_document.plan_extra.json
}

# --- deploy role --------------------------------------------------------------
# Service-level permissions for exactly the services Localbini uses. IAM is
# restricted to roles/policies carrying the project prefix so the role cannot
# escalate to arbitrary principals.
data "aws_iam_policy_document" "deploy" {
  statement {
    sid = "ManagedServices"
    actions = [
      "apigateway:*",
      "amplify:*",
      "budgets:*",
      "cloudfront:*",
      "cognito-idp:*",
      "dynamodb:*",
      "ec2:*Vpc*", "ec2:*Subnet*", "ec2:*RouteTable*", "ec2:*Route", "ec2:*SecurityGroup*",
      "ec2:*VpcEndpoint*", "ec2:*Tags", "ec2:Describe*", "ec2:*NetworkInterface*",
      "events:*",
      "lambda:*",
      "logs:*",
      "rds:*",
      "s3:*",
      "secretsmanager:*",
      "ses:*",
      "sqs:*",
      "ssm:*",
      "scheduler:*",
      "acm:*",
      "cloudwatch:*",
      "kms:DescribeKey", "kms:ListAliases", "kms:CreateGrant",
      "tag:GetResources",
    ]
    resources = ["*"]
  }

  statement {
    sid = "ProjectScopedIam"
    actions = [
      "iam:CreateRole", "iam:DeleteRole", "iam:GetRole", "iam:UpdateRole", "iam:TagRole", "iam:UntagRole",
      "iam:UpdateAssumeRolePolicy", "iam:ListRolePolicies", "iam:ListAttachedRolePolicies",
      "iam:PutRolePolicy", "iam:GetRolePolicy", "iam:DeleteRolePolicy",
      "iam:AttachRolePolicy", "iam:DetachRolePolicy", "iam:ListInstanceProfilesForRole",
      "iam:CreatePolicy", "iam:DeletePolicy", "iam:GetPolicy", "iam:GetPolicyVersion",
      "iam:ListPolicyVersions", "iam:CreatePolicyVersion", "iam:DeletePolicyVersion", "iam:TagPolicy",
      "iam:PassRole",
    ]
    resources = [
      "arn:aws:iam::${local.account_id}:role/${local.name_prefix}-*",
      "arn:aws:iam::${local.account_id}:policy/${local.name_prefix}-*",
    ]
  }

  statement {
    sid       = "ServiceLinkedRoles"
    actions   = ["iam:CreateServiceLinkedRole"]
    resources = ["arn:aws:iam::${local.account_id}:role/aws-service-role/*"]
  }

  statement {
    sid       = "DenyStateBucketTampering"
    effect    = "Deny"
    actions   = ["s3:DeleteBucket", "s3:PutBucketPolicy", "s3:PutBucketVersioning", "s3:PutLifecycleConfiguration"]
    resources = [aws_s3_bucket.state.arn]
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
  policy_arn = aws_iam_policy.state_access.arn
}
