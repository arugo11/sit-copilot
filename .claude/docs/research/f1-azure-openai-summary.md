# F1 Azure OpenAI Summary Integration — Research Findings

## Overview

Research findings for integrating Azure OpenAI into F1 (30-second lecture summary) feature.
Focus: Japanese lecture summarization with evidence attribution, reusing F4 patterns.

---

## 1. Azure OpenAI API Best Practices (2025)

### Latest API Architecture

- **Responses API**: New unified API (2025) combining chat completions and assistants
- **Recommended API Version**: `2024-10-21` (current GA)
- **Primary Model**: `gpt-4o` (versions: 2024-11-20, 2024-08-06)

### Basic Setup Pattern

```python
from openai import AzureOpenAI

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version="2024-10-21",
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": "You are a lecture summarization assistant."},
        {"role": "user", "content": "Summarize this..."}
    ],
    temperature=0,
    max_tokens=1000
)
```

### Model Parameters for Summarization

| Parameter | Recommended Value | Rationale |
|-----------|------------------|-----------|
| `temperature` | 0-0.3 | Factual consistency, low randomness |
| `max_tokens` | 800-1500 | Balance between detail and cost |
| `top_p` | 1.0 | Default recommended |
| `frequency_penalty` | 0.0 | No penalties for summarization |
| `presence_penalty` | 0.0 | No penalties needed |

---

## 2. Japanese Text Handling

### Tokenization Characteristics

- **Japanese**: ~1.2-1.5 tokens per character (more expensive than English)
- **English**: ~0.75 tokens per word (~4 chars per token)
- **Punctuation**: ~1 token per symbol
- **Emojis**: ~2-3 tokens each

### Token Counting Tool

```python
import tiktoken

def count_tokens(text: str, model: str = "gpt-4o") -> int:
    encoding = tiktoken.encoding_for_model(model)
    return len(encoding.encode(text))

# Example
japanese_text = "こんにちは、世界です。"
print(count_tokens(japanese_text))  # ~8-10 tokens
```

**Key Insight**: Japanese is 1.5-2x more expensive than English for equivalent content.

---

## 3. Structured Output with Citations (2025)

### Structured Outputs Feature

- **Available since**: API version `2024-08-01-preview`
- **GA version**: `2024-10-21`
- **Supported by gpt-4o**: Yes (versions 2024-08-06, 2024-11-20)
- **Purpose**: Force JSON schema compliance

### Implementation Pattern

```python
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[...],
    response_format={
        "type": "json_object"
    },
    temperature=0
)

# Or with Pydantic (openai >= 1.42.0)
from pydantic import BaseModel

class LectureSummary(BaseModel):
    summary: str
    key_points: list[str]
    citations: list[dict]

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[...],
    response_format={
        "type": "json_schema",
        "json_schema": {
            "name": "lecture_summary",
            "schema": LectureSummary.model_json_schema()
        }
    }
)
```

### Evidence Citation Pattern (from F4)

**Existing F4 Citation Format**:
```json
{
    "type": "speech|visual",
    "timestamp": "05:23",
    "text": "excerpt from source"
}
```

**F4 Verifier Pattern** (reusable for F1):
- Claim-by-claim validation
- JSON output with `passed`, `summary`, `unsupported_claims`
- Local fallback using text fragment matching

---

## 4. Prompt Engineering for Lecture Summarization

### Best Practices from Research

1. **Clear System Role**: Define specialized persona for Japanese lecture summarization
2. **Output Format Spec**: Explicitly request JSON/structure with citations
3. **Multi-Source Handling**: Structure prompt to handle speech + slide + board
4. **Length Constraints**: Specify character limits (600 char for F1)
5. **Evidence Attribution**: Force timestamp-based citations

### Template Pattern

