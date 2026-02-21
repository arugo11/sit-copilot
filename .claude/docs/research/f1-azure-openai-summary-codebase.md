# F1 Lecture Summary - Azure OpenAI Integration Codebase Analysis

Date: 2026-02-21
Task: Analyze existing F1 summary implementation and Azure OpenAI patterns from F4 QA

---

## 1. Current F1 Summary Implementation

### 1.1 Service Layer: `app/services/lecture_summary_service.py`

**Current Approach: Deterministic Rule-Based Summary**

- **NO Azure OpenAI integration** - purely deterministic concatenation
- 30-second sliding windows (`WINDOW_SIZE_MS = 30_000`)
- 60-second lookback for context (`LOOKBACK_MS = 60_000`)

**Key Methods:**

| Method | Current Implementation |
|--------|----------------------|
| `_build_summary_text()` | Concatenates speech + visual text with template strings |
| `_build_evidence()` | Returns last 3 speech + 3 visual event IDs |
| `_build_key_terms()` | Simple tokenization via regex (`re.split()`) + deduplication |

**Summary Text Pattern (Current):**
```python
# Line 297-313
if speech_text and visual_text:
    summary = f"この区間では、{speech_text}。視覚情報では {visual_text} が確認されました。"
elif speech_text:
    summary = f"この区間では、{speech_text}"
elif visual_text:
    summary = f"この区間では、視覚情報として {visual_text} が確認されました。"
else:
    summary = "この区間の要約を生成できるデータがありません。"
```

**Key Limitations:**
- No semantic understanding
- No redundancy elimination
- No lecture-style structuring (definitions, examples, emphasis)
- Simple text concatenation with truncation (`MAX_SUMMARY_CHARS = 600`)

### 1.2 Data Models Used

| Model | Fields Used | Purpose |
|-------|-------------|---------|
| `SpeechEvent` | `text`, `start_ms`, `end_ms`, `is_final` | Speech transcription source |
| `VisualEvent` | `ocr_text`, `timestamp_ms`, `source`, `quality` | OCR text from slides/board |
| `SummaryWindow` | `summary_text`, `key_terms_json`, `evidence_event_ids_json` | Persisted summary |

### 1.3 API Endpoint

```
GET /api/v4/lecture/summary/latest
  -> SqlAlchemyLectureSummaryService.get_latest_summary()
  -> Returns LectureSummaryLatestResponse
```

### 1.4 Test Structure: `tests/unit/services/test_lecture_summary_service.py`

- 5 test cases covering persistence, no_data, rebuild, ownership, concurrency
- Tests deterministic behavior only

---

## 2. Azure OpenAI Patterns (Reusable from F4 QA)

### 2.1 Answerer Service: `app/services/lecture_answerer_service.py`

**Architecture:**
```python
class AzureOpenAILectureAnswererService:
    def __init__(self, api_key, endpoint, model, ...):
        self._api_key = api_key
        self._endpoint = endpoint
        self._model = model
        ...
```

**Key Patterns to Reuse:**

1. **Azure OpenAI Readiness Check:**
```python
def _is_azure_openai_ready(self) -> bool:
    if not self._api_key.strip(): return False
    if not self._endpoint.strip(): return False
    return "openai.azure.com" in self._endpoint.lower()
```

2. **Chat Completion URL Builder:**
```python
def _build_chat_completion_url(self) -> str:
    endpoint = self._endpoint.rstrip("/")
    deployment = quote(self._model.strip(), safe="")
    return f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version={self._api_version}"
```

3. **Async HTTP Call Pattern:**
```python
async def _call_openai(self, prompt: str) -> str:
    url = self._build_chat_completion_url()
    payload = {
        "messages": [
            {"role": "system", "content": "..."},
            {"role": "user", "content": prompt},
        ],
        "temperature": self._temperature,
        "max_tokens": self._max_tokens,
    }
    def _run_request() -> str:
        with urlopen(request, timeout=self._timeout_seconds) as response:
            return response.read().decode("utf-8")
    raw = await asyncio.to_thread(_run_request)  # Non-blocking
```

4. **Local Fallback Pattern:**
```python
if not self._is_azure_openai_ready():
    return self._build_local_fallback_answer(sources)
```

### 2.2 Verifier Service: `app/services/lecture_verifier_service.py`

**Additional Pattern: JSON Response Mode**
```python
payload["response_format"] = {"type": "json_object"}  # For structured output
```

### 2.3 Config: `app/core/config.py`

**Azure OpenAI Settings (Already Defined):**
```python
azure_openai_enabled: bool = False
azure_openai_api_key: str = ""
azure_openai_endpoint: str = ""
azure_openai_model: str = "gpt-4o"
```

---

## 3. What Needs to Be Added for F1 Azure OpenAI Summary

### 3.1 New Service: `LectureSummaryGeneratorService`

