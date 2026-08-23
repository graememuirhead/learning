locals {
  suffix               = "${var.app_name}-${var.environment}"
  storage_account_name = substr(replace("${var.app_name}${var.environment}st", "-", ""), 0, 24)
  function_app_name    = "${local.suffix}-func"
  app_service_plan_name = "${local.suffix}-plan"
  app_insights_name    = "${local.suffix}-ai"
  log_analytics_name   = "${local.suffix}-law"
  key_vault_name       = "${local.suffix}-kv"
  base_url             = "https://${local.function_app_name}.azurewebsites.net/api"
}

# --------------------------------------------------------------------------- #
# Resource Group
# --------------------------------------------------------------------------- #

resource "azurerm_resource_group" "main" {
  name     = "${local.suffix}-rg"
  location = var.location
}

# --------------------------------------------------------------------------- #
# Storage Account
# --------------------------------------------------------------------------- #

resource "azurerm_storage_account" "main" {
  name                     = local.storage_account_name
  resource_group_name      = azurerm_resource_group.main.name
  location                 = azurerm_resource_group.main.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  min_tls_version          = "TLS1_2"
  allow_nested_items_to_be_public = false
  https_traffic_only_enabled      = true
}

resource "azurerm_storage_container" "passes" {
  name                  = "passes"
  storage_account_id    = azurerm_storage_account.main.id
  container_access_type = "private"
}

# --------------------------------------------------------------------------- #
# Log Analytics Workspace (required by Application Insights v2)
# --------------------------------------------------------------------------- #

resource "azurerm_log_analytics_workspace" "main" {
  name                = local.log_analytics_name
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "PerGB2018"
  retention_in_days   = 90
}

# --------------------------------------------------------------------------- #
# Application Insights
# --------------------------------------------------------------------------- #

resource "azurerm_application_insights" "main" {
  name                = local.app_insights_name
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  workspace_id        = azurerm_log_analytics_workspace.main.id
  application_type    = "web"
  retention_in_days   = 90
}

# --------------------------------------------------------------------------- #
# App Service Plan (Consumption / Serverless)
# --------------------------------------------------------------------------- #

resource "azurerm_service_plan" "main" {
  name                = local.app_service_plan_name
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  os_type             = "Linux"
  sku_name            = "Y1"
}

# --------------------------------------------------------------------------- #
# Function App
# --------------------------------------------------------------------------- #

resource "azurerm_linux_function_app" "main" {
  name                       = local.function_app_name
  resource_group_name        = azurerm_resource_group.main.name
  location                   = azurerm_resource_group.main.location
  service_plan_id            = azurerm_service_plan.main.id
  storage_account_name       = azurerm_storage_account.main.name
  storage_account_access_key = azurerm_storage_account.main.primary_access_key
  https_only                 = true

  identity {
    type = "SystemAssigned"
  }

  site_config {
    application_stack {
      python_version = "3.11"
    }
    application_insights_key               = azurerm_application_insights.main.instrumentation_key
    application_insights_connection_string = azurerm_application_insights.main.connection_string
  }

  app_settings = {
    # Runtime
    FUNCTIONS_WORKER_RUNTIME = "python"
    FUNCTIONS_EXTENSION_VERSION = "~4"

    # Storage
    STORAGE_CONNECTION_STRING = azurerm_storage_account.main.primary_connection_string
    STORAGE_CONTAINER_PASSES  = "passes"

    # API base URL
    BASE_URL = local.base_url

    # Apple Wallet
    APPLE_PASS_TYPE_IDENTIFIER = var.apple_pass_type_identifier
    APPLE_TEAM_IDENTIFIER      = var.apple_team_identifier
    APPLE_PASS_CERTIFICATE_PEM = var.apple_pass_certificate_pem
    APPLE_PASS_KEY_PEM         = var.apple_pass_key_pem
    APPLE_WWDR_CERTIFICATE_PEM = var.apple_wwdr_certificate_pem
    APPLE_KEY_PASSWORD         = var.apple_key_password

    # Google Wallet
    GOOGLE_ISSUER_ID            = var.google_issuer_id
    GOOGLE_CLASS_SUFFIX         = var.google_class_suffix
    GOOGLE_SERVICE_ACCOUNT_JSON = var.google_service_account_json

    # Logo
    LOGO_FILENAME = var.logo_filename
  }
}

# --------------------------------------------------------------------------- #
# Key Vault
# --------------------------------------------------------------------------- #

data "azurerm_client_config" "current" {}

resource "azurerm_key_vault" "main" {
  name                       = local.key_vault_name
  resource_group_name        = azurerm_resource_group.main.name
  location                   = azurerm_resource_group.main.location
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "standard"
  enable_rbac_authorization  = true
  soft_delete_retention_days = 90
  purge_protection_enabled   = false
}

# Grant the Function App's managed identity the Key Vault Secrets User role
resource "azurerm_role_assignment" "func_kv_secrets_user" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_linux_function_app.main.identity[0].principal_id
}