```python
SYSTEM_PROMPT = """あなたは講義の要約を専門とするAIアシスタントです。

講義の発言、スライド、板書の内容を要約し、重要なポイントを抽出してください。
必ずタイムスタンプを引用して情報の出典を明示してください。"""

USER_PROMPT = """以下の講義コンテンツを要約してください。

【発言】
- [05:23] {transcript_text}
- [12:45] {transcript_text}

【スライド】
- [03:10] {slide_text}

【板書】
- [08:30] {board_text}

要件:
- 600文字以内で要約
- 3-5つの重要なポイントを箇条書き
- 各ポイントにタイムスタンプを引用
- 出典を明示: [発言:05:23], [スライド:03:10]など

出力形式 (JSON):
{
    "summary": "全体の要約（400字以内）",
    "key_points": [
        {"point": "要点1", "source_type": "speech", "timestamp": "05:23"},
        {"point": "要点2", "source_type": "slide", "timestamp": "03:10"}
    ]
}
"""
```

### Multi-Source Attribution Strategies

| Strategy | Pattern | Pros | Cons |
|----------|---------|------|------|
| Inline Citation | `[発言:05:23] テキスト` | Simple, readable | Hard to parse |
| Structured JSON | Separate citations array | Programmatic, structured | More complex |
| Prefix Format | `（05:23 発言）` | Natural Japanese | Inconsistent |

**Recommendation**: Use structured JSON (reuses F4 pattern).

---

## 5. Cost Optimization Strategies

### Token Management

1. **Estimate Before Call**: Use `tiktoken` to pre-calculate tokens
2. **Set Appropriate max_tokens**: Don't over-allocate
3. **Summarize in Stages**: For long content, summarize chunks first
4. **Cache Repeated Summaries**: Store results for identical inputs

### Cost Calculation

```python
# GPT-4o pricing (approximate, 2025)
INPUT_COST_PER_1K = 0.005  # USD
OUTPUT_COST_PER_1K = 0.015  # USD

def calculate_cost(input_text: str, output_text: str) -> float:
    input_tokens = count_tokens(input_text)
    output_tokens = count_tokens(output_text)
    return (
        (input_tokens / 1000) * INPUT_COST_PER_1K +
        (output_tokens / 1000) * OUTPUT_COST_PER_1K
    )
```

### Japanese-Specific Optimization

- **Use concise Japanese**: Eliminate redundant phrasing
- **Pre-process sources**: Filter irrelevant content before API call
- **Batch similar requests**: Reduce per-request overhead

---

## 6. Error Handling & Retry Patterns

### Rate Limiting (Azure OpenAI)

- **429 Too Many Requests**: Exceeded rate limit (retry with backoff)
- **403 Forbidden**: Exceeded quota (hard limit)
- **Rate Types**: RPM (requests/minute) + TPM (tokens/minute)
- **Evaluation Window**: 1-10 second intervals, not just per-minute

### Retry with Exponential Backoff

```python
import time
import random

def call_with_retry(func, max_retries=5):
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            # Exponential backoff with jitter
            delay = (2 ** attempt) + random.uniform(0, 1)
            time.sleep(delay)
```

### Monitoring Rate Limits

**Response Headers to Monitor**:
- `x-ratelimit-remaining-requests`: Remaining in current window
- `x-ratelimit-reset-requests`: Seconds until reset
- `x-ratelimit-remaining-tokens`: Token budget remaining

### F4 Pattern: Deterministic Fallback

**Existing F4 Approach** (reusable for F1):
```python
def _is_azure_openai_ready(self) -> bool:
    if not self._api_key.strip():
        return False
    if not self._endpoint.strip():
        return False
    # Check for Azure OpenAI endpoint pattern
    return "openai.azure.com" in self._endpoint.lower()

# If not ready, use local fallback
if not self._is_azure_openai_ready():
    return self._build_local_fallback(sources)
```

**F1 Requirement**: ERROR when Azure disabled (no fallback per project brief).

---

## 7. Evidence Attribution in RAG Context

### Research Findings

- **Lost in the Middle Problem**: LLMs struggle with middle context portions
- **Claim-by-Claim Verification**: F4 pattern is research-aligned
- **Conflicting Evidence**: Active research area; use structured verification
- **Temporal Awareness**: Time-based ranking important for lectures

### Reusable F4 Patterns

1. **Source Format**: `LectureSource` with `timestamp`, `text`, `source_type`
2. **Verifier Service**: Claim-by-claim validation with JSON output
3. **Local Fallback**: Text fragment matching (12-char window)

### F1 Adaptation

- **Chunk Units**: SpeechEvents (same as F4)
- **Timestamp Precision**: Preserve for citations
- **Source Types**: speech, slide, board (F4: speech, visual)

