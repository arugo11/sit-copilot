# WandB Weave - Azure Deployment Research

> Research conducted: 2026-02-23  
> Researcher: gemini-explore agent  
> Status: Knowledge-based synthesis

---

## Executive Summary

WandB WeaveはAzure Container Instances (ACI)、Azure Kubernetes Service (AKS)、Azure App Service、Azure Virtual Machinesにデプロイ可能です。SIT CopilotのFastAPIアプリケーションには、開発環境ではWeave Local、本番環境ではWeave Cloudの使用が推奨されます。

---

## 1. Weave Local Deployment Options in Azure

### 1.1 Azure Container Instances (ACI) - Recommended for Development

**Pros:**
- 最も簡単なデプロイメント
- サーバーレス（VM管理不要）
- 従量課金
- 快速な起動時間

**Configuration:**
```yaml
# weave-local-container.yaml
apiVersion: 2019-12-01
location: eastus
name: weave-local
properties:
  image: wandb/weave:latest
  ports:
    - port: 8080
  resources:
    requests:
      cpu: 1.0
      memoryInGB: 2.0
  environmentVariables:
    - name: WEAVE_MODE
      value: local
    - name: WEAVE_DATA_DIR
      value: /weave-data
  volumeMounts:
    - name: weave-data
      mountPath: /weave-data
volumes:
  - name: weave-data
    azureFile:
      shareName: weave-data
      storageAccountName: mystorageaccount
type: Microsoft.ContainerInstance/containerGroups
```

**Deploy Command:**
```bash
az container create \
  --resource-group sit-copilot-rg \
  --file weave-local-container.yaml
```

### 1.2 Azure Kubernetes Service (AKS) - Recommended for Production

**Pros:**
- スケーラビリティ
- 高可用性
- 既存のKubernetesワークロードと統合

**Configuration:**
```yaml
# weave-local-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: weave-local
spec:
  replicas: 1
  selector:
    matchLabels:
      app: weave-local
  template:
    metadata:
      labels:
        app: weave-local
    spec:
      containers:
      - name: weave-local
        image: wandb/weave:latest
        ports:
        - containerPort: 8080
        env:
        - name: WEAVE_MODE
          value: "local"
        resources:
          requests:
            cpu: 500m
            memory: 512Mi
          limits:
            cpu: 1000m
            memory: 1Gi
        volumeMounts:
        - name: weave-data
          mountPath: /weave-data
      volumes:
      - name: weave-data
        persistentVolumeClaim:
          claimName: weave-data-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: weave-local
spec:
  selector:
    app: weave-local
  ports:
  - port: 80
    targetPort: 8080
  type: LoadBalancer
```

**Deploy Command:**
```bash
kubectl apply -f weave-local-deployment.yaml
```

### 1.3 Azure App Service (Container)

**Pros:**
- PaaS (管理不要)
- 組み込みのスケーリング
- デプロイメントスロット

**Configuration:**
```bash
az webapp create \
  --resource-group sit-copilot-rg \
  --name weave-local-app \
  --plan weave-app-service-plan \
  --deployment-container-image-name wandb/weave:latest

# Configure settings
az webapp config appsettings set \
  --name weave-local-app \
  --resource-group sit-copilot-rg \
  --settings WEAVE_MODE=local
```

### 1.4 Azure Virtual Machine

**Pros:**
- 完全な制御
- 既存のVMインフラを活用

**Setup:**
```bash
# On Azure VM (Ubuntu)
sudo apt-get update
sudo apt-get install -y docker.io

# Run Weave Local as container
docker run -d \
  --name weave-local \
  -p 8080:8080 \
  -v /opt/weave-data:/weave-data \
  -e WEAVE_MODE=local \
  wandb/weave:latest
```

---

## 2. Environment Variable and Secret Management

### 2.1 Azure Key Vault Integration

**Best Practice:** Weave APIキーをAzure Key Vaultに保存

```python
# azure-keyvault-weave-integration.py
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

def get_weave_api_key() -> str:
    """Retrieve Weave API key from Azure Key Vault."""
    credential = DefaultAzureCredential()
    client = SecretClient(
        vault_url="https://sit-copilot-kv.vault.azure.net",
        credential=credential
    )
    
    secret = client.get_secret("weave-api-key")
    return secret.value

# Use in application
import os
os.environ["WANDB_API_KEY"] = get_weave_api_key()
```

**Store Secret:**
```bash
az keyvault secret set \
  --vault-name sit-copilot-kv \
  --name weave-api-key \
  --value "your-actual-api-key"
```

### 2.2 Managed Identity for Weave Cloud

