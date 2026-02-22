# Weave Multimodal Features

## Overview

SIT Copilot tracks multimodal data in Weave: images (slides, OCR) and audio metadata (speech). This guide explains how to view and work with this data.

## Image Display in Weave

### How It Works

Weave's `weave.Image` type allows embedding image previews directly in traces:

```python
import weave

# From bytes (JPEG, PNG, etc.)
image = weave.Image.from_bytes(image_bytes)

# Weave automatically:
# 1. Encodes the image
# 2. Stores it with the trace
# 3. Displays it in the UI
```

### OCR with Image Preview

When OCR is performed on a slide or board image, Weave captures both:

1. **Input image**: The visual content
2. **Output text**: Extracted text + confidence

```
Trace: vision_ocr_extract
├─ Input
│  ├─ image_preview: [weave.Image]  <- Visible in UI
│  ├─ source: "azure-vision"
│  └─ timestamp_ms: 12345678
└─ Output
   ├─ ocr_text: "外れ値, 残差確認"
   ├─ ocr_confidence: 0.92
   └─ quality: "high"
```

**Viewing in Weave UI:**

1. Navigate to the trace
2. Click on `vision_ocr_extract`
3. See the input image side-by-side with extracted text
4. Verify OCR accuracy visually

### Slide Transitions with Thumbnails

Each slide transition is tracked with a thumbnail:

```
Trace: slide_transition
├─ Input
│  ├─ slide_image: [weave.Image]  <- Thumbnail preview
│  ├─ slide_number: 5
│  └─ timestamp_ms: 12345678
└─ Output
   └─ ocr_text: "Slide: Linear Regression"
```

**Viewing in Weave UI:**

1. Filter traces by `slide_transition`
2. See a timeline of slide changes
3. Click to view slide thumbnail + OCR text
4. Verify slide change detection worked correctly

## Audio Tracking

### Why Not Store Audio Files?

Audio files are large (MB per minute). Storing them in Weave would:

- Slow down trace browsing
- Exceed storage limits quickly
- Increase network bandwidth

### Audio Metadata Tracking

Instead, we track audio metadata:

```python
await observer.track_speech_event(
    session_id="lec_abc123",
    start_ms=0,
    end_ms=5000,
    text="Corrected text",
    original_text="ASR raw text",
    confidence=0.95,
    is_final=True,
    speaker="lecturer",
    # Note: No audio_bytes - only metadata
)
```

**What's captured:**

- `start_ms` / `end_ms`: Timestamp range
- `text`: Corrected transcription
- `original_text`: Raw ASR output (before correction)
- `confidence`: ASR confidence score
- `is_final`: Final vs intermediate result
- `speaker`: Speaker identifier

**Audio file location:**

- Audio is stored in Azure Blob Storage
- Blob path can be added to metadata if needed
- Weave UI shows transcription, not audio

## Multimodal Trace Examples

### Complete QA Turn with Context

```
Trace: qa_turn (session_id: lec_abc123)
├─ question: "What did the professor say about outliers?"
├─ retrieval
│  ├─ chunk_1: "外れ値の検出には..."
│  └─ chunk_2: "残差プロットを..."
├─ llm_call
│  ├─ prompt: "Answer based on context..."
│  └─ response: "The professor explained..."
└─ answer: "Based on the lecture..."

Linked traces:
├─ vision_ocr_extract (slide 5)
│  └─ [IMAGE: "外れ値, 残差確認"]
├─ speech_to_text (00:15-00:20)
│  └─ "外れ値の検出には箱ひげ図が使えます"
└─ slide_transition (slide 5)
   └─ [IMAGE: slide thumbnail]
```

### Live Lecture Session