**Suggested Structure:**
```python
class LectureSummaryGeneratorService(Protocol):
    async def generate_summary(
        self,
        speech_events: list[SpeechEvent],
        visual_events: list[VisualEvent],
        lang_mode: str,
    ) -> str:
        """Generate LLM-powered summary."""
        ...

class AzureOpenAILectureSummaryGeneratorService:
    """Reuses AnswererService patterns."""
    
    DEFAULT_MODEL = "gpt-4o"
    DEFAULT_MAX_TOKENS = 800
    DEFAULT_TEMPERATURE = 0.5  # Lower for factual summary
    
    def __init__(self, api_key, endpoint, model, ...):
        # Same as AnswererService
    
    async def generate_summary(self, speech_events, visual_events, lang_mode):
        # Build prompt with speech + visual context
        # Call Azure OpenAI
        # Fallback to current deterministic method if unavailable
```

### 3.2 Prompt Engineering Requirements

**Summary Prompt Should:**
1. Aggregate speech + visual events into coherent narrative
2. Identify key terms (concepts, definitions)
3. Extract evidence (timestamps, visual references)
4. Respect 30-second window context
5. Support language modes (ja, easy-ja, en)

**Prompt Structure:**
```python
prompt = f"""あなたは講義の30秒区間を要約するアシスタントです。

以下の講義記録（音声転写 + 板書/スライドのOCR）を要約してください。

【音声転写】
{speech_text}

【視覚情報（板書/スライド）】
{visual_text}

ガイドライン:
- 重要な概念や定義を抽出してください
- 簡潔な要約（2-3文）を作成してください
- 時系列を意識して構成してください
"""
```

### 3.3 Key Term Extraction Enhancement

**Current:** Regex-based tokenization
**Proposed:** LLM-based extraction with categorization

```python
@dataclass
class ExtractedKeyTerm:
    term: str
    category: Literal["definition", "concept", "example", "formula"]
    evidence_type: LectureEvidenceType
```

### 3.4 Configuration Updates Needed

Already available in `config.py`:
- `azure_openai_enabled`
- `azure_openai_api_key`
- `azure_openai_endpoint`
- `azure_openai_model`

**May Add:**
- `lecture_summary_max_tokens: int = 800`
- `lecture_summary_temperature: float = 0.5`

---

## 4. Integration Strategy

### 4.1 Modify `SqlAlchemyLectureSummaryService._build_summary_text()`

**Current:**
```python
@staticmethod
def _build_summary_text(*, speech_events, visual_events) -> str:
    # Deterministic concatenation
```

**Proposed:**
```python
def __init__(self, db: AsyncSession, summary_generator: LectureSummaryGeneratorService):
    self._db = db
    self._summary_generator = summary_generator

async def _build_summary_text(self, *, speech_events, visual_events, lang_mode) -> str:
    return await self._summary_generator.generate_summary(
        speech_events=speech_events,
        visual_events=visual_events,
        lang_mode=lang_mode,
    )
```

### 4.2 Dependency Injection in `app/api/v4/lecture.py`

```python
def get_lecture_summary_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LectureSummaryService:
    summary_generator = AzureOpenAILectureSummaryGeneratorService(
        api_key=settings.azure_openai_api_key,
        endpoint=settings.azure_openai_endpoint,
        model=settings.azure_openai_model,
    )
    return SqlAlchemyLectureSummaryService(
        db=db,
        summary_generator=summary_generator,
    )
```

### 4.3 Fallback Behavior

Maintain current deterministic summary as fallback:
```python
async def generate_summary(self, speech_events, visual_events, lang_mode):
    if not self._is_azure_openai_ready():
        return self._build_deterministic_summary(speech_events, visual_events)
    # LLM-based generation
```

---

## 5. Key Files Summary

| File | Current State | Required Action |
|------|--------------|-----------------|
| `app/services/lecture_summary_service.py` | Deterministic only | Add LLM generator dependency |
| `app/services/lecture_answerer_service.py` | Azure OpenAI patterns | **Reuse** for summary generator |
| `app/services/lecture_verifier_service.py` | Azure OpenAI patterns | Reference for JSON mode |
| `app/core/config.py` | Azure OpenAI settings | Already configured |
| `app/schemas/lecture.py` | Summary schemas | Add lang_mode if needed |
| `app/api/v4/lecture.py` | Summary endpoint | Add generator DI |
| `tests/unit/services/test_lecture_summary_service.py` | Deterministic tests | Add LLM mock tests |

---

## 6. Success Criteria

- [ ] Azure OpenAI generates coherent 30-second summaries
- [ ] Fallback to deterministic when Azure unavailable
- [ ] `azure_openai_enabled=False` keeps deterministic behavior
- [ ] Tests pass with mocked Azure OpenAI calls
- [ ] No breaking changes to existing API contract