**Configuration:**
```python
# app/services/weave_observer_service.py
from azure.identity import ManagedIdentityCredential

class AzureWeaveObserverService(WandBWeaveObserverService):
    """Weave observer with Azure Managed Identity."""
    
    def __init__(self):
        # Fetch API key from Key Vault using Managed Identity
        credential = ManagedIdentityCredential()
        # ... Key Vault access ...
        super().__init__(settings=settings)
```

**Assign Identity:**
```bash
# Assign Managed Identity to App Service/ACI/AKS
az identity create \
  --resource-group sit-copilot-rg \
  --name sit-copilot-identity

az keyvault set-policy \
  --name sit-copilot-kv \
  --object-id $(az identity show \
    --resource-group sit-copilot-rg \
    --name sit-copilot-identity \
    --query principalId -o tsv) \
  --secret-permissions get list
```

### 2.3 App Service Configuration

```bash
# Set environment variables
az webapp config appsettings set \
  --name sit-copilot-api \
  --resource-group sit-copilot-rg \
  --settings \
    WEAVE_ENABLED=true \
    WEAVE_MODE=cloud \
    WEAVE_PROJECT=sit-copilot \
    @Microsoft.KeyVault(SecretUri=https://sit-copilot-kv.vault.azure.net/secrets/weave-api-key/)
```

### 2.4 Container Instances Configuration

```bash
az container create \
  --resource-group sit-copilot-rg \
  --name sit-copilot-api \
  --image yourregistry.azurecr.io/sit-copilot:latest \
  --secure-environment-variables \
    WEAVE_ENABLED=true \
    WEAVE_MODE=cloud \
    WANDB_API_KEY=$WEAVE_API_KEY
```

---

## 3. Networking Considerations

### 3.1 VNET Integration

**Scenario:** Weave Local + Application in same VNET

```bash
# Create VNET
az network vnet create \
  --resource-group sit-copilot-rg \
  --name sit-copilot-vnet \
  --address-prefixes 10.0.0.0/16

# Create subnet for Weave
az network vnet subnet create \
  --resource-group sit-copilot-rg \
  --vnet-name sit-copilot-vnet \
  --name weave-subnet \
  --address-prefixes 10.0.1.0/24

# Deploy Weave in VNET (ACI)
az container create \
  --resource-group sit-copilot-rg \
  --name weave-local \
  --vnet sit-copilot-vnet \
  --subnet weave-subnet \
  # ... other config ...
```

### 3.2 Private Endpoints for Weave Cloud

**For production with data residency requirements:**

```bash
# Create Private Endpoint for Weave Cloud (if available)
az network private-endpoint create \
  --resource-group sit-copilot-rg \
  --name weave-cloud-pe \
  --vnet-name sit-copilot-vnet \
  --subnet weave-subnet \
  --connection-name weave-cloud-connection \
  --private-connection-resource-id /subscriptions/.../providers/Microsoft.Network/privateLinkServices/weave-cloud \
  --group-id weave
```

### 3.3 Firewall Rules

**If using Azure Firewall:**

```azurecli
# Allow Weave Cloud endpoints
az network firewall network-rule create \
  --firewall-name sit-copilot-fw \
  --resource-group sit-copilot-rg \
  --name weave-cloud-rule \
  --source-addresses 10.0.0.0/16 \
  --destination-addresses api.wandb.ai \
  --destination-ports 443 \
  --protocols TCP
```

### 3.4 NSG Configuration

```bash
# Network Security Group for Weave container
az network nsg rule create \
  --resource-group sit-copilot-rg \
  --nsg-name weave-nsg \
  --name allow-weave-ui \
  --access Allow \
  --direction Inbound \
  --protocol Tcp \
  --destination-port-ranges 8080 \
  --source-address-prefixes "*"
```

---

## 4. Monitoring and Logging Integration

### 4.1 Azure Monitor Integration

```python
# app/services/weave_azure_monitor_service.py
from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry import trace

class WeaveWithAzureMonitor:
    """Integrate Weave traces with Azure Monitor."""
    
    def __init__(self):
        # Initialize Azure Monitor
        configure_azure_monitor(
            connection_string=os.environ["APPLICATIONINSIGHTS_CONNECTION_STRING"]
        )
        
        # Initialize Weave
        weave.init(project_name="sit-copilot")
        
    @weave.op()
    async def tracked_operation(self, data: dict):
        # This trace appears in both Weave AND Azure Monitor
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("operation"):
            result = await process(data)
            return result
```

### 4.2 Application Insights Integration

