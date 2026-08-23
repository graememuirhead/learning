output "function_app_name" {
  description = "Name of the deployed Function App"
  value       = azurerm_linux_function_app.main.name
}

output "function_app_url" {
  description = "Base URL of the API"
  value       = "https://${azurerm_linux_function_app.main.default_hostname}/api"
}

output "resource_group_name" {
  description = "Name of the resource group"
  value       = azurerm_resource_group.main.name
}

output "storage_account_name" {
  description = "Name of the storage account"
  value       = azurerm_storage_account.main.name
}

output "key_vault_name" {
  description = "Name of the Key Vault"
  value       = azurerm_key_vault.main.name
}

output "storage_connection_string" {
  description = "Storage account connection string"
  value       = azurerm_storage_account.main.primary_connection_string
  sensitive   = true
}
