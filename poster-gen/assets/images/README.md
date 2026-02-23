# Architecture Diagram

This directory contains visual assets for the SIT Copilot poster.

## Architecture Diagram Structure

The architecture diagram should visualize the multi-modal integration flow showing how Speech, Slide, and Question inputs flow through the system.

### Diagram Layout

```
┌─────────────────────────────────────────────────────────────────┐
│                    Multi-Modal Integration Flow                  │
└─────────────────────────────────────────────────────────────────┘

    ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
    │   Speech     │     │    Slide     │     │  Question    │
    │  (Azure SDK) │     │   (Vision)   │     │   (Text)     │
    │   🎤 Audio   │     │   📄 Image   │     │   ❓ Input   │
    └──────┬───────┘     └──────┬───────┘     └──────┬───────┘
           │                    │                     │
           ▼                    ▼                     │
    ┌──────────────┐     ┌──────────────┐             │
    │     ASR      │     │     OCR      │             │
    │  (Japanese)  │     │  (Extraction)│             │
    │   📝 Text    │     │   📝 Text    │             │
    └──────┬───────┘     └──────┬───────┘             │
           │                    │                     │
           └────────┬───────────┘                     │
                    │                                 │
                    ▼                                 │
           ┌──────────────────┐                       │
           │   Azure AI       │                       │
           │    Search        │                       │
           │  (Hybrid + Vec)  │                       │
           │   🔍 Indexing    │                       │
           └────────┬─────────┘                       │
                    │                                 │
                    ▼                                 │
           ┌──────────────────┐                       │
           │  Azure OpenAI    │◄──────────────────────┘
           │   (GPT-4o)       │
           │   🤖 LLM         │
           │   (Answer)       │
           └────────┬─────────┘
                    │
           ┌────────┴────────┐
           ▼                 ▼
    ┌──────────┐      ┌──────────┐
    │ Caption  │      │  Answer  │
    │ Summary  │      │  (with   │
    │(Source-  │      │ Source)  │
    │  tagged) │      └──────────┘
    └──────────┘
```

### Component Details

#### Input Layer
- **Speech Input**: Azure Speech Services SDK for real-time audio capture
- **Slide Input**: Vision API for OCR and image processing
- **Question Input**: Text-based user queries

#### Processing Layer
- **ASR (Automatic Speech Recognition)**: Converts Japanese speech to text with correction
- **OCR (Optical Character Recognition)**: Extracts text from slide images
- **Azure AI Search**: Hybrid search (BM25 + Vector) for semantic retrieval

#### Output Layer
- **Caption Summary**: Real-time rolling summaries with source tagging
- **Q&A Answer**: Context-aware responses with source citations

### Color Coding

| Component | Color | Purpose |
|-----------|-------|---------|
| Speech/Input | Blue (#3B82F6) | Audio processing |
| Slide/Input | Purple (#8B5CF6) | Image processing |
| Question/Input | Pink (#EC4899) | User interaction |
| ASR/Processing | Teal (#14B8A6) | Speech recognition |
| OCR/Processing | Amber (#F59E0B) | Text extraction |
| Search/Indexing | Indigo (#6366F1) | Semantic search |
| LLM/Generation | Purple (#8B5CF6) | Text generation |
| Caption/Output | Green (#10B981) | Real-time output |
| Answer/Output | Blue (#3B82F6) | Q&A response |

### Flow Metrics

| Flow | Latency | Accuracy |
|------|---------|----------|
| Captioning | 2.8s | 87% |
| Q&A | 4.2s | 92% |
| OCR | N/A | 94% |

### Notes for Image Creation

1. **Format**: PNG at 300 DPI for print quality
2. **Dimensions**: Should scale to fit the A0 poster section (approximately 30" wide x 8" tall)
3. **Style**: Clean, flat design with rounded corners
4. **Font**: Noto Sans JP for Japanese text, Inter for English
5. **Background**: Transparent or light gray (#F3F4F6)

### Placeholder

While an actual image is being created, the poster generation system will render a text-based placeholder.
