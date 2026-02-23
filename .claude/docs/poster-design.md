# SIT Copilot Poster Design Document

## Overview

A0-size presentation-quality poster for AI Innovators Cup @ Shibaura 2026 competition.

**Goal**: Showcase SIT Copilot - a lecture support AI system with real-time captioning, live Q&A, and multi-modal integration.

**Size**: A0 Portrait (841 x 1189 mm / 33.1 x 46.8 inches)

---

## Layout Architecture

### Grid System

- **12-column grid** with 6mm gutters
- **8mm row baseline** for vertical rhythm
- **25mm outer margins** on all sides
- **Content area**: 791 x 1139 mm

### Section Layout

```
┌─────────────────────────────────────────────────────────────┐
│  Header (170mm height)                                       │
│  - Title: SIT Copilot                                       │
│  - Subtitle: AI-Powered Lecture Support System             │
│  - Authors, Affiliation, Logos                              │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─────────────────────┬─────────────────────────────────┐ │
│  │ 1. Background       │ 2. Objectives                    │ │
│  │ (5 columns)         │ (7 columns)                      │ │
│  │ - Problem statement │ - Real-time captioning          │ │
│  │ - Target audience   │ - Live Q&A with context         │ │
│  │                     │ - Source-only answers           │ │
│  ├─────────────────────┴─────────────────────────────────┤ │
│  │                                                           │ │
│  │ 3. AI Usage & Application Method (12 columns - HERO)     │ │
│  │ ┌─────────────────────────────────────────────────┐     │ │
│  │ │           Multi-Modal Integration Flow           │     │ │
│  │ │  Speech ──┬──► ASR ──┬──► LLM ──┬──► Caption    │     │ │
│  │ │            │          │         │               │     │ │
│  │ │  Slide ───┴──► OCR ───┘         ├──► Summary    │     │ │
│  │ │                                    │              │     │ │
│  │ │  Question ─────────────────────────┴──► Answer    │     │ │
│  │ └─────────────────────────────────────────────────┘     │ │
│  │                                                           │ │
│  │ ┌─────────────────┬─────────────────┬──────────────┐    │ │
│  │ │ Captioning Flow │  Q&A Flow       │ OCR Flow     │    │ │
│  │ │ (with KPIs)     │ (with evidence) │ (with ROI)   │    │ │
│  │ └─────────────────┴─────────────────┴──────────────┘    │ │
│  │                                                           │ │
│  ├─────────────────────────────────────────────────────────┤ │
│  │                                                           │ │
│  │ 4. Results & Output (8 columns) │ 5. Future Plans (4)  │ │
│  │ - KPI metrics display           │ - Enhanced NLP       │ │
│  │ - Model performance             │ - Multi-language    │ │
│  │ - Prompt design examples        │ - Analytics         │ │
│  │ - Demo video QR code            │                     │ │
│  │                                 │                     │ │
│  └─────────────────────────────────┴─────────────────────┘ │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### Reading Flow

1. Title → Problem → Solution (Background/Objectives)
2. How it works (AI Usage - visual center)
3. Proof it works (Results with metrics)
4. What's next (Future Plans + QR code)

---

## Typography

### Font Sizes (for A0 at 1-2m viewing distance)

| Element | Size | Weight | Font Family |
|---------|------|--------|-------------|
| Title | 120-140pt | Bold | Noto Sans JP |
| Subtitle | 72-80pt | Medium | Noto Sans JP |
| Authors | 48-56pt | Regular | Noto Sans JP |
| Section Headers | 64-72pt | Bold | Noto Sans JP |
| Body Text | 30-34pt | Regular | Noto Sans JP |
| Captions | 24-26pt | Regular | Noto Sans JP |

### Font Family

- **Primary**: Noto Sans JP (Google Fonts - Japanese support)
- **English/Numbers**: Inter (fallback)
- **Monospace**: JetBrains Mono (for code/prompts)

---

## Color Palette

### Technical Blue Theme

| Role | Color | Hex | Usage |
|------|-------|-----|-------|
| Primary | Dark Navy | `#0F2742` | Headers, backgrounds |
| Secondary | Blue | `#1F6FEB` | Flow diagrams, links |
| Secondary2 | Teal | `#14B8A6` | Q&A flow, accents |
| Accent | Amber | `#F59E0B` | KPIs, highlights (max 10%) |
| Text | Dark Gray | `#1F2937` | Body text |
| Background | Light Gray | `#F7F9FC` | Poster background |
| Border | Medium Gray | `#E5E7EB` | Section borders |

### Accessibility

- **Contrast ratio**: All text meets WCAG AA (4.5:1)
- **Colorblind friendly**: Avoid red-green combinations
- **Patterns + colors**: For data visualization

---

## Content Structure

### 1. Header Section

