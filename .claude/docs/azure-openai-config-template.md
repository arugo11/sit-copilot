# Azure OpenAI Configuration Template

## Environment Variables (.env.azure.generated)

### Required Settings

```bash
# Azure OpenAI API Key
# Get from: Azure Portal → Azure OpenAI resource → Keys and Endpoints
AZURE_OPENAI_API_KEY=your-api-key-here

# Azure OpenAI Endpoint
# Format depends on resource type:
# - Standard OpenAI: https://{resource-name}.openai.azure.com/
# - Cognitive Services: https://{region}.api.cognitive.microsoft.com/
AZURE_OPENAI_ENDPOINT=https://japaneast.api.cognitive.microsoft.com

# Azure OpenAI Account Name
# This is the resource name (e.g., aoai-sitc-02210594)
AZURE_OPENAI_ACCOUNT_NAME=your-resource-name

# Azure OpenAI Model Deployment Name
# Must match the deployment name in Azure Portal
# Common deployments: gpt-5-nano, gpt-4o
AZURE_OPENAI_MODEL=gpt-5-nano

# Azure OpenAI API Version
# Required for Cognitive Services endpoints
# Recommended: 2024-05-01-preview
AZURE_OPENAI_API_VERSION=2024-05-01-preview

# Enable Azure OpenAI
AZURE_OPENAI_ENABLED=true
```

### Optional Settings (Azure Search)

```bash
# Azure Search (optional, for enhanced retrieval)
AZURE_SEARCH_ENABLED=false
AZURE_SEARCH_API_KEY=
AZURE_SEARCH_ENDPOINT=
AZURE_SEARCH_INDEX_NAME=lecture_index
```

## Configuration Examples

### Example 1: Cognitive Services (Japan East)

```bash
AZURE_OPENAI_API_KEY=<SET_IN_KEY_VAULT>
AZURE_OPENAI_ENDPOINT=https://aoai-sitc-02210594.cognitiveservices.azure.com
AZURE_OPENAI_ACCOUNT_NAME=aoai-sitc-02210594
AZURE_OPENAI_MODEL=gpt-5-nano
AZURE_OPENAI_API_VERSION=2024-05-01-preview
AZURE_OPENAI_ENABLED=true
```

### Example 2: Standard OpenAI (East US)

```bash
AZURE_OPENAI_API_KEY=your-key-here
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_ACCOUNT_NAME=your-resource
AZURE_OPENAI_MODEL=gpt-4o
AZURE_OPENAI_API_VERSION=2024-10-21
AZURE_OPENAI_ENABLED=true
```

## How to Get Configuration Values

### Method 1: Azure CLI

```bash
# Login
az login

# List OpenAI resources
az cognitiveservices account list --query "[?kind=='OpenAI']" --output table

# Get API keys
az cognitiveservices account keys list \
  --name "your-resource-name" \
  --resource-group "your-resource-group" --output table

# Get endpoint
az cognitiveservices account show \
  --name "your-resource-name" \
  --resource-group "your-resource-group" \
  --query "properties.endpoint" --output tsv

# List deployments
az cognitiveservices account deployment list \
  --name "your-resource-name" \
  --resource-group "your-resource-group" --output table
```

### Method 2: Azure Portal

1. Navigate to https://portal.azure.com
2. Search for "Azure OpenAI"
3. Open your resource
4. Go to "Keys and Endpoints" in the left menu
5. Copy:
   - API key (key1 or key2)
   - Endpoint URL
   - Resource name (from endpoint or properties)

## API Version Compatibility

| API Version | Endpoint Type | Status |
|-------------|----------------|--------|
| `2024-02-15-preview` | Cognitive Services | ✅ Working |
| `2024-10-21` | Cognitive Services | ❌ DeploymentNotFound |
| `2024-10-21` | Standard OpenAI | ✅ Working |
| `2024-02-15-preview` | Standard OpenAI | ⚠️ May work |

**Recommendation**: Use `2024-02-15-preview` for Cognitive Services endpoints.

## Troubleshooting

### Error: "DeploymentNotFound"

**Cause**: API version incompatible with endpoint type

**Solution**:
- For Cognitive Services: Use `AZURE_OPENAI_API_VERSION=2024-02-15-preview`
- For standard OpenAI: Use `AZURE_OPENAI_API_VERSION=2024-10-21`

### Error: "azure_openai_answer_network_error"

**Cause**: Network connectivity or endpoint URL incorrect

**Solution**:
1. Verify endpoint URL matches your resource type
2. Check API key is valid and not expired
3. Ensure deployment name matches exactly (case-sensitive)

### Error: "The subscription is not registered to use namespace 'Microsoft.CognitiveServices'"

**Cause**: Resource provider not registered in subscription

**Solution**:
```bash
az provider register --namespace Microsoft.CognitiveServices
```

## Security Best Practices

1. **Never commit `.env.azure.generated` to git**
2. **Use different API keys for dev/staging/production**
3. **Rotate keys regularly** (Azure Portal → Keys → Regenerate)
4. **Monitor usage** to detect unauthorized access
5. **Use Key Vault** for production deployments

## Related Files

- Configuration schema: `app/core/config.py`
- Dependency injection: `app/api/v4/lecture_qa.py`
- Services using Azure OpenAI:
  - `app/services/lecture_answerer_service.py`
  - `app/services/lecture_verifier_service.py`
  - `app/services/lecture_followup_service.py`
- Design documentation: `.claude/docs/DESIGN.md`
- Setup guide: `AZURE_SETUP_GUIDE.md`

---
**Last Updated**: 2026-02-22
**Status**: ✅ Tested and working with gpt-5-nano
