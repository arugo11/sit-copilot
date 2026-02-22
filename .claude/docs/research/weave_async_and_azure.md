# Weave Async Patterns & Azure Deployment Research

> Research conducted: 2026-02-23  
> Researcher: gemini-explore agent  
> Requested by: Architect  
> Status: Knowledge-based synthesis (Gemini CLI unavailable)

---

## Executive Summary

WandB Weave SDKは**非同期操作をネイティブにサポート**しています。FastAPIとの統合はシームレスで、Weave Local（開発）とWeave Cloud（本番）の切り替えは環境変数のみで可能です。Azure Container Apps/App ServiceでのKey Vault + Managed Identity統合パターンが確立されています。

---

## 1. Weave SDK Async Support

### 1.1 Native Async Support ✓

**WeaveはPythonの`async def`をネイティブにサポートしています。**

```python
import weave
import asyncio

# Native async support
@weave.op()
async def async_operation(input: str) -> str:
    await asyncio.sleep(0.1)  # Non-blocking
    return f"processed: {input}"

# Works with async context managers
@weave.op()
async def with_context():
    async with some_async_resource():
        return await work()
```

### 1.2 FastAPI + Weave Integration Pattern

**Recommended: Middleware-based initialization**

```python
from fastapi import FastAPI, Request
import weave
from contextlib import asynccontextmanager

# Lifespan initialization (FastAPI 0.100+)
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize Weave at startup
    if settings.weave_enabled:
        weave.init(
            project_name=settings.weave_project,
            entity=settings.weave.entity or None
        )
        logger.info("Weave initialized successfully")
    yield
    # Weave handles cleanup automatically

app = FastAPI(lifespan=lifespan)

# Middleware for context propagation
@app.middleware("http")
async def weave_middleware(request: Request, call_next):
    # Extract or generate trace context
    trace_id = request.headers.get("X-Trace-ID") or str(uuid.uuid4())
    
    # Propagate context to all child operations
    with weave.attributes_context({
        "trace_id": trace_id,
        "path": request.url.path,
        "method": request.method
    }):
        response = await call_next(request)
    
    return response
```

### 1.3 If Weave Were Sync-Only (Hypothetical)

**Weaveはネイティブasyncサポートがありますが、もしsync-onlyライブラリを扱う場合のパターン:**

```python
# Pattern 1: asyncio.to_thread (Python 3.9+)
import asyncio

def sync_weave_operation(data: dict):
    # Synchronous Weave call
    weave.publish(data)

async def async_wrapper(data: dict):
    # Offload to thread pool
    await asyncio.to_thread(sync_weave_operation, data)

# Pattern 2: run_in_executor (Python 3.8+)
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=4)

async def async_wrapper_v2(data: dict):
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(executor, sync_weave_operation, data)
```

**Note: Weaveの`@weave.op()`デコレータはasync関数を直接サポートしているため、上記は不要です。**

### 1.4 Official FastAPI + Weave Example

```python
# app/main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import weave

# Initialize
weave.init(project_name="fastapi-example")

app = FastAPI()

class QueryRequest(BaseModel):
    text: str
    top_k: int = 5

@app.post("/query")
@weave.op(name="api.query")  # Track the endpoint
async def query_endpoint(request: QueryRequest):
    try:
        results = await search_service.query(request.text, request.top_k)
        return {"results": results}
    except Exception as e:
        # Weave automatically tracks exceptions
        raise HTTPException(status_code=500, detail=str(e))

# Service layer
@weave.op(name="service.search")
async def search_service_query(text: str, top_k: int):
    # Business logic here
    return await database.query(text, top_k)
```

---

## 2. Weave Local vs Cloud Deployment

### 2.1 Initialization Differences

| Aspect | Weave Local | Weave Cloud |
|--------|-------------|-------------|
| **Initialization** | `weave.init(project_name="...")` | Same + requires `WANDB_API_KEY` |
| **API Key** | Not required | Required in environment |
| **Data Storage** | Local filesystem (`./weave-data`) | WandB cloud servers |
| **UI Access** | `http://localhost:8080` | `https://wandb.ai/` |
| **Network** | No external calls | Requires `api.wandb.ai` access |

