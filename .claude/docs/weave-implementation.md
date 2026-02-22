# WandB Weave Implementation Guide

## Overview

This guide explains how WandB Weave is integrated into SIT Copilot for LLM and session observability.

## What is Weave?

WandB Weave is a toolkit for LLM application observability. It provides:

- **Trace tracking**: Track LLM calls and their relationships
- **Evaluation**: Compare different prompts and models
- **Debugging**: Inspect inputs and outputs for each operation
- **Visualization**: View traces in a web UI

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     FastAPI App                          │
│  ┌───────────────────────────────────────────────────┐  │
│  │              lifespan() context manager            │  │
│  │  ┌─────────────────────────────────────────────┐  │  │
│  │  │  WeaveDispatcher (background workers)       │  │  │
│  │  │  - Non-blocking queue                        │  │  │
│  │  │  - 2 workers (configurable)                  │  │  │
│  │  │  - Timeout enforcement                       │  │  │
│  │  └─────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────┘  │
│                         │                                │
│                         ▼                                │
│  ┌───────────────────────────────────────────────────┐  │
│  │         WandBWeaveObserverService                 │  │
│  │  - track_qa_turn()                                │  │
│  │  - track_llm_call()                               │  │
│  │  - track_ocr_with_image()                         │  │
│  │  - track_slide_transition()                       │  │
│  │  - track_speech_event()                           │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│                    WandB Weave                          │
│  - Local mode: Embedded HTTP server                    │
│  - Cloud mode: Data sent to weave.wandb.ai             │
└─────────────────────────────────────────────────────────┘
```

## Observer Pattern

The observer pattern allows business logic to record observability data without being blocked:

1. **Protocol-based**: `WeaveObserverService` defines the interface
2. **No-op fallback**: `NoopWeaveObserverService` does nothing (when disabled)
3. **Fire-and-forget**: All `track_*` methods return immediately
4. **Error isolation**: Observer failures never crash the app

## Dispatcher Pattern

The `WeaveDispatcher` provides non-blocking operation:

1. **Queue-based**: Operations are queued to background workers
2. **Overflow handling**: Full queue = dropped observation (logged)
3. **Timeout**: Long-running observations are cancelled
4. **Graceful shutdown**: Drains queue with timeout on app stop

## Configuration

Weave is configured via environment variables with the `WEAVE_` prefix:

```bash
# Enable/disable Weave (default: true for demo)
WEAVE_ENABLED=true

# Project name in Weave
WEAVE_PROJECT=sit-copilot-demo

# Mode: local or cloud
WEAVE_MODE=local

# Cloud authentication (only for cloud mode)
WEAVE_API_KEY=your-wandb-api-key
WEAVE_ENTITY=your-entity  # Optional

# Data capture settings (demo: all enabled)
WEAVE_CAPTURE_PROMPTS=true
WEAVE_CAPTURE_RESPONSES=true
WEAVE_CAPTURE_IMAGES=true
WEAVE_MAX_IMAGE_SIZE_BYTES=10485760  # 10MB

