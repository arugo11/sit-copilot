# Poster Creation Research Summary

## PptxGenJS Advanced Features

### Custom Slide Size for A0 Poster
```javascript
let pptx = new PptxGenJS();
// A0 size: 33.1 x 46.8 inches
pptx.layout = { name: 'A0', width: 33.1, height: 46.8 };
```

### Master Slides and Templates
```javascript
pptx.defineSlideMaster({
  title: 'POSTER_MASTER',
  background: { color: 'F1F1F1' },
  objects: [
    {
      image: { x: 31, y: 45, w: 1.5, h: 1.5, path: 'path/to/logo.png' }
    },
    {
      text: {
        text: 'University Name - Department',
        options: { x: 0, y: 46, w: '100%', align: 'center', color: 'A9A9A9', fontSize: 18 }
      }
    }
  ],
});

// To use it:
let slide = pptx.addSlide({ masterName: 'POSTER_MASTER' });
```

### Image Positioning and Sizing
```javascript
slide.addImage({
  path: 'path/to/figure1.jpg',
  x: 1,      // 1 inch from the left
  y: 5,      // 5 inches from the top
  w: 15,     // 15 inches wide
  h: 10      // 10 inches high
});
```

### Text Formatting
```javascript
// Poster Title
slide.addText('The Impact of Climate Change on Marine Ecosystems', {
  x: 1, y: 1, w: 31.1, h: 3,
  fontSize: 88,
  fontFace: 'Arial',
  bold: true,
  align: 'center',
  valign: 'middle'
});

// Section Body
slide.addText('...', {
  x: 1, y: 15, w: 15, h: 20,
  fontSize: 24,
  fontFace: 'Calibri',
  align: 'left'
});
```

### Shape Objects
```javascript
// A horizontal line to separate title from content
slide.addShape(pptx.shapes.LINE, {
  x: 1, y: 4, w: 31.1, h: 0,
  line: { color: '0000FF', width: 3 }
});

// A background box for a "Key Findings" section
slide.addShape(pptx.shapes.RECTANGLE, {
  x: 16.5, y: 25, w: 15.6, h: 10,
  fill: { color: 'EFEFEF' }
});
```

### Color Schemes and Themes
```javascript
const COLORS = {
  primary: '0B3D91', // Dark Blue
  accent: 'FFC20E', // Yellow
  text: '333333',
  background: 'F8F9FA'
};

slide.addText('Important Note', { color: COLORS.primary, ... });
```

## Award-Winning Academic Poster Design

### Layout Patterns
- **3-Column Layout**: Most common and effective format for academic posters
- **Grid Systems**: Maintain alignment and consistency
- **Modular Design**: Think of poster in terms of blocks (Introduction, Methods, Results, Conclusion)

### Color Schemes for Technical/Academic Audiences
- **Simple & Consistent**: Limit palette to 2-3 main colors
- **High Contrast**: Black/dark gray text on white background
- **Institutional Branding**: Use university or company brand colors
- **AI-Assisted Palettes**: Tools like Adobe Color or Coolors

### Visual Hierarchy Best Practices
- **Title is Key**: Largest text element, readable from several meters away
- **Clear Headings**: Use size, weight, and color for distinction
- **Billboard Test**: Main takeaway should be understood in seconds
- **Strategic Use of Space**: Don't fear white space

### Typography Choices
- **Font Families**:
  - Sans-serif (Helvetica, Arial, Futura, Lato, Montserrat) - preferred
  - Limit to 1-2 font families
- **Font Sizes**:
  - Title: 85pt or larger
  - Author/Affiliation: 56pt
  - Section Headers: 36pt
  - Body Text: 24pt (minimum)
  - Captions: 18pt

### Balance Text and Visuals
- **50/50 Split**: Ideal balance between text and visuals
- **Wall of Text is the Enemy**: Aim for ~250 words total
- **Visuals Should Tell the Story**: Use charts, graphs, diagrams
- **Central Graphic**: Large, compelling eye-catcher in center

### Common Design Elements in Award-Winning Posters
- Clear takeaway message
- QR codes for full paper, GitHub repo, demo
- Author photos and affiliation logos
- Logical flow: Problem -> Solution -> Results -> Conclusion

## Software Architecture Visualization

### Diagram Design Principles
- **Clarity and Simplicity**: Understandable at a glance
- **Tell a Story**: Clear, logical flow (top-to-bottom or left-to-right)
- **Consistency**: Same shape for same type of component
- **Include a Legend**: Explain notation

### AI/ML Pipeline Visualization
- **Use Directed Acyclic Graphs (DAGs)**: Standard for ML pipelines
- **Key Stages**: Data Sources -> Preprocessing -> Model Training -> Evaluation -> Deployment
- **Tools**: Kubeflow Pipelines, Apache Airflow, MLflow, Kedro-Viz