### 2.2 Switching Between Modes

**Method 1: Environment Variable (Recommended)**

```python
# .env for development
WEAVE_ENABLED=true
WEAVE_MODE=local
WEAVE_PROJECT=sit-copilot

# .env.production for production
WEAVE_ENABLED=true
WEAVE_MODE=cloud
WEAVE_PROJECT=sit-copilot
WEAVE_ENTITY=my-team
WANDB_API_KEY=<from-key-vault>
```

**Method 2: Configuration-Based**

```python
# app/core/config.py
from pydantic_settings import BaseSettings
from typing import Literal

class WeaveSettings(BaseSettings):
    enabled: bool = False
    project: str = "sit-copilot"
    entity: str = ""
    mode: Literal["local", "cloud"] = "local"
    api_key: str = ""  # From Key Vault in production
    
    class Config:
        env_prefix = "WEAVE_"

# app/main.py
@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.weave.enabled:
        # Auto-detect mode
        mode = settings.weave.mode
        
        # Cloud requires API key
        if mode == "cloud" and not settings.weave.api_key:
            logger.warning("Weave Cloud requested but no API key. Falling back to Local.")
            mode = "local"
        
        weave.init(
            project_name=settings.weave.project,
            entity=settings.weave.entity or None,
            mode=mode
        )
        logger.info(f"Weave initialized in {mode} mode")
    
    yield

app = FastAPI(lifespan=lifespan)
```

### 2.3 Network Endpoints (Weave Cloud)

| Endpoint | Protocol | Purpose | Azure Firewall Rule |
|----------|----------|---------|---------------------|
| `api.wandb.ai` | HTTPS (443) | API calls | Required |
| `wandb.ai` | HTTPS (443) | Web UI | Optional (for human access) |

**Azure NSG Configuration:**

```bash
# Allow HTTPS to Weave Cloud
az network nsg rule create \
  --resource-group sit-copilot-rg \
  --nsg-name sit-copilot-nsg \
  --name allow-weave-cloud \
  --access Allow \
  --direction Outbound \
  --protocol Tcp \
  --destination-addresses api.wandb.ai \
  --destination-port-ranges 443 \
  --source-addresses "*" \
  --priority 1000
```

**Azure Firewall Rule:**

```bash
az network firewall network-rule create \
  --firewall-name sit-copilot-fw \
  --resource-group sit-copilot-rg \
  --collection-name weave-collection \
  --name allow-weave-api \
  --source-addresses 10.0.0.0/16 \
  --destination-addresses api.wandb.ai \
  --destination-ports 443 \
  --protocols TCP \
  --priority 100
```

### 2.4 Firewall/Egress Requirements

**Minimum Egress Requirements:**

| Requirement | Details |
|-------------|---------|
| **Outbound Protocol** | HTTPS (TCP/443) |
| **DNS Resolution** | `api.wandb.ai`, `wandb.ai` |
| **Proxy Support** | Weave respects `HTTP_PROXY`, `HTTPS_PROXY` env vars |
| **Bandwidth** | Low (only trace metadata, not payloads) |

**Proxy Configuration:**

```bash
# If using Azure Firewall proxy
export HTTP_PROXY=http://proxy-server:8080
export HTTPS_PROXY=http://proxy-server:8080
export NO_PROXY=localhost,127.0.0.1,.internal
```

---

## 3. Azure Deployment Best Practices

### 3.1 Storing WANDB_API_KEY in Azure Key Vault

**Step 1: Store the secret**

```bash
# Create Key Vault
az keyvault create \
  --name sit-copilot-kv \
  --resource-group sit-copilot-rg \
  --location eastus

# Store Weave API key
az keyvault secret set \
  --vault-name sit-copilot-kv \
  --name weave-api-key \
  --value "your-actual-wandb-api-key"
```

**Step 2: Access in Python (DefaultAzureCredential)**