```
┌─────────────────────────────────────────────────────────────┐
│  SIT Copilot                                      [Logo]     │
│  AI-Powered Lecture Support System                         │
│                                                               │
│  [Author Names]                         [Affiliation Logo] │
│  Shibaura Institute of Technology                           │
└─────────────────────────────────────────────────────────────┘
```

### 2. Background (5 columns)

**Problem Statement**
- Lectures are information-dense and fast-paced
- Students miss key points while taking notes
- Non-native speakers struggle with real-time comprehension
- Existing tools lack lecture-specific context

**Target Audience**
- University students (especially non-native speakers)
- Lecture attendees with accessibility needs
- Instructors wanting to enhance engagement

### 3. Objectives (7 columns)

**Core Features**
1. **Real-time Captioning**: Instant speech-to-text with source tracking
2. **Live Q&A**: Context-aware answers using slide content
3. **Source-Only Responses**: Citations prevent misinformation
4. **Multi-Modal Input**: Voice, text, and visual (slide OCR)
5. **Accessibility**: Adjustable fonts, high contrast, easy Japanese

**Technical Objectives**
- < 3s latency for caption generation
- < 5s latency for Q&A responses
- > 85% ASR accuracy after correction
- > 90% QA answer relevance

### 4. AI Usage & Application Method (HERO Section)

#### Multi-Modal Integration Flow (Central Diagram)

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Speech     │     │    Slide     │     │  Question    │
│  (Azure SDK) │     │   (Vision)   │     │   (Text)     │
└──────┬───────┘     └──────┬───────┘     └──────┬───────┘
       │                    │                     │
       ▼                    ▼                     │
┌──────────────┐     ┌──────────────┐             │
│     ASR      │     │     OCR      │             │
│  (Japanese)  │     │  (Extraction)│             │
└──────┬───────┘     └──────┬───────┘             │
       │                    │                     │
       └────────┬───────────┘                     │
                │                                 │
                ▼                                 │
       ┌──────────────────┐                      │
       │   Azure AI       │                      │
       │    Search        │                      │
       │  (Hybrid + Vec)  │                      │
       └────────┬─────────┘                      │
                │                                 │
                ▼                                 │
       ┌──────────────────┐                      │
       │  Azure OpenAI    │◄─────────────────────┘
       │   (GPT-4o)       │
       └────────┬─────────┘
                │
       ┌────────┴────────┐
       ▼                 ▼
┌──────────┐      ┌──────────┐
│ Caption  │      │  Answer  │
│ Summary  │      │  (with   │
│ (Source- │      │ Source)  │
│  tagged) │      └──────────┘
└──────────┘
```

#### Feature Breakdown (3 Mini-Sections)

**Captioning Flow**
- Real-time ASR with Japanese correction
- Evidence tags: 🎤 Speech | 📄 Slide | 📝 Board
- Rolling summaries every 30s
- KPI: 2.8s avg latency, 87% accuracy

**Q&A Flow**
- BM25 + Hybrid search for relevance
- Context from slides + transcript
- Source verification prevents hallucination
- KPI: 4.2s avg latency, 92% relevance

**OCR Flow**
- 1 FPS capture with change detection
- ROI support (slide area only)
- Quality filtering by confidence
- KPI: 94% extraction success

#### Prompt Engineering Examples

Show 2-3 concise prompt examples:

```
Captioning:
"Summarize the last 60 seconds of lecture content.
Group related points. Mark sources: [Speech], [Slide],
[Blackboard]. Max 150 words."

