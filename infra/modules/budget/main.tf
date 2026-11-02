variable "name" {
  description = "Budget name."
  type        = string
}

variable "monthly_limit_usd" {
  description = "Monthly cost budget in USD."
  type        = number
}

variable "alert_emails" {
  description = "Email addresses notified on budget thresholds."
  type        = list(string)
}

variable "env" {
  description = "Environment name; the budget filters on the env cost-allocation tag."
  type        = string
}

resource "aws_budgets_budget" "monthly" {
  name         = var.name
  budget_type  = "COST"
  limit_amount = format("%.2f", var.monthly_limit_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  cost_filter {
    name   = "TagKeyValue"
    values = [format("user:env$%s", var.env)]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = var.alert_emails
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = var.alert_emails
  }
}

output "budget_name" {
  description = "Name of the budget."
  value       = aws_budgets_budget.monthly.name
}
