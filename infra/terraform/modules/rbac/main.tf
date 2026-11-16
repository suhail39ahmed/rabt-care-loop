# Least-privilege role assignments; every one carries a description naming its purpose.
resource "azurerm_role_assignment" "this" {
  for_each             = var.assignments
  scope                = each.value.scope
  role_definition_name = each.value.role
  principal_id         = each.value.principal_id
  principal_type       = each.value.principal_type
  description          = "rabt: ${each.key}"
}
