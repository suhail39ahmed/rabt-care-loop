# Written only when the Terraform runner can reach the vault data plane (see root local.write_secrets).

resource "time_sleep" "rbac" {
  create_duration = var.rbac_propagation_wait
}

resource "time_static" "created" {}

resource "azurerm_key_vault_secret" "this" {
  for_each        = toset(var.secret_names)
  name            = each.value
  value           = var.secrets[each.value].value
  key_vault_id    = var.key_vault_id
  content_type    = var.secrets[each.value].content_type
  expiration_date = timeadd(time_static.created.rfc3339, "${var.expiry_days * 24}h")
  tags            = var.tags

  depends_on = [time_sleep.rbac]
}