Q&A:
"Using ONLY the provided lecture transcript and slide
text, answer the question. Cite sources with (chunk_id).
If information is insufficient, say 'I cannot answer
from the available materials'."
```

### 5. Results & Output (8 columns)

#### Model Performance (25pts - Highlight!)

**Metrics Display**
```
┌────────────────────────────────────────────────────────┐
│  Model Performance                                     │
│                                                         │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐      │
│  │ ASR Accuracy│  │ QA Relevance│ │ OCR Success │      │
│  │    87%     │  │    92%     │  │    94%     │      │
│  └────────────┘  └────────────┘  └────────────┘      │
│                                                         │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐      │
│  │Caption Lat. │  │  QA Lat.   │  │ Citation   │      │
│  │   2.8s     │  │   4.2s     │  │  Accuracy  │      │
│  └────────────┘  └────────────┘  │    96%     │      │
│                                  └────────────┘      │
└────────────────────────────────────────────────────────┘
```

**Key Achievements**
- Real-time multi-modal processing (3 streams)
- Source verification prevents misinformation
- Accessibility features: font scaling, high contrast
- Observability: WandB Weave for all operations

#### Prompt Design (20pts - Highlight!)

**Innovation Highlights**
- Dynamic context window (last 60s for summaries)
- Evidence source tracking for trust
- Fallback mechanisms for insufficient data
- Language switching (Japanese ↔ English)

**Prompt Iteration**
1. **Initial**: Basic summarization
2. **V2**: Added source tracking
3. **V3**: Evidence tag optimization
4. **Final**: Dynamic context + fallback

#### Demo Video QR Code

```
┌──────────────────┐
│                  │
│   [QR CODE]      │  Scan to watch 3-min demo
│                  │  See SIT Copilot in action!
│                  │
│  Demo Video      │
└──────────────────┘
```

### 6. Future Plans (4 columns)

**Short-term**
- Enhanced NLP: Key term extraction
- Multi-language support (EN, ZH)
- Usage analytics dashboard

**Long-term**
- Integration with LMS platforms
- Mobile app for students
- Offline mode with local models

---

## Code Architecture

### Directory Structure

```
poster-gen/
├── src/
│   ├── domain/
│   │   ├── schema.ts          # Zod schemas for poster content
│   │   └── types.ts           # TypeScript types
│   ├── layout/
│   │   ├── a0.ts              # A0 dimensions and grid
│   │   └── grid.ts            # Grid system utilities
│   ├── theme/
│   │   ├── colors.ts          # Color palette
│   │   └── typography.ts      # Font sizes and families
│   ├── components/
│   │   ├── primitives/        # Text, box, image
│   │   ├── sections/          # Background, objectives, etc.
│   │   └── header.ts          # Poster header
│   ├── renderer/
│   │   ├── pptx-adapter.ts    # PptxGenJS wrapper
│   │   └── renderer.ts        # Main render orchestrator
│   └── app/
│       ├── cli.ts             # Command-line interface
│       └── generate.ts        # Entry point
├── posters/
│   └── sit-copilot.json       # Poster content data
├── assets/
│   ├── images/                # Screenshots, diagrams
│   └── logos/                 # University, project logos
├── package.json
├── tsconfig.json
└── vite.config.ts
```

### Component Contract

All components follow this interface:

```typescript
interface Component {
  measure(): Box;              // Calculate dimensions
  render(box: Box): void;      // Render to PptxGenJS
}

interface Box {
  x: number;  // inches
  y: number;
  w: number;
  h: number;
}
```

### Content Schema (JSON)

```typescript
const posterContent = {
  meta: {
    title: "SIT Copilot",
    subtitle: "AI-Powered Lecture Support System",
    authors: ["Author 1", "Author 2"],
    affiliation: "Shibaura Institute of Technology",
    date: "2026-02-24"
  },
  sections: {
    background: { ... },
    objectives: { ... },
    aiUsage: { ... },
    results: { ... },
    futurePlans: { ... }
  },
  theme: "technical-blue",  // or "minimal", "academic"
  layout: "3-column"
};
```

---

## Implementation Phases

### Phase 1: Setup (1 hour)
- [ ] Initialize TypeScript project with Vite
- [ ] Install PptxGenJS and dependencies
- [ ] Set up project structure
- [ ] Configure build tooling

### Phase 2: Foundation (2.5 hours)
- [ ] Implement A0 layout constants
- [ ] Create grid system utilities
- [ ] Define theme (colors, typography)
- [ ] Create content schema with Zod

### Phase 3: Components (4 hours)
- [ ] Implement primitive components (text, box, image)
- [ ] Implement section components
- [ ] Implement header component
- [ ] Create component library

### Phase 4: Content (3 hours)
- [ ] Create poster content JSON
- [ ] Design architecture diagram
- [ ] Prepare screenshots/images
- [ ] Write copy for all sections

### Phase 5: Integration (2.5 hours)
- [ ] Build PptxGenJS adapter
- [ ] Implement render orchestrator
- [ ] Create CLI interface
- [ ] Add validation and error handling

### Phase 6: Polish (2 hours)
- [ ] Visual tuning and spacing adjustments
- [ ] Color and typography refinement
- [ ] Add QR code generation
- [ ] Export and print preparation

**Total Estimate**: 15-18 hours

---

## Dependencies

```json
{
  "dependencies": {
    "pptxgenjs": "^3.12.0",
    "zod": "^3.22.0"
  },
  "devDependencies": {
    "typescript": "^5.3.0",
    "vite": "^5.0.0",
    "tsx": "^4.7.0",
    "@types/node": "^20.10.0"
  }
}
```

---

## Deliverables

1. **A0 PowerPoint file** (`sit-copilot-poster.pptx`)
2. **Source code** in `poster-gen/` directory
3. **Content JSON** for easy updates
4. **Export PDF** for printing
5. **Documentation** (README.md)

---

## References

- AI Innovators Cup Requirements (PDF)
- PptxGenJS Documentation: https://gitbrent.github.io/PptxGenJS/
- Award-winning poster examples (research results)
- C4 Model for architecture diagrams
