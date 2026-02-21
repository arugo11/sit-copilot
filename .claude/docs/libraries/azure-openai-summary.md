# Azure OpenAI Library — Lecture Summarization

Library constraints and best practices for Azure OpenAI integration in F1 lecture summary.

---

## Version & API

### Recommended Configuration

```python
API_VERSION = "2024-10-21"  # Current GA
MODEL = "gpt-4o"            # Version 2024-11-20 or 2024-08-06
PYTHON_PACKAGE = "openai>=1.42.0"  # For structured outputs
```

### API Endpoints

```
POST {endpoint}/openai/deployments/{deployment}/chat/completions?api-version=2024-10-21
```

---

## Key Constraints

### 1. Rate Limits

| Metric | Description | Typical Limit |
|--------|-------------|---------------|
| RPM | Requests Per Minute | Varies by tier |
| TPM | Tokens Per Minute | Varies by tier |
| Window | Evaluation Period | 1-10 seconds (not just per-minute!) |

**Important**: Rate limits are evaluated over short intervals (1-10s), not just per-minute.

### 2. Token Limits

| Model | Context Window | Max Output |
|-------|---------------|------------|
| gpt-4o | 128K | 4K-16K (configurable) |

**Japanese Token Ratio**: ~1.2-1.5 tokens per character (vs 0.75 per word for English).

### 3. Structured Outputs

- **Required**: `response_format: {"type": "json_object"}` 
- **Supported Models**: gpt-4o (2024-08-06+), gpt-4o-mini
- **Constraint**: System message must include "Return JSON" or similar

### 4. No Incremental Updates

- Index/summary must be regenerated when new content added
- No partial updates to existing summaries

---

## Request Pattern

### Basic Chat Completion

```python
from openai import AzureOpenAI
import asyncio

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version="2024-10-21",
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)

async def summarize_lecture(sources: list[dict]) -> dict:
    prompt = _build_summary_prompt(sources)
    
    response = await asyncio.to_thread(
        client.chat.completions.create,
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": "You are a lecture summarization assistant. Return JSON."
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0,
        max_tokens=1000,
        response_format={"type": "json_object"}
    )
    
    return json.loads(response.choices[0].message.content)
```

### Retry with Exponential Backoff

```python
import time
import random
from urllib.error import HTTPError

def call_with_retry(func, max_retries=5):
    for attempt in range(max_retries):
        try:
            return func()
        except HTTPError as e:
            if e.code == 429:  # Rate limit
                if attempt == max_retries - 1:
                    raise
                delay = (2 ** attempt) + random.uniform(0, 1)
                time.sleep(delay)
            else:
                raise
```

---

## Response Format

### JSON Schema for Summary

```json
{
    "type": "object",
    "properties": {
        "summary": {
            "type": "string",
            "maxLength": 400,
            "description": "Overall summary in Japanese"
        },
        "key_points": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "point": {"type": "string", "maxLength": 100},
                    "source_type": {"type": "string", "enum": ["speech", "slide", "board"]},
                    "timestamp": {"type": "string", "pattern": "^\\d{2}:\\d{2}$"}
                },
                "required": ["point", "source_type", "timestamp"]
            },
            "minItems": 3,
            "maxItems": 5
        }
    },
    "required": ["summary", "key_points"]
}
```

---

## Error Handling

### HTTP Status Codes

| Code | Meaning | Action |
|------|---------|--------|
| 200 | Success | Process response |
| 400 | Bad Request | Fix request (invalid JSON, missing params) |
| 401 | Invalid API Key | Check credentials |
| 403 | Quota Exceeded | Request quota increase |
| 429 | Rate Limited | Retry with backoff |
| 500 | Server Error | Retry with backoff |
| 503 | Service Unavailable | Retry with backoff |

### F1 Requirement: No Fallback

**Per project specification**: When Azure OpenAI is disabled/unavailable, raise ERROR.
Do NOT use local/deterministic fallback (unlike F4).

```python
def _is_azure_openai_ready(self) -> bool:
    """Check if Azure OpenAI is properly configured."""
    if not self._api_key.strip():
        return False
    if not self._endpoint.strip():
        return False
    if not self._model.strip():
        return False
    return "openai.azure.com" in self._endpoint.lower()

async def summarize(self, sources: list[Source]) -> Summary:
    if not self._is_azure_openai_ready():
        raise LectureSummaryError(
            "Azure OpenAI is not configured. "
            "F1 summary requires Azure OpenAI (no fallback available)."
        )
    # Proceed with API call...
```

---

## Cost Optimization

### Token Counting