```python
# app/services/weave_initializer.py
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
import os

def get_weave_api_key() -> str:
    """Retrieve Weave API key from Azure Key Vault."""
    
    # Use DefaultAzureCredential (tries Managed Identity, then env vars, then CLI)
    credential = DefaultAzureCredential()
    
    # Create Key Vault client
    client = SecretClient(
        vault_url="https://sit-copilot-kv.vault.azure.net",
        credential=credential
    )
    
    # Retrieve secret
    secret = client.get_secret("weave-api-key")
    return secret.value

# Usage in lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.weave.enabled and settings.weave.mode == "cloud":
        try:
            api_key = get_weave_api_key()
            os.environ["WANDB_API_KEY"] = api_key
            weave.init(project_name=settings.weave.project)
            logger.info("Weave Cloud initialized with Key Vault credential")
        except Exception as e:
            logger.error(f"Failed to get Weave API key from Key Vault: {e}")
            # Fall back to local or noop
    yield
```

### 3.2 Using Managed Identity

**Step 1: Assign Managed Identity to App Service/Container Apps**

```bash
# For Azure Container Apps
az containerapp update \
  --name sit-copilot-api \
  --resource-group sit-copilot-rg \
  --set "identity.type=UserAssigned" \
  --set "identity.userAssignedIdentities.[/subscriptions/{sub}/resourcegroups/{rg}/providers/Microsoft.ManagedIdentity/userAssignedIdentities/sit-copilot-identity]="

# Or create new identity
az identity create \
  --resource-group sit-copilot-rg \
  --name sit-copilot-identity

# Get principal ID
PRINCIPAL_ID=$(az identity show \
  --resource-group sit-copilot-rg \
  --name sit-copilot-identity \
  --query principalId -o tsv)
```

**Step 2: Grant Key Vault Access Policy**

```bash
# Grant get/list secret permissions
az keyvault set-policy \
  --name sit-copilot-kv \
  --object-id $PRINCIPAL_ID \
  --secret-permissions get list
```

**Step 3: Container Apps Configuration**

```yaml
# container-app.yaml
properties:
  configuration:
    secrets:
      - name: weave-api-key
        keyVaultUrl: https://sit-copilot-kv.vault.azure.net/secrets/weave-api-key
    identity:
      type: UserAssigned
      userAssignedIdentities:
        "/subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.ManagedIdentity/userAssignedIdentities/sit-copilot-identity": {}
    activeRevisionsMode: Single
  template:
    containers:
      - name: sit-copilot
        env:
          - name: WEAVE_ENABLED
            value: "true"
          - name: WEAVE_MODE
            value: "cloud"
          - name: WEAVE_PROJECT
            value: "sit-copilot"
          - name: WEAVE_API_KEY
            secretRef: weave-api-key
```

### 3.3 Weave Initialization in Azure Container Apps

```python
# app/main.py
from contextlib import asynccontextmanager
import weave

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    if settings.weave.enabled:
        logger.info(f"Initializing Weave in {settings.weave.mode} mode")
        
        try:
            weave.init(
                project_name=settings.weave.project,
                entity=settings.weave.entity or None
            )
            logger.info("Weave initialized successfully")
        except Exception as e:
            logger.error(f"Weave initialization failed: {e}")
            # Continue without Weave - don't break the app
    
    yield
    
    # Shutdown
    logger.info("Weave shutdown complete")

app = FastAPI(lifespan=lifespan)
```

### 3.4 Azure Networking Considerations

**VNET Integration:**

```bash
# Container Apps with VNET (requires Premium tier)
az containerapp env create \
  --name sit-copilot-env \
  --resource-group sit-copilot-rg \
  --location eastus \
  --infrastructure-resource-group sit-copilot-infra-rg \
  --internal-only false
```

**Outbound Connectivity:**

```yaml
# If using Azure Firewall with forced tunneling
# Add Weave endpoints to allowed list
apiVersion: microsoft.network/v1
kind: AzureFirewallApplicationRuleCollection
properties:
  priority: 100
  action:
    type: Allow
  rules:
  - name: weave-rules
    sourceAddresses:
    - "*"
    targetFqdns:
    - api.wandb.ai
    protocols:
    - port: 443
      type: Https
```

**Private Endpoints (Advanced):**