```
Session: lec_abc123 (Statistics 101)

Timeline:
00:00 - slide_transition: slide 1
        ├─ [IMAGE: title slide]
        └─ OCR: "統計学基礎"

00:05 - speech_to_text: "今日は統計学の基礎を学びます"
        ├─ text: "Today we learn statistics basics"
        └─ confidence: 0.95

00:30 - vision_ocr_extract
        ├─ [IMAGE: whiteboard with equations]
        └─ OCR: "平均 = Σx/n"

01:00 - qa_turn
        ├─ question: "平均値の求め方を教えて"
        └─ answer: "平均値は全てのデータの合計を..."

... (continues for entire lecture)
```

## Image Size Limits

To avoid overwhelming Weave, images are limited:

```python
# Configuration
WEAVE_MAX_IMAGE_SIZE_BYTES=10485760  # 10MB default

# In code
if (
    settings.weave.capture_images
    and image_bytes
    and len(image_bytes) <= settings.weave.max_image_size_bytes
):
    data["image_preview"] = weave.Image.from_bytes(image_bytes)
```

**Images exceeding the limit:**
- Skipped (not embedded in trace)
- `blob_path` still recorded for reference
- Warning logged at DEBUG level

## Enabling/Disabling Image Capture

### Enable (Demo Mode)

```bash
WEAVE_CAPTURE_IMAGES=true
WEAVE_MAX_IMAGE_SIZE_BYTES=10485760
```

### Disable (Production - Privacy)

```bash
WEAVE_CAPTURE_IMAGES=false
```

When disabled:
- OCR text is still tracked
- Slide transitions are tracked (without image)
- Blob paths are recorded (if available)

## Viewing Multimodal Data

### Local Weave UI

1. Start with `WEAVE_MODE=local`
2. Navigate to http://localhost:8080
3. Browse operations:
   - `vision_ocr_extract` - OCR results with images
   - `slide_transition` - Slide changes with thumbnails
   - `speech_to_text` - Transcription metadata

### Cloud Weave UI

1. Navigate to https://weave.wandb.ai
2. Select project: `sit-copilot-demo`
3. Filter by session_id
4. View multimodal traces

## Best Practices

### For Demo/Development

```bash
WEAVE_CAPTURE_IMAGES=true
WEAVE_CAPTURE_PROMPTS=true
WEAVE_CAPTURE_RESPONSES=true
```

- Full visibility into system behavior
- Image previews for debugging
- All prompts/responses tracked

### For Production

```bash
WEAVE_CAPTURE_IMAGES=false  # Privacy
WEAVE_CAPTURE_PROMPTS=false  # Privacy
WEAVE_CAPTURE_RESPONSES=true  # For quality monitoring
```

- Balance observability with privacy
- Capture aggregated metrics
- Record session IDs for correlation

### For Debugging OCR Issues

1. Enable image capture
2. Reproduce the issue
3. Open Weave UI
4. Find the `vision_ocr_extract` trace
5. Compare input image with extracted text
6. Adjust confidence thresholds if needed

### For Debugging Slide Detection

1. Enable image capture
2. Run a lecture session
3. Filter by `slide_transition`
4. Verify slide thumbnails match actual slides
5. Check `change_score` values
6. Adjust detection threshold if needed

## Privacy Considerations

### Student Data

- Images may contain student faces (board camera)
- Transcriptions contain student speech
- Disable image capture in production

### Instructor Content

- Slides may contain copyrighted material
- Lecture content is IP
- Review retention policy for Weave data

### Recommendations

```bash
# Production settings
WEAVE_CAPTURE_IMAGES=false
WEAVE_CAPTURE_PROMPTS=false
WEAVE_MODE=cloud  # For compliance auditing
```

## Troubleshooting

### Images Not Showing

1. Check `WEAVE_CAPTURE_IMAGES=true`
2. Verify image size < 10MB
3. Check weave version: `uv show weave`
4. Look for errors in logs

### OCR Text Garbled

1. View source image in Weave UI
2. Check `ocr_confidence` score
3. Verify image quality settings
4. Consider preprocessing (contrast, resolution)

### Audio Timing Mismatch

1. Check `start_ms` and `end_ms` values
2. Verify Azure Speech timestamps
3. Compare with video recording
4. Check for clock drift between services
