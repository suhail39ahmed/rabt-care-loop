variable "assignments" {
  description = "Role assignments keyed by a static name. scope/principal_id may be unknown until apply."
  type = map(object({
    scope          = string
    role           = string
    principal_id   = string
    principal_type = optional(string)
  }))
}
