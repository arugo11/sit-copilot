# F4 Lecture QA Research Summary

Research Date: 2025-02-21
Project: F4 Lecture QA (講義後QA)

## 1. rank-bm25 Library

### Installation
```bash
pip install rank-bm25
```

### Core API

**Initialization:**
```python
from rank_bm25 import BM25Okapi

# Corpus must be pre-tokenized (list of lists of strings)
tokenized_corpus = [
    ["hello", "world"],
    ["hello", "python"],
    ["world", "of", "machine", "learning"]
]

bm25 = BM25Okapi(tokenized_corpus, k1=1.5, b=0.75, epsilon=0.25)
```

**Key Parameters:**
- `k1` (default 1.5): Term frequency saturation parameter
- `b` (default 0.75): Length normalization parameter
- `epsilon` (default 0.25): Lower bound for IDF values

**Retrieval Methods:**
```python
# Get scores for all documents
doc_scores = bm25.get_scores(tokenized_query)

# Get top-n documents
top_docs = bm25.get_top_n(tokenized_query, corpus_documents, n=3)
```

**Available Variants:**
- `BM25Okapi`: Standard Okapi BM25
- `BM25L`: BM25 with length normalization
- `BM25+`: Improved version addressing zero-score issues
- `BM25Adpt`: Adaptive BM25
- `BM25T`: BM25 with term-specific parameters

### Limitations for Lecture QA

1. **No Built-in Tokenization**: Must implement preprocessing (lowercasing, stopword removal)
2. **No Incremental Updates**: Index must be rebuilt when documents are added
3. **Single-Field Only**: Native API doesn't support multi-field ranking (speech + visual)
4. **Not Production-Scale**: Author recommends `retriv` for large-scale production

### Multi-Field Strategy for Lecture QA

Since rank-bm25 doesn't natively support multi-field search, use these approaches:

**Option 1: Concatenated Documents**
```python
# Combine speech + visual content into single searchable text
document = f"[SPEECH] {transcript_text} [VISUAL] {ocr_text}"
```

**Option 2: Separate Indexes with Score Fusion**
```python
# Build separate BM25 indexes for speech and visual
bm25_speech = BM25Okapi(speech_corpus)
bm25_visual = BM25Okapi(visual_corpus)

# Combine scores with weighted fusion
speech_scores = bm25_speech.get_scores(query)
visual_scores = bm25_visual.get_scores(query)
combined_scores = 0.7 * speech_scores + 0.3 * visual_scores
```

**Option 3: Hybrid Field Tags**
```python
# Tag each chunk with its source type
chunks = [
    ["SPEECH", "this", "is", "spoken", "content"],
    ["VISUAL", "slide", "title", "text"],
]
# Query with field boost: "SPEECH query" gets higher speech weight
```

### Index Building Pattern

```python
class LectureIndex:
    def __init__(self):
        self.bm25: BM25Okapi | None = None
        self.documents: list[dict] = []  # Metadata storage
    
    def build_index(self, chunks: list[dict]):
        """Build BM25 index from lecture chunks."""
        tokenized_corpus = []
        for chunk in chunks:
            # Preprocess: lowercase, tokenize
            tokens = self._tokenize(chunk["text"])
            tokenized_corpus.append(tokens)
            self.documents.append(chunk)
        
        self.bm25 = BM25Okapi(tokenized_corpus)
    
    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """Search and return top-k chunks with metadata."""
        if not self.bm25:
            return []
        
        tokenized_query = self._tokenize(query)
        top_indices = self.bm25.get_top_n(
            tokenized_query, 
            list(range(len(self.documents))), 
            n=top_k
        )
        return [self.documents[i] for i in top_indices]
```

## 2. Azure OpenAI for RAG-based QA

### API Pattern