```python
from azure.applicationinsights import ApplicationInsights

# Send Weave traces to Application Insights
@app.middleware("http")
async def dual_tracking_middleware(request: Request, call_next):
    trace_id = str(uuid.uuid4())
    
    # Weave tracking
    with weave.attributes_context({"trace_id": trace_id}):
        response = await call_next(request)
    
    # Application Insights tracking
    telemetry_client.track_trace({
        "name": f"HTTP {request.method} {request.url.path}",
        "properties": {
            "trace_id": trace_id,
            "status_code": response.status_code
        }
    })
    
    return response
```

### 4.3 Log Analytics Queries

```kusto
// Query Weave traces in Log Analytics
AppTraces
| where timestamp > ago(24h)
| where customDimensions.TraceType == "weave"
| project timestamp, operation_Name, customDimensions
| order by timestamp desc
```

---

## 5. Cost Optimization Strategies

### 5.1 Weave Local Cost Optimization

| Strategy | Savings | Notes |
|----------|---------|-------|
| **Use ACI for dev** | ~60-80% vs VM | Serverless, pay-per-use |
| **Scale to zero** | ~100% when idle | Only during dev hours |
| **Use existing AKS** | ~0 marginal | Share cluster resources |

### 5.2 Weave Cloud Cost Optimization

```python
# Sampling to reduce costs
class CostOptimizedWeaveObserver:
    """Weave observer with smart sampling."""
    
    def __init__(self, settings: WeaveSettings):
        self.sample_rate = settings.sample_rate
        self.high_value_threshold = settings.high_value_latency_ms
    
    @weave.op()
    async def track_qa_turn(self, question: str, **kwargs):
        # Always track slow operations (performance issues)
        if kwargs.get("latency_ms", 0) > self.high_value_threshold:
            return await self._do_track(question, **kwargs)
        
        # Sample normal operations
        if random.random() < self.sample_rate:
            return await self._do_track(question, **kwargs)
        
        return None  # Skip tracking
```

### 5.3 Reserved Instances for VM-based Deployment

```bash
# Purchase Reserved Instance for production
az reservation create \
  --reserved-resource-type VirtualMachines \
  --sku Standard_D2s_v3 \
  --location eastus \
  --capacity 1 \
  --billing-scope /subscriptions/... \
  --term P1Y  # 1-year term
```

---

## 6. Production Deployment Best Practices

### 6.1 Health Probes

```yaml
# For AKS/ACI deployment
livenessProbe:
  httpGet:
    path: /health
    port: 8080
  initialDelaySeconds: 30
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /ready
    port: 8080
  initialDelaySeconds: 10
  periodSeconds: 5
```

### 6.2 Resource Limits

```yaml
resources:
  requests:
    cpu: 500m      # Base allocation
    memory: 512Mi
  limits:
    cpu: 2000m     # Max during spikes
    memory: 2Gi
```

### 6.3 Auto-scaling

```yaml
# Horizontal Pod Autoscaler for AKS
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: sit-copilot-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: sit-copilot
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

### 6.4 Rolling Updates

```bash
# Zero-downtime deployment
kubectl set image deployment/sit-copilot \
  sit-copilot=yourregistry.azurecr.io/sit-copilot:v1.2.0

kubectl rollout status deployment/sit-copilot

# Rollback if needed
kubectl rollout undo deployment/sit-copilot
```

### 6.5 Blue-Green Deployment

```bash
# Deploy new version alongside old
kubectl apply -f sit-copilot-v2.yaml

# Switch traffic gradually
kubectl patch service sit-copilot-service \
  --type=json \
  -p='[{"op": "replace", "path": "/spec/selector/app", "value": "sit-copilot-v2"}]'
```

---

## 7. Decision Matrix: Weave Local vs Cloud for SIT Copilot

| Factor | Weave Local | Weave Cloud | Recommendation |
|--------|-------------|-------------|----------------|
| **Development** | ✅ Best choice | Overkill | **Local** |
| **Staging** | ✅ Good | ✅ Good | **Local** (cost) |
| **Production** | Limited | ✅ Best | **Cloud** |
| **Cost** | Free (infra only) | Usage-based | Local for dev |
| **Maintenance** | Self-managed | Managed | Cloud for prod |
| **Collaboration** | Limited | Full team | Cloud for prod |
| **Data Residency** | ✅ Full control | Varies | Local if strict |
| **Azure Integration** | Custom | Native | Cloud available |

---

## 8. Recommended Architecture for SIT Copilot

### 8.1 Development Environment

```
┌─────────────────────────────────────────┐
│  Developer Machine / Azure Dev Box       │
│                                          │
│  ┌────────────────────────────────────┐ │
│  │  SIT Copilot (FastAPI)             │ │
│  │  - Weave enabled: true             │ │
│  │  - Weave mode: local               │ │
│  │  - Data dir: ./weave-data          │ │
│  └────────────────────────────────────┘ │
│           │                              │
│           ▼                              │
│  ┌────────────────────────────────────┐ │
│  │  Weave Local (embedded)            │ │
│  │  - Local UI: http://localhost:8080 │ │
│  │  - Trace storage: ./weave-data     │ │
│  └────────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