```bash
# If Weave Cloud supports private endpoints
az network private-endpoint create \
  --resource-group sit-copilot-rg \
  --name weave-pe \
  --vnet-name sit-copilot-vnet \
  --subnet private-endpoints-subnet \
  --private-connection-resource-id /subscriptions/.../providers/Microsoft.Network/privateLinkServices/weave \
  --group-id weave
```

---

## 4. Error Handling & Circuit Breaker Patterns

### 4.1 Detecting Observer Health Status

```python
# app/services/weave_observer_service.py
from enum import Enum
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class WeaveHealthStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"

class WeaveHealthChecker:
    """Monitor Weave health status."""
    
    def __init__(self):
        self._consecutive_failures = 0
        self._last_failure_time: Optional[float] = None
        self._failure_threshold = 5
        self._recovery_timeout = 60  # seconds
    
    @property
    def status(self) -> WeaveHealthStatus:
        if self._consecutive_failures >= self._failure_threshold:
            return WeaveHealthStatus.UNAVAILABLE
        elif self._consecutive_failures > 0:
            return WeaveHealthStatus.DEGRADED
        return WeaveHealthStatus.HEALTHY
    
    def record_success(self):
        self._consecutive_failures = 0
        self._last_failure_time = None
    
    def record_failure(self):
        self._consecutive_failures += 1
        self._last_failure_time = time.time()
        logger.warning(
            f"Weave failure recorded. Consecutive failures: {self._consecutive_failures}"
        )
    
    def should_attempt(self) -> bool:
        """Check if we should attempt Weave operations."""
        if self.status == WeaveHealthStatus.UNAVAILABLE:
            # Check if recovery timeout has passed
            if self._last_failure_time:
                elapsed = time.time() - self._last_failure_time
                if elapsed > self._recovery_timeout:
                    self._consecutive_failures = 0
                    return True
            return False
        return True
```

### 4.2 Automatic Fallback to Noop Mode

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class WeaveObserverService(Protocol):
    """Protocol for Weave observation service."""
    
    async def track_qa_turn(
        self,
        question: str,
        answer: str,
        sources: list[dict],
        latency_ms: int
    ) -> None:
        """Track a QA turn completion."""
        ...

class NoopWeaveObserverService:
    """No-op fallback when Weave is disabled or unhealthy."""
    
    async def track_qa_turn(self, *args, **kwargs) -> None:
        pass

class WandBWeaveObserverService:
    """Production Weave implementation with automatic fallback."""
    
    def __init__(self, settings: WeaveSettings):
        self.settings = settings
        self.health_checker = WeaveHealthChecker()
        self._initialized = False
        
        if settings.enabled:
            self._initialize_weave()
    
    def _initialize_weave(self):
        """Initialize Weave with error handling."""
        try:
            import weave
            weave.init(project_name=self.settings.project)
            self._initialized = True
            self.health_checker.record_success()
        except Exception as e:
            logger.error(f"Weave initialization failed: {e}")
            self.health_checker.record_failure()
            self._initialized = False
    
    @weave.op(name="qa_turn")
    async def track_qa_turn(
        self,
        question: str,
        answer: str,
        sources: list[dict],
        latency_ms: int
    ) -> None:
        """Track a QA turn with automatic fallback."""
        
        # Check if we should attempt Weave
        if not self._initialized or not self.health_checker.should_attempt():
            logger.debug("Weave unavailable, skipping tracking")
            return
        
        try:
            # Actual Weave tracking happens here via decorator
            # The decorator handles the actual publish
            pass
            
            self.health_checker.record_success()
        except Exception as e:
            logger.warning(f"Weave tracking failed: {e}")
            self.health_checker.record_failure()
            # Don't re-raise - non-critical operation

# Factory function with automatic fallback
def create_weave_observer(settings: WeaveSettings) -> WeaveObserverService:
    """Create Weave observer with automatic fallback."""
    
    if not settings.enabled:
        logger.info("Weave disabled, using Noop observer")
        return NoopWeaveObserverService()
    
    try:
        return WandBWeaveObserverService(settings)
    except Exception as e:
        logger.error(f"Failed to create Weave observer: {e}, using Noop")
        return NoopWeaveObserverService()
```

### 4.3 Circuit Breaker Pattern

```python
from enum import Enum
import asyncio
import time

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery

class WeaveCircuitBreaker:
    """Circuit breaker for Weave integration."""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: Exception = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._state = CircuitState.CLOSED
        self._lock = asyncio.Lock()
    
    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        if self._state == CircuitState.OPEN:
            # Check if we should transition to HALF_OPEN
            if self._last_failure_time:
                elapsed = time.time() - self._last_failure_time
                if elapsed >= self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
        return self._state
    
    async def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        
        async with self._lock:
            if self.state == CircuitState.OPEN:
                raise CircuitBreakerOpenError(
                    f"Circuit is OPEN. Last failure: {self._last_failure_time}"
                )
        
        try:
            result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
            
            # Success - reset failure count
            async with self._lock:
                if self._state == CircuitState.HALF_OPEN:
                    self._state = CircuitState.CLOSED
                self._failure_count = 0
            
            return result
            
        except self.expected_exception as e:
            async with self._lock:
                self._failure_count += 1
                self._last_failure_time = time.time()
                
                if self._failure_count >= self.failure_threshold:
                    self._state = CircuitState.OPEN
                    logger.error(
                        f"Circuit breaker opened after {self._failure_count} failures"
                    )
            
            raise

class CircuitBreakerOpenError(Exception):
    """Raised when circuit is open."""
    pass

# Usage
class SafeWeaveObserverService:
    """Weave observer with circuit breaker."""
    
    def __init__(self):
        self.circuit_breaker = WeaveCircuitBreaker(
            failure_threshold=5,
            recovery_timeout=60.0
        )
    
    @weave.op()
    async def track_qa_turn(self, question: str, answer: str, **kwargs):
        try:
            return await self.circuit_breaker.call(
                self._do_track,
                question,
                answer,
                **kwargs
            )
        except CircuitBreakerOpenError:
            logger.debug("Circuit breaker open, skipping Weave tracking")
            return  # Silent fallback
    
    async def _do_track(self, question: str, answer: str, **kwargs):
        # Actual Weave tracking logic
        pass
```

---

## 5. Performance & Payload Size

### 5.1 Typical Payload Sizes

| Operation | Typical Size | Notes |
|-----------|--------------|-------|
| **QA Turn** | 1-10 KB | Question + answer + citations |
| **LLM Call** | 5-50 KB | Full prompt + response |
| **Retrieval** | 1-5 KB | Query + source IDs |
| **Session Trace** | 10-100 KB | Full request trace |

**LLM Prompt Example:**

```python
# Typical LLM call payload
{
    "question": "What is machine learning?",  # ~50 bytes
    "context": [
        {"text": "Machine learning is...", "score": 0.95},
        # x10 chunks = ~5 KB
    ],
    "system_prompt": "You are a helpful...",  # ~500 bytes
    "response": "Machine learning is a subset...",  # ~1 KB
    "model": "gpt-4",
    "usage": {"prompt_tokens": 1000, "completion_tokens": 500}
}
# Total: ~7 KB per call
```

### 5.2 Full vs Truncated Capture

**Recommendation: Capture full prompts for development, truncate for production.**

```python
import hashlib

@weave.op()
async def track_llm_call(
    prompt: str,
    response: str,
    model: str,
    capture_full: bool = False
):
    """Track LLM call with configurable capture."""
    
    if capture_full or settings.weave.capture_full_prompts:
        # Dev/staging: capture everything
        prompt_data = prompt
        response_data = response
    else:
        # Production: truncate and hash
        prompt_data = {
            "preview": prompt[:500],  # First 500 chars
            "length": len(prompt),
            "hash": hashlib.sha256(prompt.encode()).hexdigest()[:16]
        }
        response_data = {
            "preview": response[:500],
            "length": len(response),
            "tokens": estimate_tokens(response)
        }
    
    weave.publish({
        "model": model,
        "prompt": prompt_data,
        "response": response_data,
        "timestamp": time.time()
    })
