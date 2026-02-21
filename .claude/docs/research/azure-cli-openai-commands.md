# Azure CLI Commands for Azure OpenAI Service

## Overview

This document contains Azure CLI commands for managing Azure OpenAI Service resources, including listing resources, retrieving API keys, endpoint URLs, and deployed models.

## Prerequisites

### Required Azure CLI Extension

```bash
# Install or update the cognitiveservices extension
az extension add --name cognitiveservices
az extension update --name cognitiveservices
```

### Authentication

```bash
# Login to Azure
az login

# Set specific subscription (if you have multiple)
az account set --subscription <subscription-id-or-name>
```

### Required Permissions

- **Microsoft.CognitiveServices/accounts/read** - To list and view resources
- **Microsoft.CognitiveServices/accounts/listKeys/action** - To retrieve API keys
- **Microsoft.CognitiveServices/accounts/deployments/read** - To list deployments
- **Owner, Contributor, or Cognitive Services Contributor role** - Full access

---

## 1. List Azure OpenAI Resources

### List all OpenAI resources in a subscription

```bash
az cognitiveservices account list \
  --resource-type "Microsoft.CognitiveServices/accounts" \
  --query "[?kind=='OpenAI'].{name:name, resourceGroup:resourceGroup, location:location, endpoint:properties.endpoint}" \
  -o json
```

### List OpenAI resources in a specific resource group

```bash
az cognitiveservices account list \
  --resource-group <your-resource-group> \
  --query "[?kind=='OpenAI']" \
  -o json
```

### Example Output

```json
[
  {
    "name": "my-openai-resource",
    "resourceGroup": "my-rg",
    "location": "eastus",
    "endpoint": "https://my-openai-resource.openai.azure.com/"
  }
]
```

---

## 2. Get API Keys

### List all keys for an OpenAI resource

```bash
az cognitiveservices account keys list \
  --name <your-openai-resource-name> \
  --resource-group <your-resource-group> \
  -o json
```

### Get only the first key

```bash
az cognitiveservices account keys list \
  --name <your-openai-resource-name> \
  --resource-group <your-resource-group> \
  --query "key1" \
  -o tsv
```

### Example Output

```json
{
  "key1": "abcdefghijklmnopqrstuvwxyz1234567890",
  "key2": "0987654321zyxwvutsrqponmlkjihgfedcba"
}
```

---

## 3. Get Endpoint URL

### Get endpoint URL

```bash
az cognitiveservices account show \
  --name <your-openai-resource-name> \
  --resource-group <your-resource-group> \
  --query "properties.endpoint" \
  -o tsv
```

### Get full resource details (including endpoint)

```bash
az cognitiveservices account show \
  --name <your-openai-resource-name> \
  --resource-group <your-resource-group> \
  -o json
```

### Example Output

```
https://my-openai-resource.openai.azure.com/
```

---

## 4. Get Resource Name

### From resource list

```bash
az cognitiveservices account list \
  --resource-group <your-resource-group> \
  --query "[?kind=='OpenAI'].name" \
  -o tsv
```

### From specific resource

```bash
az cognitiveservices account show \
  --name <your-openai-resource-name> \
  --resource-group <your-resource-group> \
  --query "name" \
  -o tsv
```

---

## 5. List Deployed Models

### List all deployments

```bash
az cognitiveservices account deployment list \
  --name <your-openai-resource-name> \
  --resource-group <your-resource-group> \
  -o json
```

### List deployments with specific fields

```bash
az cognitiveservices account deployment list \
  --name <your-openai-resource-name> \
  --resource-group <your-resource-group> \
  --query "[].{name:name, model:properties.model.name, version:properties.model.version, capacity:properties.scale.capacity}" \
  -o table
```

### Example Output

```json
[
  {
    "name": "gpt-4-deployment",
    "properties": {
      "model": {
        "name": "gpt-4",
        "version": "0613"
      },
      "scale": {
        "capacity": 120
      }
    }
  },
  {
    "name": "gpt-35-turbo-deployment",
    "properties": {
      "model": {
        "name": "gpt-35-turbo",
        "version": "0613"
      },
      "scale": {
        "capacity": 180
      }
    }
  }
]
```

### Table format output

```
Name                    Model       Version    Capacity
----------------------  ----------  ---------  ----------
gpt-4-deployment        gpt-4       0613       120
gpt-35-turbo-deployment gpt-35-turbo 0613       180
```

---

## 6. Combined Script Example

### Script to get all OpenAI information

```bash
#!/bin/bash
RESOURCE_GROUP="<your-resource-group>"
OPENAI_NAME="<your-openai-resource-name>"

echo "=== Azure OpenAI Resource Information ==="
echo ""

echo "1. Endpoint URL:"
az cognitiveservices account show \
  --name $OPENAI_NAME \
  --resource-group $RESOURCE_GROUP \
  --query "properties.endpoint" \
  -o tsv

echo ""
echo "2. API Key (Key1):"
az cognitiveservices account keys list \
  --name $OPENAI_NAME \
  --resource-group $RESOURCE_GROUP \
  --query "key1" \
  -o tsv

echo ""
echo "3. Deployed Models:"
az cognitiveservices account deployment list \
  --name $OPENAI_NAME \
  --resource-group $RESOURCE_GROUP \
  --query "[].{Deployment:name, Model:properties.model.name, Version:properties.model.version}" \
  -o table
```

---

## 7. Quick Reference

| Task | Command |
|------|---------|
| List resources | `az cognitiveservices account list --query "[?kind=='OpenAI']"` |
| Get endpoint | `az cognitiveservices account show -n <name> -g <rg> --query "properties.endpoint" -o tsv` |
| Get API keys | `az cognitiveservices account keys list -n <name> -g <rg>` |
| List deployments | `az cognitiveservices account deployment list -n <name> -g <rg>` |

---

## 8. Common Output Formats

| Format | Flag | Description |
|--------|------|-------------|
| JSON | `-o json` | Machine-readable JSON |
| Table | `-o table` | Human-readable table |
| TSV | `-o tsv` | Tab-separated values (good for parsing) |
| YAML | `-o yaml` | YAML format |

---

## Sources

- [Azure CLI - az cognitiveservices](https://docs.microsoft.com/cli/azure/cognitiveservices)
- [Azure OpenAI Service Documentation](https://docs.microsoft.com/azure/cognitive-services/openai/)
- [Azure RBAC roles for Cognitive Services](https://docs.microsoft.com/azure/role-based-access-control/built-in-roles#cognitive-services-contributor)

