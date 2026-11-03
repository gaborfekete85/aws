# Activate project/env/owner as cost allocation tags so Cost Explorer and the per-env
# budgets can filter on them. AWS only accepts keys that already appear in billing
# data, so flip this on ~24 h after the first environment deploy (docs/cost.md).
variable "activate_cost_allocation_tags" {
  description = "Activate the project/env/owner cost allocation tags (after the first deploy)."
  type        = bool
  default     = false
}

resource "aws_ce_cost_allocation_tag" "this" {
  for_each = var.activate_cost_allocation_tags ? toset(["project", "env", "owner"]) : toset([])
  tag_key  = each.value
  status   = "Active"
}