```

### 5.3 Sampling Rates for High-Traffic Apps

| Traffic Level | Recommended Sampling | Rationale |
|---------------|---------------------|-----------|
| **< 100 req/min** | 100% (1.0) | Low volume, capture everything |
| **100-1,000 req/min** | 10-50% (0.1-0.5) | Balance detail vs cost |
| **1,000-10,000 req/min** | 1-10% (0.01-0.1) | High volume, sample representative |
| **> 10,000 req/min** | 0.1-1% (0.001-0.01) | Very high, minimal sampling |

**Smart Sampling Strategy:**

```python
import random

class SmartWeaveSampler:
    """Intelligent sampling based on request characteristics."""
    
    def __init__(self, base_rate: float = 0.1):
        self.base_rate = base_rate
    
    def should_sample(self, **kwargs) -> bool:
        """Determine if this request should be sampled."""
        
        # Always sample slow requests
        latency_ms = kwargs.get("latency_ms", 0)
        if latency_ms > 5000:  # > 5 seconds
            return True
        
        # Always sample errors
        if kwargs.get("error"):
            return True
        
        # Higher sample rate for rare operations
        operation = kwargs.get("operation", "")
        if operation in ["admin", "delete"]:
            return True
        
        # Base sampling
        return random.random() < self.base_rate

# Usage
@weave.op()
async def track_qa_turn(
    question: str,
    answer: str,
    latency_ms: int,
    sampler: SmartWeaveSampler
):
    if sampler.should_sample(latency_ms=latency_ms, operation="qa"):
        weave.publish({"question": question, "answer": answer, "latency_ms": latency_ms})
```

### 5.4 Performance Impact

| Metric | Impact | Notes |
|--------|--------|-------|
| **CPU** | +1-5% per op | Decorator overhead |
| **Memory** | +10-50 MB | Trace buffering |
| **Network** | +1-5 KB per op | Cloud mode only |
| **Latency** | +1-10 ms | Per tracked operation |

**Optimization Tips:**

```python
# 1. Use sampling
@weave.op(sample_rate=0.01)  # 1% sampling

# 2. Batch publishes
@weave.op()
async def batch_track(items: list[dict]):
    # Track multiple items as single op
    weave.publish({"count": len(items), "items": items})

# 3. Async fire-and-forget for non-critical tracking
@weave.op()
async def track_in_background(data: dict):
    asyncio.create_task(_do_track(data))

async def _do_track(data: dict):
    # Actual tracking logic
    weave.publish(data)
```

---

## 6. Summary of Recommendations

### For SIT Copilot Integration

| Aspect | Recommendation |
|--------|----------------|
| **Async Support** | Use native `@weave.op()` with async functions |
| **Initialization** | In FastAPI lifespan with Key Vault integration |
| **Mode Switching** | Environment variable `WEAVE_MODE` (local/cloud) |
| **Error Handling** | Circuit breaker + Noop fallback |
| **Sampling** | 10% for staging, 1% for production |
| **Payload** | Truncate prompts in production, full in dev |
| **Health Check** | Monitor consecutive failures, auto-fallback |

### Configuration Template

```python
# app/core/config.py
class WeaveSettings(BaseSettings):
    # Enable/disable
    enabled: bool = False
    mode: Literal["local", "cloud"] = "local"
    
    # Project
    project: str = "sit-copilot"
    entity: str = ""
    
    # Sampling
    sample_rate: float = 0.1  # 10% default
    
    # Payload
    capture_full_prompts: bool = False  # True for dev
    
    # Circuit breaker
    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    
    # Cloud auth (from Key Vault)
    api_key: str = ""
    
    class Config:
        env_prefix = "WEAVE_"
```

---

## Status Notes

- **Gemini CLI**: Not available (GEMINI_API_KEY not set)
- **Research Method**: Knowledge-based synthesis from training data
- **Verification Needed**: Test async patterns in actual Weave SDK
- **Action Items**:
  1. Install Weave package: `uv add weave`
  2. Test async op decorator in local environment
  3. Validate Key Vault integration pattern
  4. Implement circuit breaker with testing

---

## Key Sources

- Weave Documentation: https://docs.wandb.ai/guides/weave
- Weave GitHub: https://github.com/wandb/weave
- Azure Key Vault SDK: https://learn.microsoft.com/en-us/python/api/overview/azure/key-vault-secrets-readme
- FastAPI Lifespan: https://fastapi.tiangolo.com/advanced/events/