### Color Coding for System Components
- **Limited Palette**: 3-5 colors
- **Logical Assignment**:
  - Blue: External systems/UI
  - Green: Core application services
  - Yellow: Databases/data stores
  - Red: Authentication/security
- **High Contrast**: Ensure distinguishable and colorblind accessible
- **Use a Legend**: Define what each color represents

### Layer Diagrams vs. Flow Diagrams
- **Layer Diagrams (Structural)**: Show high-level structure and organization (C4 Model)
- **Flow Diagrams (Behavioral)**: Show sequence of interactions or data flow
- **Poster Recommendation**: Use layer diagram as main view, supplement with flow diagram

### Simplifying Complex Architectures
- **Abstraction**: Hide unnecessary details
- **C4 Model**: System Context Diagram (Level 1) or Container Diagram (Level 2)
- **Focus on Narrative**: Omit components not relevant to research contribution
- **Use Grouping**: Draw boundaries around related components

### Tools for Clean Technical Diagrams
| Category | Tool | Key Features |
|----------|------|--------------|
| GUI-Free | diagrams.net | Free, powerful, versatile |
| GUI-Commercial | Lucidchart | Collaboration, templates |
| Diagrams as Code | PlantUML | Create from text, version control |
| Diagrams as Code | Mermaid | Markdown-like, GitHub integration |

## AI Innovators Cup Requirements

### Official Requirements
- **Size**: A0 or A1, vertical orientation
- **Format**: Self-contained poster with QR code highly recommended
- **Required Sections**:
  - Background (背景)
  - Objectives (目的)
  - AI Utilized (AI活用の工夫)
  - Application Method / How it Works
  - Results / Output (結果・アウトプット)
  - Future Plans (今後の展開)

### Evaluation Criteria (100 points)
| Criterion | Points | Key for High Score |
|-----------|--------|-------------------|
| Model Performance & Effectiveness | 25 | High accuracy, reproducibility, justified model choice |
| Prompt Design & AI Utilization | 20 | Logical, creative inputs, testing/refinement process |
| Idea & Creativity | 20 | Novel idea or unique perspective |
| Analysis & Insight | 15 | Deep, logical analysis of results |
| Poster Composition & Design | 10 | Clear layout, organized, visually easy to understand |
| Presentation & Dialogue | 10 | Easy to grasp, accurate Q&A |

### QR Code Recommendations
- **Highly Recommended**: Include QR code linking to 3-minute demonstration video
- Video should showcase project in action and explain real-world use cases

## SIT Copilot Project Features for Poster

### 1. Real-time Lecture Captioning and Summarization
- Azure Speech SDK for real-time speech recognition
- Captions displayed instantly, finalized every 5 seconds
- Summaries generated every 30 seconds (last 60 seconds of lecture)
- Evidence tags showing source (speech, slide, blackboard)

### 2. Live Q&A with Slide Context Awareness
- AssistPanel provides mini-Q&A during lecture
- OCR extracts slide text for context
- Immediate, concise answers during live view

### 3. Procedure/Manual QA System
- Procedure Guide (F2) for university procedure questions
- Source-based answers from official documents
- Prevents misinformation through source verification

### 4. Voice Input with Japanese ASR Correction
- Primary input via microphone
- Japanese ASR correction for improved accuracy
- ASR hallucination judgment and subtitle review

### 5. OCR for Slide Text Extraction
- Azure AI Vision for OCR on slides and blackboard
- Frontend captures at 1fps with change detection
- ROI (Region of Interest) support
- Quality control with confidence filtering

### 6. Azure OpenAI Integration
- Multiple models: ReadinessAnalyzer, LectureSummarizer, LectureQAAnswerer, ProcedureAnswerer, Verifier, Simplifier, Translator
- Centralized OpenAI service integration
- Observability wrappers for monitoring

### 7. Azure AI Search Integration
- Two indexes: procedure_index and lecture_index
- Hybrid search (keyword + vector)
- Chunked content indexing after lecture finalization

### 8. WandB Weave Observability
- Observability wrappers for all services
- Metrics: API latency, error rates, OCR success rates
- Trace visualization for debugging

### 9. System Architecture
- Frontend: React + TypeScript, Azure Static Web Apps
- Backend: FastAPI, Azure Container Apps
- Database: SQLite on Azure Files
- Azure Services: OpenAI, Speech, Vision, AI Search, Blob Storage

### 10. Key Technical Achievements
- Source-only Q&A with citations
- Real-time multi-modal integration (speech + OCR + summarization)
- Comprehensive evaluation metrics (WER, QA accuracy, citation consistency)
- Accessibility: adjustable fonts, high-contrast themes, easy Japanese support