```python
import tiktoken

def count_tokens(text: str, model: str = "gpt-4o") -> int:
    encoding = tiktoken.encoding_for_model(model)
    return len(encoding.encode(text))

# Pre-calculate before API call
input_tokens = count_tokens(input_text)
estimated_output_tokens = 1000  # Based on max_tokens
estimated_cost = (
    (input_tokens / 1000) * 0.005 +
    (estimated_output_tokens / 1000) * 0.015
)
```

### Optimization Strategies

1. **Set appropriate max_tokens**: Don't over-allocate
2. **Pre-filter sources**: Remove irrelevant content before API call
3. **Use concise prompts**: Eliminate redundant instructions
4. **Monitor usage**: Check response headers for rate limit status

---

## Prompt Templates

### System Prompt

```
あなたは講義の要約を専門とするAIアシスタントです。

講義の発言、スライド、板書の内容を要約し、重要なポイントを抽出してください。
必ずタイムスタンプを引用して情報の出典を明示してください。

回答はJSON形式で返してください。
```

### User Prompt Template

```
以下の講義コンテンツを要約してください。

【発言】
{speech_section}

【スライド】
{slide_section}

【板書】
{board_section}

要件:
- 600文字以内で全体を要約
- 3-5つの重要なポイントを抽出
- 各ポイントに出典を明示: [発言:05:23], [スライド:03:10]など
- タイムスタンプは必ず含める

出力形式:
{{
    "summary": "全体の要約（400字以内）",
    "key_points": [
        {{"point": "要点1", "source_type": "speech", "timestamp": "05:23"}},
        {{"point": "要点2", "source_type": "slide", "timestamp": "03:10"}}
    ]
}}
```

---

## Reusable Patterns from F4

### Configuration Constants

```python
# From app/services/lecture_answerer_service.py
DEFAULT_MODEL = "gpt-4o"
DEFAULT_MAX_TOKENS = 1000
DEFAULT_TEMPERATURE = 0.7  # Use 0 for summarization
DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_API_VERSION = "2024-10-21"
```

### Source Format

```python
# Extend F4's LectureSource schema
@dataclass
class LectureSource:
    text: str
    timestamp: str | None  # "MM:SS" format
    source_type: Literal["speech", "slide", "board"]  # New for F1
    bm25_score: float = 0.0
    is_direct_hit: bool = False
```

### Azure Readiness Check

```python
# Reuse from F4 services
def _is_azure_openai_ready(self) -> bool:
    if not self._api_key.strip():
        return False
    if not self._endpoint.strip():
        return False
    if not self._model.strip():
        return False
    return "openai.azure.com" in self._endpoint.lower()
```

### URL Building

```python
# Reuse from F4 services
from urllib.parse import quote

def _build_chat_completion_url(self) -> str:
    endpoint = self._endpoint.rstrip("/")
    deployment = quote(self._model.strip(), safe="")
    return (
        f"{endpoint}/openai/deployments/{deployment}/chat/completions"
        f"?api-version={self._api_version}"
    )
```

---

## Security Notes

1. **API Key Storage**: Use Azure Key Vault, never hardcode
2. **API Version Pinning**: Always specify `api_version` parameter
3. **Error Messages**: Don't expose internal details to users
4. **Request Sanitization**: Validate/escape user content in prompts

---

## Testing

### Mock Response for Tests

```python
def mock_azure_response(summary: str, key_points: list[dict]) -> dict:
    return {
        "choices": [{
            "message": {
                "content": json.dumps({
                    "summary": summary,
                    "key_points": key_points
                })
            }
        }]
    }
```

### Test Scenarios

1. **Success**: Valid sources return structured summary
2. **Empty Sources**: Return error (no fallback)
3. **Azure Unavailable**: Raise exception
4. **Rate Limited**: Retry with backoff
5. **Invalid JSON**: Handle parse error

---

## Monitoring

### Response Headers to Track

```python
def log_rate_limits(response_headers: dict):
    remaining_requests = response_headers.get("x-ratelimit-remaining-requests")
    remaining_tokens = response_headers.get("x-ratelimit-remaining-tokens")
    reset_requests = response_headers.get("x-ratelimit-reset-requests")
    
    logger.info(
        "azure_openai_rate_limits",
        extra={
            "remaining_requests": remaining_requests,
            "remaining_tokens": remaining_tokens,
            "reset_seconds": reset_requests
        }
    )
```

---

## Dependencies

```toml
[project]
dependencies = [
    "openai>=1.42.0",  # For structured outputs
    "tiktoken>=0.5.0",  # For token counting
]
```

---

## Reference Implementation

See F4 services for reusable patterns:
- `app/services/lecture_answerer_service.py` - Azure OpenAI call pattern
- `app/services/lecture_verifier_service.py` - Verification pattern
- `app/schemas/lecture_qa.py` - Source schema format
