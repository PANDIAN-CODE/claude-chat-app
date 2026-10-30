@description('Azure region for all resources')
param location string = resourceGroup().location

@description('Short name used as a prefix for all resources, e.g. "claudechat"')
param appName string = 'claudechat'

@description('Container image for the backend, e.g. ghcr.io/you/claude-chat-backend:latest')
param backendImage string

@description('Container image for the frontend, e.g. ghcr.io/you/claude-chat-frontend:latest')
param frontendImage string

@secure()
@description('Anthropic API key, stored in Key Vault - never put the real value in source control')
param anthropicApiKey string

@secure()
@description('JWT signing secret, stored in Key Vault')
param jwtSecret string

param claudeModel string = 'claude-haiku-5-5'

var logAnalyticsName = '${appName}-logs'
var appInsightsName = '${appName}-insights'
var keyVaultName = '${take(appName, 6)}kv${uniqueString(resourceGroup().id)}'
var envName = '${appName}-env'
var backendAppName = '${appName}-backend'
var frontendAppName = '${appName}-frontend'

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logAnalyticsName
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
  }
}

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: keyVaultName
  location: location
  properties: {
    sku: { family: 'A', name: 'standard' }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true
  }
}

resource anthropicSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'anthropic-api-key'
  properties: { value: anthropicApiKey }
}

resource jwtSecretResource 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'jwt-secret'
  properties: { value: jwtSecret }
}

resource containerAppEnv 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: envName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

resource backendApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: backendAppName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    managedEnvironmentId: containerAppEnv.id
    configuration: {
      ingress: {
        external: false
        targetPort: 8000
        transport: 'http'
      }
      secrets: [
        {
          name: 'anthropic-api-key'
          keyVaultUrl: anthropicSecret.properties.secretUri
          identity: 'system'
        }
        {
          name: 'jwt-secret'
          keyVaultUrl: jwtSecretResource.properties.secretUri
          identity: 'system'
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'backend'
          image: backendImage
          env: [
            { name: 'ANTHROPIC_API_KEY', secretRef: 'anthropic-api-key' }
            { name: 'JWT_SECRET', secretRef: 'jwt-secret' }
            { name: 'CLAUDE_MODEL', value: claudeModel }
            { name: 'DATABASE_URL', value: 'sqlite:////data/app.db' }
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsights.properties.ConnectionString }
          ]
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 2
      }
    }
  }
}

resource frontendApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: frontendAppName
  location: location
  properties: {
    managedEnvironmentId: containerAppEnv.id
    configuration: {
      ingress: {
        external: true
        targetPort: 80
        transport: 'http'
      }
    }
    template: {
      containers: [
        {
          name: 'frontend'
          image: frontendImage
          env: [
            { name: 'BACKEND_URL', value: '${backendApp.properties.configuration.ingress.fqdn}' }
          ]
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 2
      }
    }
  }
}

resource kvSecretsUserRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, backendApp.id, 'Key Vault Secrets User')
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      '4633458b-17de-408a-b874-0445c86b69e6'
    )
    principalId: backendApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

output frontendUrl string = 'https://${frontendApp.properties.configuration.ingress.fqdn}'
output backendInternalUrl string = backendApp.properties.configuration.ingress.fqdn
output keyVaultName string = keyVault.name
