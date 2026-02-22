# Weave Azure Deployment Guide

## Overview

This guide covers deploying SIT Copilot with WandB Weave observability to Azure Container Apps.

## Deployment Modes

### Development: Weave Local

**Use for:** Development, testing, demos

- Weave runs embedded in the container
- UI served at http://localhost:8080
- No external dependencies
- Zero network latency

**Configuration:**
```bash
WEAVE_ENABLED=true
WEAVE_MODE=local
WEAVE_PROJECT=sit-copilot-demo
```

### Production: Weave Cloud

**Use for:** Production environments

- Data sent to weave.wandb.ai
- Centralized observability across replicas
- Historical data retention
- Team collaboration

**Configuration:**
```bash
WEAVE_ENABLED=true
WEAVE_MODE=cloud
WEAVE_PROJECT=sit-copilot-prod
WEAVE_API_KEY=<from-key-vault>
```

## Prerequisites

### 1. WandB Account

1. Sign up at https://wandb.ai
2. Create a project: `sit-copilot-prod`
3. Generate API key: https://wandb.ai/settings

### 2. Azure Resources

- Key Vault: For storing API key
- Container Apps: For running the app
- Managed Identity: For Key Vault access

## Azure Key Vault Setup

### Create Key Vault

```bash
# Resource group
az group create \
  --name sit-copilot-rg \
  --location japaneast

# Key Vault
az keyvault create \
  --name sit-copilot-kv \
  --resource-group sit-copilot-rg \
  --location japaneast \
  --enable-rbac-authorization true
```

### Store Weave API Key

```bash
# Store API key as secret
az keyvault secret set \
  --vault-name sit-copilot-kv \
  --name weave-api-key \
  --value "your-wandb-api-key-here"

# Verify
az keyvault secret show \
  --vault-name sit-copilot-kv \
  --name weave-api-key
```

## Managed Identity Setup

### Create User-Assigned Identity

```bash
# Create identity
az identity create \
  --name sit-copilot-identity \
  --resource-group sit-copilot-rg

# Get principal ID
PRINCIPAL_ID=$(az identity show \
  --name sit-copilot-identity \
  --resource-group sit-copilot-rg \
  --query principalId -o tsv)

# Get resource ID
IDENTITY_RESOURCE_ID=$(az identity show \
  --name sit-copilot-identity \
  --resource-group sit-copilot-rg \
  --query id -o tsv)
```

### Grant Key Vault Access

```bash
# Get Key Vault resource ID
KV_RESOURCE_ID=$(az keyvault show \
  --name sit-copilot-kv \
  --resource-group sit-copilot-rg \
  --query id -o tsv)

# Grant secret access
az role assignment create \
  --assignee $PRINCIPAL_ID \
  --role "Key Vault Secrets User" \
  --scope $KV_RESOURCE_ID
```

## Container Apps Configuration

### Create Container App Environment

```bash
az containerapp env create \
  --name sit-copilot-env \
  --resource-group sit-copilot-rg \
  --location japaneast
```

### Deploy with Weave Cloud

```bash
az containerapp create \
  --name sit-copilot-api \
  --resource-group sit-copilot-rg \
  --environment sit-copilot-env \
  --image <your-registry>/sit-copilot:latest \
  --target-port 8000 \
  --ingress external \
  --user-assigned-identity $IDENTITY_RESOURCE_ID \
  --secrets weave-api-key-secret=secretref:weave-api-key \
  --env-vars \
    WEAVE_ENABLED=true \
    WEAVE_MODE=cloud \
    WEAVE_PROJECT=sit-copilot-prod \
    WEAVE_API_KEY=secretref:weave-api-key-secret \
    WEAVE_CAPTURE_IMAGES=false \
    WEAVE_CAPTURE_PROMPTS=false \
    WEAVE_CAPTURE_RESPONSES=true
```

**Important parameters:**

| Parameter | Value | Purpose |
|-----------|-------|---------|
| `WEAVE_ENABLED` | `true` | Enable Weave |
| `WEAVE_MODE` | `cloud` | Use Weave Cloud |
| `WEAVE_PROJECT` | `sit-copilot-prod` | Project name in Weave |
| `WEAVE_API_KEY` | `secretref:...` | API key from Key Vault |
| `WEAVE_CAPTURE_IMAGES` | `false` | Privacy: no images in production |
| `WEAVE_CAPTURE_PROMPTS` | `false` | Privacy: no user prompts |
| `WEAVE_CAPTURE_RESPONSES` | `true` | Quality monitoring |

## Deployment Settings Reference

### Development Environment

```yaml
env:
  - name: WEAVE_ENABLED
    value: "true"
  - name: WEAVE_MODE
    value: "local"
  - name: WEAVE_PROJECT
    value: "sit-copilot-dev"
  - name: WEAVE_CAPTURE_IMAGES
    value: "true"
  - name: WEAVE_CAPTURE_PROMPTS
    value: "true"
  - name: WEAVE_CAPTURE_RESPONSES
    value: "true"
```

