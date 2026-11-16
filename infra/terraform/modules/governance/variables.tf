variable "name" {
  description = "Naming base for the budget and lock (budget-<name>, lock-<name>)."
  type        = string
}

variable "resource_group_id" {
  description = "Resource group the budget and lock apply to."
  type        = string
}

variable "budget_amount" {
  description = "Monthly budget in the billing currency."
  type        = number

  validation {
    condition     = var.budget_amount > 0
    error_message = "budget_amount must be positive."
  }
}

variable "budget_start_date" {
  description = "Budget start (first day of a month, RFC3339). null = first day of the current month at first apply."
  type        = string
  default     = null
}

variable "contact_emails" {
  description = "Budget notification emails."
  type        = list(string)
}

variable "action_group_id" {
  description = "Action group notified by the budget."
  type        = string
}

variable "enable_resource_lock" {
  description = "Put a CanNotDelete lock on the resource group."
  type        = bool
  default     = false
}

variable "defender_plans" {
  description = "Microsoft Defender for Cloud plans to turn on (subscription-wide, billed). Empty = none."
  type        = list(string)
  default     = []
}
