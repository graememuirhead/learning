@description('Base name for all resources (e.g. ryetri)')
param appName string = 'ryetri'

@description('Azure region')
param location string = resourceGroup().location

@description('Environment suffix (dev / prod)')
@allowed(['dev', 'prod'])
param environment string = 'prod'

// ---- Derived names --------------------------------------------------------

var suffix = '${appName}-${environment}'
var storageAccountName = replace('${appName}${environment}st', '-', '')
var functionAppName = '${suffix}-func'
var appServicePlanName = '${suffix}-plan'
var appInsightsName = '${suffix}-ai'
var keyVaultName = '${suffix}-kv'

// ---- Storage Account ------------------------------------------------------

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageAccountName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    supportsHttpsTrafficOnly: true
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-01-01' = {
  parent: storageAccount
  name: 'default'
}

resource passesContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  parent: blobService
  name: 'passes'
  properties: {
    publicAccess: 'None'
  }
}

// ---- Application Insights -------------------------------------------------

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    RetentionInDays: 90
  }
}

// ---- App Service Plan (Consumption / Serverless) --------------------------

resource appServicePlan 'Microsoft.Web/serverfarms@2023-01-01' = {
  name: appServicePlanName
  location: location
  sku: {
    name: 'Y1'
    tier: 'Dynamic'
  }
  kind: 'functionapp'
  properties: {
    reserved: true   // Linux
  }
}

// ---- Azure Function App ---------------------------------------------------

resource functionApp 'Microsoft.Web/sites@2023-01-01' = {
  name: functionAppName
  location: location
  kind: 'functionapp,linux'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: appServicePlan.id
    httpsOnly: true
    siteConfig: {
      pythonVersion: '3.11'
      appSettings: [
        {
          name: 'AzureWebJobsStorage'
          value: 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};AccountKey=${storageAccount.listKeys().keys[0].value};EndpointSuffix=${az.environment().suffixes.storage}'
        }
        {
          name: 'WEBSITE_CONTENTAZUREFILECONNECTIONSTRING'
          value: 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};AccountKey=${storageAccount.listKeys().keys[0].value};EndpointSuffix=${az.environment().suffixes.storage}'
        }
        {
          name: 'WEBSITE_CONTENTSHARE'
          value: toLower(functionAppName)
        }
        {
          name: 'FUNCTIONS_EXTENSION_VERSION'
          value: '~4'
        }
        {
          name: 'FUNCTIONS_WORKER_RUNTIME'
          value: 'python'
        }
        {
          name: 'APPINSIGHTS_INSTRUMENTATIONKEY'
          value: appInsights.properties.InstrumentationKey
        }
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: appInsights.properties.ConnectionString
        }
        {
          name: 'STORAGE_CONNECTION_STRING'
          value: 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};AccountKey=${storageAccount.listKeys().keys[0].value};EndpointSuffix=${az.environment().suffixes.storage}'
        }
        {
          name: 'BASE_URL'
          value: 'https://${functionAppName}.azurewebsites.net/api'
        }
        // ---- Secrets: set manually or via Key Vault reference ----
        // Apple Wallet certificates and Google service account are sensitive.
        // Either:
        //   (a) Add them as app settings via the Azure Portal / az cli after deploy.
        //   (b) Store in Key Vault and reference: @Microsoft.KeyVault(SecretUri=...)
        {
          name: 'APPLE_PASS_TYPE_IDENTIFIER'
          value: 'pass.com.ryetri.membership'
        }
        {
          name: 'APPLE_TEAM_IDENTIFIER'
          value: ''   // set after deploy
        }
        {
          name: 'APPLE_PASS_CERTIFICATE_PEM'
          value: ''   // base64-encoded PEM – set after deploy
        }
        {
          name: 'APPLE_PASS_KEY_PEM'
          value: ''   // base64-encoded PEM – set after deploy
        }
        {
          name: 'APPLE_WWDR_CERTIFICATE_PEM'
          value: ''   // base64-encoded PEM – set after deploy
        }
        {
          name: 'APPLE_KEY_PASSWORD'
          value: ''
        }
        {
          name: 'GOOGLE_ISSUER_ID'
          value: ''   // set after deploy
        }
        {
          name: 'GOOGLE_CLASS_SUFFIX'
          value: 'ryetri_membership'
        }
        {
          name: 'GOOGLE_SERVICE_ACCOUNT_JSON'
          value: ''   // base64-encoded JSON – set after deploy
        }
        {
          name: 'LOGO_FILENAME'
          value: 'logo.png'
        }
      ]
    }
  }
}

// ---- Key Vault (optional – for storing secrets) ---------------------------

resource keyVault 'Microsoft.KeyVault/vaults@2023-02-01' = {
  name: keyVaultName
  location: location
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 90
  }
}

// Grant the Function App's managed identity the Key Vault Secrets User role
resource kvRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, functionApp.id, 'Key Vault Secrets User')
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      '4633458b-17de-408a-b874-0445c86b69e6'  // Key Vault Secrets User
    )
    principalId: functionApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// ---- Outputs --------------------------------------------------------------

output functionAppName string = functionApp.name
output functionAppUrl string = 'https://${functionApp.properties.defaultHostName}'
output storageAccountName string = storageAccount.name
output keyVaultName string = keyVault.name