### Demo Environment

```yaml
env:
  - name: WEAVE_ENABLED
    value: "true"
  - name: WEAVE_MODE
    value: "cloud"
  - name: WEAVE_PROJECT
    value: "sit-copilot-demo"
  - name: WEAVE_API_KEY
    secretRef: weave-api-key
  - name: WEAVE_CAPTURE_IMAGES
    value: "true"
  - name: WEAVE_CAPTURE_PROMPTS
    value: "true"
  - name: WEAVE_CAPTURE_RESPONSES
    value: "true"
```

### Production Environment

```yaml
env:
  - name: WEAVE_ENABLED
    value: "true"
  - name: WEAVE_MODE
    value: "cloud"
  - name: WEAVE_PROJECT
    value: "sit-copilot-prod"
  - name: WEAVE_API_KEY
    secretRef: weave-api-key
  - name: WEAVE_CAPTURE_IMAGES
    value: "false"
  - name: WEAVE_CAPTURE_PROMPTS
    value: "false"
  - name: WEAVE_CAPTURE_RESPONSES
    value: "true"
  - name: WEAVE_QUEUE_MAXSIZE
    value: "2000"
  - name: WEAVE_WORKER_COUNT
    value: "4"
```

## Performance Tuning

### High-Traffic Scenarios

For production with high request volume:

```yaml
env:
  - name: WEAVE_QUEUE_MAXSIZE
    value: "5000"  # Larger queue
  - name: WEAVE_WORKER_COUNT
    value: "8"     # More workers
  - name: WEAVE_TIMEOUT_MS
    value: "3000"  # Longer timeout
  - name: WEAVE_SAMPLE_RATE
    value: "0.1"   # Sample 10% of requests
```

### Low-Latency Requirements

For minimal impact on response times:

```yaml
env:
  - name: WEAVE_QUEUE_MAXSIZE
    value: "500"   # Small queue
  - name: WEAVE_WORKER_COUNT
    value: "2"     # Few workers
  - name: WEAVE_TIMEOUT_MS
    value: "1000"  # Short timeout
  - name: WEAVE_SAMPLE_RATE
    value: "0.01"  # Sample 1% of requests
```

## Monitoring

### Health Checks

Weave failures don't affect app health (by design), but monitor:

```bash
# Check Weave initialization in logs
az containerapp logs show \
  --name sit-copilot-api \
  --resource-group sit-copilot-rg \
  --follow \
  | grep "Weave"
```

Expected logs:
```
INFO: Weave initialized: project=sit-copilot-prod
INFO: WeaveDispatcher started: 4 workers, queue maxsize=2000
```

### Alerting

Alert on:
- `Weave initialization failed` - Weave not working
- `Weave queue full` - Observability bottleneck
- `Weave observation timeout` - Slow Weave response

## Data Retention

### Weave Cloud Retention

- **Free tier**: 30 days
- **Paid tier**: Custom retention

### Data Export

```python
# Export traces for analysis
import weave

weave.init(project="sit-copilot-prod")

# Query traces
traces = weave.ops.table_query("qa_turn", where="session_id = 'lec_123'")
```

## Troubleshooting

### Weave Initialization Failed

**Symptoms:**
- Log: `Weave initialization failed: ...`
- App works but no traces

**Solutions:**
1. Verify `WEAVE_API_KEY` is correct
2. Check network connectivity to weave.wandb.ai
3. Verify project exists in WandB

### Queue Full Warnings

**Symptoms:**
- Log: `Weave queue full, dropping observation`
- Missing traces

**Solutions:**
1. Increase `WEAVE_QUEUE_MAXSIZE`
2. Increase `WEAVE_WORKER_COUNT`
3. Reduce `WEAVE_SAMPLE_RATE`

### High Memory Usage

**Symptoms:**
- Container memory limits exceeded
- OOMKilled

**Solutions:**
1. Reduce `WEAVE_CAPTURE_IMAGES=false`
2. Reduce `WEAVE_QUEUE_MAXSIZE`
3. Reduce `WEAVE_SAMPLE_RATE`

## Security Checklist

- [ ] API key stored in Key Vault
- [ ] Managed Identity has Key Vault access
- [ ] `WEAVE_CAPTURE_IMAGES=false` in production
- [ ] `WEAVE_CAPTURE_PROMPTS=false` in production
- [ ] Network policies allow weave.wandb.ai
- [ ] Data retention policy configured
- [ ] Access controls on WandB project

## Cost Considerations

### Weave Cloud Pricing

- **Free tier**: Limited traces per month
- **Team**: $50/month per user
- **Enterprise**: Custom pricing

### Azure Costs

- Key Vault: ~$0.03/10,000 operations
- Container Apps: CPU/memory allocation
- Egress: Data transfer to Weave

**Optimization:**
- Use sampling in production
- Disable image capture
- Consider local mode for non-critical envs