**Citation Response Structure (from Azure OpenAI On Your Data):**
```python
{
    "citations": [{
        "content": str,      # Required: citation content
        "title": str,        # Optional: document title
        "url": str,          # Optional: source URL
        "filepath": str,     # Optional: file path
        "chunk_id": str      # Optional: chunk identifier
    }],
    "intent": str,          # Detected intent (can ignore)
    "all_retrieved_documents": [{
        "search_queries": [str],
        "data_source_index": int,
        "original_search_score": float,
        "rerank_score": float,
        "filter_reason": str
    }]
}
```

### Source-Only Constraint Pattern

**Prompt Template:**
```python
SOURCE_ONLY_PROMPT = """
You are a lecture QA assistant. Answer the question using ONLY the provided sources.

Sources:
{sources_formatted}

Question: {question}

Requirements:
1. Use ONLY information from the sources above
2. If the answer is not in the sources, say "講義内容に該当する情報が見つかりませんでした。"
3. Include timestamps for speech sources: [SPEECH: MM:SS]
4. For visual sources, note: [VISUAL CONTENT]
5. Do NOT use outside knowledge

Answer:"""
```

**Source Formatting:**
```python
def format_sources(sources: list[dict]) -> str:
    formatted = []
    for i, src in enumerate(sources, 1):
        if src["type"] == "speech":
            formatted.append(
                f"[Source {i}] SPEECH ({src['timestamp']}): {src['text']}"
            )
        else:  # visual
            formatted.append(
                f"[Source {1}] VISUAL: {src['text']}"
            )
    return "\n\n".join(formatted)
```

## 3. LLM-based Verifier Design

### Verification Patterns

**Pattern 1: Claim-by-Claim Verification**
```python
VERIFIER_PROMPT = """
Given an answer and source documents, verify each factual claim.

Answer: {answer}

Sources:
{sources}

Task: For each claim in the answer:
1. Extract the claim
2. Check if it's supported by sources
3. Mark: SUPPORTED | PARTIAL | NOT_SUPPORTED
4. If NOT_SUPPORTED, provide correction

Return JSON format.
"""
```

**Pattern 2: Consistency Checking**
```python
def verify_consistency(answer: str, sources: list[dict]) -> dict:
    """Check if answer is consistent with sources."""
    prompt = f"""
    Does this answer contradict the sources?

    Answer: {answer}
    Sources: {format_sources(sources)}

    Return: {"consistent": true/false, "issues": ["list of contradictions"]}
    """
    # Call LLM and parse response
```

**Pattern 3: Citation Validation**
```python
def validate_citations(answer: str, sources: list[dict]) -> dict:
    """Validate that citations in answer actually support the claim."""
    prompt = f"""
    Check each citation in the answer. Does the cited source actually support the claim?

    Answer: {answer}
    Available Sources: {sources}

    Return: {"valid_citations": int, "total_citations": int, "issues": [...]}
    """
```

### Fallback Strategies

1. **Verification Failed → Return Source-Only Response**
2. **Low Confidence → Return Disclaimer** + Sources
3. **No Sources → Fallback Message** (from procedure_qa pattern)

## 4. Lecture QA Best Practices

### Chunking Strategy

**For Transcripts:**
```python
# Chunk by semantic boundaries (sentences, paragraphs)
# Recommended: 256-512 tokens per chunk
# Overlap: 10-20% between chunks
# Preserve: timestamps, speaker, type (speech/visual)
```

**Parameters:**
- Chunk size: 256-512 tokens (optimal for BM25 + LLM context)
- Overlap: 50-100 tokens (maintains context)
- Boundary: Sentence/phrase boundaries (avoid mid-word splits)

### Context Window Management

**Retrieval Strategy:**
```python
# Retrieve top-5 to top-10 chunks
# Rank by BM25 score
# Apply diversity penalty (avoid retrieving same section)
# Limit total retrieved tokens to ~2000 for answer generation
```

**Answer Generation:**
```python
# Typical Azure OpenAI context window: 128K tokens
# Reserve: ~2K for system prompt + instructions
# Retrieved context: ~2-4K tokens
# Query: ~200 tokens
# Answer generation: ~500-1000 tokens
```