---

## 8. Regional Considerations

- **Japan East Region**: Available for Azure OpenAI
- **Data Residency**: Consider compliance requirements
- **Latency**: Japan East better for Japanese users

---

## 9. Security Best Practices

- **Azure Key Vault**: Store API keys (not hardcoded)
- **Managed Identity**: Use where possible
- **API Version Locking**: Pin `api_version` to prevent breaking changes
- **Error Message Sanitization**: Don't expose internals to users

---

## 10. Reusable F4 Components

### Services to Adapt for F1

| F4 Component | F1 Adaptation |
|--------------|---------------|
| `LectureAnswererService` | `LectureSummaryService` (new) |
| `LectureVerifierService` | Reuse for citation validation |
| `LectureSource` schema | Extend with `source_type: speech/slide/board` |
| `_is_azure_openai_ready()` | Reuse pattern |
| `_call_openai()` | Reuse with summary-specific prompt |
| Local fallback | Replace with ERROR (F1 requirement) |

### Configuration Pattern

```python
# Reuse F4 config pattern
class AzureOpenAIConfig:
    DEFAULT_MODEL = "gpt-4o"
    DEFAULT_API_VERSION = "2024-10-21"
    DEFAULT_TEMPERATURE = 0  # Lower for summarization
    DEFAULT_MAX_TOKENS = 1000
    DEFAULT_TIMEOUT_SECONDS = 30
```

---

## 11. Key Constraints & Decisions

| Constraint | Impact | Recommendation |
|------------|--------|----------------|
| 600 char limit | Short summaries | Focus on key points only |
| gpt-4o model | Fixed model | No model selection needed |
| ERROR when disabled | No fallback | Raise exception if Azure unavailable |
| Evidence tags required | Structured output | Use `response_format: json_object` |
| Multi-source (speech/slide/board) | Complex inputs | Tag each source with type |

---

## Sources

### Azure OpenAI Documentation
- [How to use structured outputs](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/structured-outputs) - Microsoft Learn
- [Chat completions API](https://learn.microsoft.com/ja-jp/azure/cognitive-services/openai/how-to/chatgpt) - Microsoft Learn (Japanese)
- [Azure AI Foundry models](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-models/concepts/models) - Model catalog
- [Quota management](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/quota) - Rate limits

### Token & Cost
- [Token概念讲解](https://www.xmsumi.com/detail/2098) - Token fundamentals
- [Python API真实成本](https://m.blog.csdn.net/LogicNest/article/details/152936958) - Cost analysis
- [Token管理艺术](https://m.blog.csdn.net/m0_72606794/article/details/156464631) - Token optimization

### Prompt Engineering
- [LLM指令微调：文本摘要](https://m.blog.csdn.net/qq_36803941/article/details/140154236) - Text summarization prompts
- [Advanced RAG Techniques](https://tool.lu/ru_RU/article/5SG/detail) - RAG with citations
- [GraphRAG综述](https://blog.csdn.net/2301_79985417/article/details/147349058) - Graph-based RAG

### Error Handling
- [解决RateLimitError](https://m.php.cn/faq/1816131.html) - Rate limit solutions
- [Spring AI RetryClient](https://m.blog.csdn.net/weixin_45422672/article/details/148851722) - Retry patterns

---

## Recommendations for Implementation

1. **Reuse F4 Services**: Adapt `LectureAnswererService` pattern for `LectureSummaryService`
2. **Structured Output**: Use `response_format: {"type": "json_object"}` for citations
3. **Temperature = 0**: For consistent, factual summaries
4. **Token Counting**: Pre-calculate with `tiktoken` before API calls
5. **Error Handling**: Raise exception if Azure unavailable (no fallback per spec)
6. **Citation Format**: Reuse F4's `{"type": "...", "timestamp": "...", "text": "..."}` pattern
7. **Multi-Source Tagging**: Extend schema with `source_type: speech|slide|board`
8. **Monitor Rate Limits**: Check response headers for RPM/TPM

---

## Next Steps for Architect

1. Design `LectureSummaryService` based on F4 patterns
2. Define JSON schema for summary response with citations
3. Plan multi-source aggregation (speech + slide + board)
4. Design error handling (no fallback, raise on Azure unavailable)
