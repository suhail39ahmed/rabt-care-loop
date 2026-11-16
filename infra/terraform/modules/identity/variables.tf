variable "resource_group_name" {
  description = "Resource group."
  type        = string
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default     = {}
}

variable "location" {
  description = "Region."
  type        = string
}

variable "identities" {
  description = "User-assigned managed identities: map of static key => resource name."
  type        = map(string)
}
