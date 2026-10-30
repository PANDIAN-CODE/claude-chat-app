# Azure Deployment Guide

This project deploys to **Azure Container Apps**, with secrets in **Key Vault** and
telemetry in **Application Insights**. Images are built by GitHub Actions and pushed to
**GitHub Container Registry (GHCR)** — no Azure Container Registry needed.

Deployment runs automatically via `.github/workflows/deploy.yml` on every push to `main`.
Infrastructure is defined in `infra/main.bicep`.

## One-time setup

Some of these steps require **Owner/Contributor on an Azure subscription or resource
group, plus permission to create an Azure AD App Registration** (Application
Administrator role or similar). If you don't have these rights, hand this section to
your Azure/IT admin — everything after "One-time setup" is self-service once it's done.

### 1. Create a resource group (needs Contributor on a subscription)

```bash
az group create --name claudechat-rg --location eastus
```

### 2. Set up OIDC federated login for GitHub Actions (needs Azure AD admin rights)

This lets GitHub Actions deploy to Azure without storing any password/secret.

```bash
# Create an app registration + service principal
az ad app create --display-name "claudechat-github-deploy"
APP_ID=$(az ad app list --display-name "claudechat-github-deploy" --query "[0].appId" -o tsv)
az ad sp create --id $APP_ID

# Grant it Contributor on the resource group
az role assignment create \
  --assignee $APP_ID \
  --role Contributor \
  --scope /subscriptions/<SUBSCRIPTION_ID>/resourceGroups/claudechat-rg

# Also grant it rights to assign the Key Vault Secrets User role (needed by the Bicep template)
az role assignment create \
  --assignee $APP_ID \
  --role "User Access Administrator" \
  --scope /subscriptions/<SUBSCRIPTION_ID>/resourceGroups/claudechat-rg

# Trust GitHub Actions to request tokens for this app (replace with your repo)
az ad app federated-credential create \
  --id $APP_ID \
  --parameters '{
    "name": "github-main-branch",
    "issuer": "https://token.actions.githubusercontent.com",
    "subject": "repo:<your-github-org>/<your-repo>:ref:refs/heads/main",
    "audiences": ["api://AzureADTokenExchange"]
  }'
```

Note the `appId` (this is `AZURE_CLIENT_ID`), your `tenantId` (`az account show --query
tenantId`), and your `subscriptionId` (`az account show --query id`).

### 3. Add GitHub repository secrets

In your GitHub repo → **Settings → Secrets and variables → Actions**, add:

| Secret | Value |
|---|---|
| `AZURE_CLIENT_ID` | the `appId` from step 2 |
| `AZURE_TENANT_ID` | your Azure AD tenant ID |
| `AZURE_SUBSCRIPTION_ID` | your subscription ID |
| `AZURE_RESOURCE_GROUP` | `claudechat-rg` (or whatever you named it) |
| `ANTHROPIC_API_KEY` | your real Anthropic API key |
| `JWT_SECRET` | a long random string (e.g. `python -c "import secrets; print(secrets.token_hex(32))"`) |

### 4. Make the GHCR packages public (no Azure admin needed)

The first deploy will fail to pull images if your GitHub Container Registry packages
are private, since Container Apps has no registry credentials configured. Easiest fix:
after the first successful `build-and-push` job, go to your GitHub profile/org →
**Packages** → select `claude-chat-backend` and `claude-chat-frontend` → **Package
settings** → change visibility to **Public**.

(Alternative if you must keep them private: add a Personal Access Token as a Container
Apps registry credential in `infra/main.bicep` — ask your admin, since this also touches
the resource's configuration.)

## Everyday deployment (no admin needed, once the above is done)

Just push to `main`:

```bash
git push origin main
```

GitHub Actions will:
1. Run backend tests (`pytest`) and build the frontend
2. Build and push both Docker images to GHCR
3. Deploy/update the Bicep stack in Azure (Key Vault secrets, Container Apps, Log
   Analytics, Application Insights)

Check the deployment output for the frontend's public URL, or run:

```bash
az containerapp show --name claudechat-frontend --resource-group claudechat-rg \
  --query properties.configuration.ingress.fqdn -o tsv
```

## Local testing with Docker Compose

Before touching Azure at all, you can run the whole stack locally with Docker:

```bash
docker compose up --build
```

Then open **http://localhost:8080**. This uses the same Dockerfiles that CI builds, so
if it works here, it will work in Azure too (same images, different environment
variables).

## Monitoring

Application Insights is wired into the backend automatically whenever
`APPLICATIONINSIGHTS_CONNECTION_STRING` is set (which the Bicep template does for you).
View live requests, exceptions, and dependency calls in the Azure Portal under your
`claudechat-insights` resource → **Live metrics** / **Transaction search**.