### Follow-up Context Handling

**Conversation History Pattern:**
```python
# Store previous Q&A turns
# Include previous answers as context for follow-up
# Format:
"""
Previous Question: {q1}
Answer: {a1}

Current Question: {q2}
"""
```

**Reference Resolution:**
- Extract pronouns and references ("それ", "その部分")
- Resolve to actual entities from previous turns
- Expand query with resolved context

### Confidence Scoring

**Factors:**
1. **BM25 Score**: High score = strong keyword match
2. **Source Count**: Multiple sources supporting same answer = higher confidence
3. **Verification Result**: LLM verifier pass/fail
4. **Answer Completeness**: Does answer directly address question?

**Scoring Formula (Example):**
```python
confidence = (
    0.4 * normalized_bm25_score +
    0.3 * source_count_factor +
    0.3 * verification_score
)
# Map to: high (>0.7), medium (0.4-0.7), low (<0.4)
```

## 5. Integration with Existing Patterns

### Reuse from procedure_qa_service.py

**Pattern 1: Service Layer Separation**
- `LectureRetrievalService`: BM25-based search
- `LectureAnswererService`: Azure OpenAI answer generation
- `LectureVerifierService`: LLM-based verification (new)
- `LectureQAService`: Orchestration (like SqlAlchemyProcedureQAService)

**Pattern 2: QATurn Persistence**
```python
# Reuse existing QATurn model
qa_turn = QATurn(
    session_id=session_id,  # Lecture session ID
    feature="lecture_qa",
    question=question,
    answer=answer,
    confidence=confidence,
    citations_json=[{  # Lecture-specific format
        "chunk_id": chunk["id"],
        "type": chunk["type"],  # "speech" | "visual"
        "timestamp": chunk.get("timestamp"),
        "text": chunk["text"][:200],  # Snippet
    }],
    retrieved_chunk_ids_json=[c["id"] for c in chunks],
    latency_ms=latency_ms,
    verifier_supported=True,  # F4 has verifier
)
```

**Pattern 3: Fallback Handling**
```python
# Similar to procedure_qa's no-source fallback
if not sources:
    return LectureAskResponse(
        answer="講義記録に該当する情報が見つかりませんでした。",
        confidence="low",
        sources=[],
        action_next="別のキーワードで質問してください。",
        fallback=answer,
    )
```

## 6. Key Constraints & Considerations

1. **BM25 Limitations**: No incremental updates, must rebuild index when new chunks added
2. **No Azure AI Search in F4**: Use local BM25 only
3. **Verifier Cost**: Additional LLM call per QA; may impact latency
4. **Source Types**: Handle both speech (with timestamps) and visual (OCR) content
5. **Japanese Language**: Consider Japanese tokenization for BM25 (use `jieba` or `MeCab` + SudachiPy)

## 7. Recommended Next Steps

1. **Prototype BM25 Index**: Test chunking + tokenization with actual Japanese lecture data
2. **Azure OpenAI Integration**: Implement answer generation with citation formatting
3. **Verifier Service**: Implement claim-by-claim verification pattern
4. **Performance Testing**: Measure latency for retrieval + generation + verification pipeline

## Sources

- [rank-bm25 PyPI](https://pypi.org/project/rank-bm25/)
- [rank-bm25 GitHub](https://github.com/dorianbrown/rank_bm25)
- [Azure OpenAI On Your Data API](https://learn.microsoft.com/en-us/azure/ai-services/openai/references/on-your-data)
- [FactSelfCheck: Fact-Level Hallucination Detection (arXiv 2025)](https://arxiv.org/abs/2503.17229)
- [Semantic Entropy Probes (arXiv 2025)](http://arxiv.org/html/2406.15927v1)
- [Claim Verification in LLMs (arXiv 2024)](https://arxiv.org/html/2408.14317v1)