### 8.2 Production Environment

```
┌─────────────────────────────────────────────────────────┐
│  Azure: East US                                         │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Azure Container Apps / AKS                      │  │
│  │                                                   │  │
│  │  ┌────────────────────────────────────────────┐ │  │
│  │  │  SIT Copilot Pods (xN)                      │ │  │
│  │  │  - WEAVE_ENABLED=true                       │ │  │
│  │  │  - WEAVE_MODE=cloud                         │ │  │
│  │  │  - WANDB_API_KEY (from Key Vault)          │ │  │
│  │  └────────────────────────────────────────────┘ │  │
│  │                       │                          │  │
│  │                       ▼                          │  │
│  │  ┌────────────────────────────────────────────┐ │  │
│  │  │  Azure Key Vault                           │ │  │
│  │  │  - weave-api-key (secret)                  │ │  │
│  │  └────────────────────────────────────────────┘ │  │
│  └──────────────────────────────────────────────────┘  │
│                         │                                 │
│                         ▼ (HTTPS)                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │  WandB Weave Cloud (api.wandb.ai)                │  │
│  │  - Project: sit-copilot                          │  │
│  │  - Team collaboration                            │  │
│  │  - Managed storage & retention                   │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Azure Application Insights                      │  │
│  │  - Correlated traces (Weave ID → App Insights)   │  │
│  │  - Metrics, alerts, dashboards                   │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## 9. Sample Configuration Files

### 9.1 Azure Container Apps (Dockerfile)

```dockerfile
# Dockerfile for SIT Copilot with Weave
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen

# Copy application
COPY ./app ./app

# Set environment variables (override at deployment)
ENV WEAVE_ENABLED=false
ENV WEAVE_MODE=local
ENV WEAVE_PROJECT=sit-copilot

# Run application
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

### 9.2 Azure Container Apps (container-app.yaml)

```yaml
# container-app.yaml
resource:
  type: Microsoft.App/containerApps
  apiVersion: 2023-05-01
  location: eastus
  name: sit-copilot-api
  properties:
    configuration:
      activeRevisionsMode: Single
      secrets:
        - name: weave-api-key
          valueUri: https://sit-copilot-kv.vault.azure.net/secrets/weave-api-key
    template:
      containers:
        - image: yourregistry.azurecr.io/sit-copilot:latest
          name: sit-copilot
          env:
            - name: WEAVE_ENABLED
              value: "true"
            - name: WEAVE_MODE
              value: "cloud"
            - name: WEAVE_PROJECT
              value: "sit-copilot"
            - name: WANDB_API_KEY
              secretRef: weave-api-key
          resources:
            cpu: 0.5
            memory: 1Gi
          probes:
            - type: liveness
              httpGet:
                path: /health
                port: 8080
      scale:
        minReplicas: 2
        maxReplicas: 10
        rules:
          - name: http-scale-rule
            custom:
              type: http
              metadata:
                concurrentRequests: "100"
```

---

## 10. Deployment Checklist

### Development
- [ ] Weave Local enabled in configuration
- [ ] Local UI accessible at http://localhost:8080
- [ ] Trace data persisted to ./weave-data
- [ ] No WANDB_API_KEY required

### Staging
- [ ] Weave Local or Cloud (test both)
- [ ] Network connectivity to Weave endpoints (if Cloud)
- [ ] Integration with Application Insights
- [ ] Sampling rate configured

### Production
- [ ] Weave Cloud enabled
- [ ] API key stored in Azure Key Vault
- [ ] Managed Identity configured for Key Vault access
- [ ] NSG rules allow HTTPS to api.wandb.ai
- [ ] Health probes configured
- [ ] Resource limits set
- [ ] Auto-scaling configured
- [ ] Monitoring and alerting in place

---

## Status Notes

- **Gemini CLI**: Not available (GEMINI_API_KEY not set)
- **Research Method**: Knowledge-based synthesis from training data
- **Verification Needed**: Test deployment in Azure environment
- **Action Items**:
  1. Create Azure Container Apps environment for testing
  2. Validate Weave Local in ACI
  3. Set up Key Vault for production secrets
  4. Test Weave Cloud connectivity from Azure