# Performance tuning
WEAVE_QUEUE_MAXSIZE=1000
WEAVE_WORKER_COUNT=2
WEAVE_TIMEOUT_MS=5000
WEAVE_SAMPLE_RATE=1.0
```

## Usage

### Enabling Weave

#### Local Mode (Development)

```bash
# .env or .env.azure.generated
WEAVE_ENABLED=true
WEAVE_MODE=local
WEAVE_PROJECT=sit-copilot-demo
WEAVE_CAPTURE_PROMPTS=true
WEAVE_CAPTURE_RESPONSES=true
WEAVE_CAPTURE_IMAGES=true
```

Start the server:

```bash
uv run uvicorn app.main:app
```

Weave UI will be available at: http://localhost:8080

#### Cloud Mode (Production)

```bash
# Store API key in Key Vault (see deployment guide)
export WEAVE_ENABLED=true
export WEAVE_MODE=cloud
export WEAVE_PROJECT=sit-copilot-prod
export WEAVE_API_KEY=your-wandb-api-key
```

View traces at: https://weave.wandb.ai

### Disabling Weave

```bash
export WEAVE_ENABLED=false
```

This uses `NoopWeaveObserverService` (zero overhead).

## Observed Services

### Lecture QA Service

Tracks question-answer turns:

```python
await observer.track_qa_turn(
    session_id="lec_abc123",
    feature="lecture-qa",
    question="What is machine learning?",
    answer="Machine learning is...",
    confidence="high",
    citations=[{"text": "...", "chunk_id": "..."}],
    retrieved_chunk_ids=["chunk1", "chunk2"],
    latency_ms=1250,
    verifier_supported=True,
    outcome_reason="sufficient_context",
)
```

### LLM Calls

Tracks individual LLM API calls:

```python
await observer.track_llm_call(
    provider="azure-openai",
    model="gpt-4o",
    prompt="Generate answer for...",
    response="Based on the lecture...",
    latency_ms=850,
    tokens_prompt=150,
    tokens_completion=200,
    metadata={"session_id": "lec_abc123"},
)
```

### OCR with Image

Tracks vision OCR with image preview:

```python
await observer.track_ocr_with_image(
    session_id="lec_abc123",
    timestamp_ms=12345678,
    source="azure-vision",
    ocr_text="外れ値, 残差確認",
    ocr_confidence=0.92,
    quality="high",
    change_score=0.85,
    image_bytes=b"\xff\xd8...",  # JPEG bytes
    blob_path="azure://container/slide.jpg",
)
```

### Slide Transitions

Tracks slide changes:

```python
await observer.track_slide_transition(
    session_id="lec_abc123",
    timestamp_ms=12345678,
    slide_number=5,
    ocr_text="Slide title: Linear Regression",
    image_bytes=b"\xff\xd8...",  # Slide thumbnail
    blob_path="azure://container/slide_5.jpg",
)
```

### Speech Events

Tracks ASR transcription:

```python
await observer.track_speech_event(
    session_id="lec_abc123",
    start_ms=0,
    end_ms=5000,
    text="Machine learning models learn patterns.",
    original_text="Machine learning models learn pattern.",  # ASR raw
    confidence=0.95,
    is_final=True,
    speaker="lecturer",
)
```

## Session Context

For operations that should be grouped under a session:

```python
async with observer.with_session_context(session_id="lec_abc123"):
    # All operations here inherit session context
    await observer.track_qa_turn(...)
    await observer.track_llm_call(...)
```

## Trace Structure

```
lecture.session:lec_abc123
├─ qa.ask
│  ├─ retrieval.search (BM25 or Azure AI Search)
│  └─ llm.answer.generate (Azure OpenAI)
│     └─ llm.call (raw API call)
├─ qa.followup
│  ├─ retrieval.search
│  └─ llm.answer.generate
├─ vision_ocr_extract
│  ├─ input: image (weave.Image)
│  └─ output: ocr_text + confidence
├─ slide_transition
│  └─ input: slide_image (weave.Image)
└─ speech_to_text
   ├─ input: audio_metadata (path, duration)
   └─ output: text + confidence
```

## Viewing Traces in Weave UI

### Local Mode

1. Start server with `WEAVE_MODE=local`
2. Navigate to http://localhost:8080
3. Browse traces by operation name
4. Click on a trace to see details

### Cloud Mode

1. Log in to https://weave.wandb.ai
2. Select your project (`sit-copilot-demo` or `sit-copilot-prod`)
3. Filter by `session_id` or operation type
4. View multimodal data (images, text)

## Debugging

### Check if Weave is enabled

```python
from app.core.config import settings
print(f"Weave enabled: {settings.weave.enabled}")
print(f"Weave mode: {settings.weave.mode}")
```

### View dispatcher status

```python
# In app lifecycle
dispatcher = getattr(weave_observer, "_dispatcher_value", None)
if dispatcher:
    print(f"Queue size: {dispatcher._queue.qsize()}")
    print(f"Running: {dispatcher._running}")
```

### Logs

Weave logs at `DEBUG` level:

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG

# Look for:
# - "Weave initialized"
# - "WeaveDispatcher started"
# - "Weave queue full"
# - "Weave observation timeout"
```

## Performance Impact

- **Disabled**: Zero overhead (noop implementation)
- **Enabled, local mode**: ~5-10ms per operation (background processing)
- **Enabled, cloud mode**: ~10-50ms per operation (network I/O)

The dispatcher ensures request handlers are never blocked by observability.

## Security Notes

- **Prompts/Responses**: Can be disabled with `WEAVE_CAPTURE_PROMPTS=false`
- **Images**: Limited to 10MB by default (`WEAVE_MAX_IMAGE_SIZE_BYTES`)
- **PII**: Review data capture settings for production
- **API Keys**: Store in Azure Key Vault for production

## Troubleshooting

### Weave UI not showing data

1. Check `WEAVE_ENABLED=true`
2. Verify `weave.init()` was called (check startup logs)
3. Check dispatcher is running
4. Verify operations are being called (add debug logging)

### Queue full warnings

- Increase `WEAVE_QUEUE_MAXSIZE`
- Increase `WEAVE_WORKER_COUNT`
- Reduce observation frequency with `WEAVE_SAMPLE_RATE`

### Import errors

```bash
# Install weave
uv add weave

# Or install all optional dependencies
uv sync --all-extras
```
