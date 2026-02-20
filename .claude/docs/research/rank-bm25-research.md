# rank-bm25 Research for F4 Lecture QA

Research Date: 2025-02-21
Requester: Architect (F4 Lecture QA Project)

## 1. rank-bm25 Library

### Latest Version & Installation

```bash
pip install rank-bm25
```

- **Latest Version**: 0.2.2 (Released: Feb 16, 2022)
- **License**: Apache 2.0
- **Dependencies**: numpy (minimal dependencies)

### BM25Okapi API Usage

```python
from rank_bm25 import BM25Okapi

# Corpus must be pre-tokenized (list of lists of strings)
tokenized_corpus = [
    ["hello", "world"],
    ["hello", "python"],
    ["world", "of", "machine", "learning"]
]

# Initialize with parameters
bm25 = BM25Okapi(tokenized_corpus, k1=1.5, b=0.75, epsilon=0.25)
```

**Key Parameters:**
- `k1` (default 1.5): Term frequency saturation (1.2-2.0 recommended)
- `b` (default 0.75): Length normalization (0.0=no norm, 1.0=full norm)
- `epsilon` (default 0.25): IDF lower bound to prevent division by zero

### Building Index from Text Chunks

```python
class LectureIndex:
    def __init__(self):
        self.bm25: BM25Okapi | None = None
        self.chunks: list[dict] = []
    
    def build_index(self, chunks: list[dict]):
        """Build BM25 index from SpeechEvent chunks."""
        # Extract and tokenize text from chunks
        tokenized_corpus = []
        for chunk in chunks:
            tokens = self._tokenize(chunk["text"])
            tokenized_corpus.append(tokens)
            self.chunks.append(chunk)
        
        # Build index
        self.bm25 = BM25Okapi(tokenized_corpus)
    
    def _tokenize(self, text: str) -> list[str]:
        # Tokenization logic (see Japanese section below)
        return text.lower().split()
```

### Query Methods

**get_scores():**
```python
# Get BM25 scores for ALL documents
doc_scores = bm25.get_scores(tokenized_query)
# Returns: numpy array of scores (same length as corpus)
```

**get_top_n():**
```python
# Get top-n documents sorted by score
top_docs = bm25.get_top_n(tokenized_query, corpus_documents, n=5)
# Returns: list of top-n documents
```

### Thread-Safety & Async Considerations

**⚠️ CRITICAL: rank-bm25 is NOT thread-safe for concurrent use**

From community research findings:

1. **No Thread-Safety Guarantees**: The library doesn't implement locking or synchronization
2. **Safe Pattern**: Create a NEW BM25Okapi instance per request
3. **Unsafe Pattern**: Sharing a single instance across async concurrent requests

**Recommended Async Pattern:**
```python
# Service-level pattern: create BM25 instance per request
class LectureRetrievalService:
    def __init__(self, chunk_store):
        self._chunk_store = chunk_store  # Thread-safe storage
    
    async def retrieve(self, query: str, limit: int = 5) -> list[dict]:
        # Create NEW BM25 instance per request (thread-safe)
        chunks = await self._chunk_store.get_chunks()
        tokenized_corpus = [self._tokenize(c["text"]) for c in chunks]
        
        # Fresh instance per request = safe for concurrent use
        bm25 = BM25Okapi(tokenized_corpus)
        
        tokenized_query = self._tokenize(query)
        top_indices = bm25.get_top_n(
            tokenized_query,
            list(range(len(chunks))),
            n=limit
        )
        return [chunks[i] for i in top_indices]
```

**Alternative: Use bm25s instead**
- **bm25s** is explicitly designed for concurrent use
- Orders of magnitude faster (see benchmarks below)
- Supports memory-mapped indices for large corpora

### Known Limitations & Gotchas

| Issue | Impact | Mitigation |
|-------|--------|------------|
| **No incremental updates** | Must rebuild entire index when chunks added | Rebuild on schedule; batch updates |
| **No thread safety** | Crashes/data corruption in concurrent FastAPI | Create instance per request OR use bm25s |
| **No built-in tokenization** | Must implement preprocessing | Use SudachiPy/Janome for Japanese |
| **All-in-memory** | Large corpora consume RAM | Use bm25s with mmap for scale |
| **Static index** | Index doesn't auto-update with new content | Explicit rebuild triggers |

## 2. BM25 Context Expansion Pattern

### Source-Plus-Context Retrieval

**Goal**: Return not just the matching chunk, but also neighboring chunks for context.

**Challenge**: Avoid duplicates when neighboring chunks overlap with retrieval results.

### Recommended Approach: Post-Retrieval Expansion

```python
def retrieve_with_context(
    bm25: BM25Okapi,
    chunks: list[dict],  # Must be sorted by timestamp/position
    query: str,
    top_k: int = 3,
    context_window: int = 1  # Number of chunks on each side
) -> list[dict]:
    """Retrieve chunks with neighboring context."""
    
    # 1. Get top-k results (indices into chunks array)
    tokenized_query = tokenize(query)
    top_indices = bm25.get_top_n(tokenized_query, list(range(len(chunks))), n=top_k)
    
    # 2. Expand each result with neighbors
    expanded_indices = set()
    for idx in top_indices:
        # Add context window chunks (before and after)
        for offset in range(-context_window, context_window + 1):
            neighbor_idx = idx + offset
            if 0 <= neighbor_idx < len(chunks):
                expanded_indices.add(neighbor_idx)
    
    # 3. Return expanded results (deduplicated via set)
    return [chunks[i] for i in sorted(expanded_indices)]
```

### Avoiding Duplicates

The `set()` in the example above automatically handles:
- Overlapping context windows from adjacent results
- Multiple retrievals pointing to same chunk

### Performance Considerations

| Factor | Impact | Recommendation |
|--------|--------|----------------|
| **Context window size** | Larger = more context, slower LLM | Start with `context_window=1` (1 chunk each side) |
| **Corpus size** | Larger = slower BM25 rebuild | Cache tokenized corpus; only rebuild when new chunks added |
| **Top-k value** | Larger = more expansion candidates | `top_k=3` to `top_k=5` is typical |
| **Chunk overlap** | Existing overlap reduces expansion value | If chunks already have 20% overlap, use `context_window=0` |

### Memory-Cached Pattern for Production

```python
class CachedLectureIndex:
    """Cache tokenized corpus to avoid re-tokenization on each request."""
    
    def __init__(self):
        self._chunks: list[dict] = []
        self._tokenized_corpus: list[list[str]] = []
        self._stale = True
    
    def add_chunks(self, new_chunks: list[dict]):
        """Add new chunks and mark index as stale."""
        self._chunks.extend(new_chunks)
        for chunk in new_chunks:
            self._tokenized_corpus.append(tokenize(chunk["text"]))
        self._stale = True
    
    def retrieve(self, query: str, top_k: int = 3) -> list[dict]:
        """Retrieve with fresh BM25 instance (thread-safe)."""
        # Create BM25 on-the-fly from cached tokenization
        bm25 = BM25Okapi(self._tokenized_corpus)
        tokenized_query = tokenize(query)
        top_indices = bm25.get_top_n(tokenized_query, list(range(len(self._chunks))), n=top_k)
        return [self._chunks[i] for i in top_indices]
```

## 3. Japanese Tokenization

### rank-bm25 Requirements

rank-bm25 accepts **pre-tokenized lists of strings**. Tokenization is YOUR responsibility.

### Recommended: SudachiPy

**Installation:**
```bash
pip install sudachipy sudachidict_core
```

**Usage:**
```python
from sudachipy import tokenizer, dictionary

# Initialize tokenizer (one-time, reuse)
tokenizer_obj = dictionary.Dictionary().create()

def tokenize_japanese(text: str) -> list[str]:
    """Tokenize Japanese text for BM25."""
    mode = tokenizer.Tokenizer.SplitMode.C  # Use mode C for longer units
    morphemes = tokenizer_obj.tokenize(text, mode)
    return [m.surface() for m in morphemes]

# Example
tokens = tokenize_japanese("国家公務員は給与を受け取る")
# => ['国家公務員', 'は', '給与', 'を', '受け取る']
```

**SudachiPy Split Modes:**
- **Mode A**: Most granular (e.g., "国家", "公務", "員") - better for precise matching
- **Mode B**: Medium granularity (e.g., "国家", "公務員") - balanced
- **Mode C**: Longest units (e.g., "国家公務員") - better for phrase search

**Recommendation**: Use **Mode C** for lecture QA to preserve compound terms.

### Alternative: Janome

```bash
pip install janome
```

```python
from janome.tokenizer import Tokenizer

# Initialize (slower startup than SudachiPy)
t = Tokenizer()

def tokenize_japanese(text: str) -> list[str]:
    return [token.surface for token in t.tokenize(text)]
```

**Comparison:**
| Feature | SudachiPy | Janome |
|---------|-----------|--------|
| Startup speed | Fast (pre-built dict) | Slower (pure Python) |
| Memory usage | Higher (dict loaded) | Lower |
| Accuracy | Higher (3 split modes) | Good |
| Recommendation | ✅ Production | OK for small apps |

### Tokenization Caching Strategies

**Strategy 1: Cache Tokenizer Instance**
```python
# Module-level singleton (FastAPI startup)
_tokenizer: tokenizer.Tokenizer | None = None

def get_tokenizer() -> tokenizer.Tokenizer:
    global _tokenizer
    if _tokenizer is None:
        _tokenizer = dictionary.Dictionary().create()
    return _tokenizer

def tokenize_japanese(text: str) -> list[str]:
    tok = get_tokenizer()
    return [m.surface() for m in tok.tokenize(text, tokenizer.Tokenizer.SplitMode.C)]
```

**Strategy 2: Pre-tokenize on SpeechEvent Creation**
```python
# When storing SpeechEvent, also store tokenized version
class SpeechEvent(Base):
    text: Mapped[str]
    tokens_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

# Tokenize once when creating event
event = SpeechEvent(
    text=transcript_text,
    tokens_json=tokenize_japanese(transcript_text)  # Store for reuse
)
```

**Strategy 3: LRU Cache for Frequently Queried Texts**
```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def tokenize_cached(text: str) -> tuple[str, ...]:
    """Cached tokenization (returns tuple for hashability)."""
    return tuple(get_tokenizer().tokenize(text, tokenizer.Tokenizer.SplitMode.C))
```

### Stopword Removal (Optional)

For Japanese, consider removing functional words:
```python
# Stopwords: particles (は, が, を, に), auxiliary verbs (だ, です)
JAPANESE_STOPWORDS = {"は", "が", "を", "に", "で", "の", "だ", "です", "した"}

def tokenize_japanese_no_stopwords(text: str) -> list[str]:
    tok = get_tokenizer()
    return [
        m.surface() 
        for m in tok.tokenize(text, tokenizer.Tokenizer.SplitMode.C)
        if m.surface() not in JAPANESE_STOPWORDS
    ]
```

## 4. bm25s Alternative (Recommended for Scale)

If rank-bm25 limitations become problematic, consider **bm25s**:

```bash
pip install bm25s
```

**Advantages:**
- **100x faster** than rank-bm25 (queries/sec benchmarks)
- **Thread-safe** by design
- **Memory-mapped indices** for large corpora
- **Persistent indices** (save/load from disk)
- **Numba backend** for 2x speedup on large datasets

**Usage:**
```python
import bm25s

# Create index
corpus_tokens = bm25s.tokenize(corpus, stopwords="en")
retriever = bm25s.BM25()
retriever.index(corpus_tokens)

# Save to disk
retriever.save("lecture_index")

# Load later (thread-safe!)
retriever = bm25s.BM25.load("lecture_index", mmap=True)
```

**Benchmarks (from bm25s docs):**
| Dataset | bm25s (QPS) | rank-bm25 (QPS) | Speedup |
|---------|-------------|-----------------|---------|
| nfcorpus | 1196 | 225 | 5.3x |
| scidocs | 767 | 9 | 85x |
| arguana | 574 | 2 | 287x |

## 5. Implementation Recommendations for F4

### Recommended Architecture

```python
class LectureBM25Index:
    """Thread-safe BM25 index with cached tokenization."""
    
    def __init__(self, tokenizer_mode: str = "C"):
        self._chunks: list[dict] = []
        self._tokenized_corpus: list[list[str]] = []
        self._tokenizer = dictionary.Dictionary().create()
        self._mode = getattr(tokenizer.Tokenizer.SplitMode, tokenizer_mode)
    
    def add_speech_events(self, events: list[SpeechEvent]):
        """Add events and update tokenized corpus."""
        for event in events:
            self._chunks.append({
                "id": event.id,
                "text": event.text,
                "start_ms": event.start_ms,
                "type": "speech",
            })
            # Tokenize once, store for reuse
            tokens = [m.surface() for m in self._tokenizer.tokenize(event.text, self._mode)]
            self._tokenized_corpus.append(tokens)
    
    def retrieve(
        self, 
        query: str, 
        top_k: int = 5,
        context_window: int = 0,
        mode: Literal["source-only", "source-plus-context"] = "source-only"
    ) -> list[dict]:
        """Thread-safe retrieval with context expansion."""
        # Create BM25 instance per request (safe for concurrent use)
        bm25 = BM25Okapi(self._tokenized_corpus)
        
        # Tokenize query
        query_tokens = [m.surface() for m in self._tokenizer.tokenize(query, self._mode)]
        
        # Get top-k indices
        top_indices = bm25.get_top_n(
            query_tokens, 
            list(range(len(self._chunks))), 
            n=top_k
        )
        
        # Expand context if requested
        if mode == "source-plus-context" and context_window > 0:
            expanded_indices = set()
            for idx in top_indices:
                for offset in range(-context_window, context_window + 1):
                    neighbor_idx = idx + offset
                    if 0 <= neighbor_idx < len(self._chunks):
                        expanded_indices.add(neighbor_idx)
            top_indices = sorted(expanded_indices)
        
        return [self._chunks[i] for i in top_indices]
```

### Configuration Parameters

| Parameter | Recommended Value | Rationale |
|-----------|-------------------|-----------|
| `k1` | 1.2-1.5 | Japanese text has shorter terms, lower saturation |
| `b` | 0.5-0.75 | Lecture chunks are similar length, less normalization needed |
| `top_k` | 5-10 | Balance context vs. noise |
| `context_window` | 0-2 | 0 for source-only, 1-2 for expanded context |
| Sudachi mode | C | Preserve compound terms for lecture content |

### File Structure

```
app/
├── services/
│   └── lecture_bm25_service.py    # BM25 index management
├── tokenization/
│   ├── __init__.py
│   └── sudachi.py                 # SudachiPy wrapper (singleton)
└── models/
    └── speech_event.py            # Existing model
```

## Sources

- [rank-bm25 PyPI](https://pypi.org/project/rank-bm25/)
- [rank-bm25 GitHub](https://github.com/dorianbrown/rank_bm25)
- [SudachiPy GitHub](https://github.com/WorksApplications/SudachiPy)
- [bm25s PyPI](https://pypi.org/project/bm25s/)
- [Kotaemon Custom Retrieval](https://blog.csdn.net/weixin_32324637/article/details/156038338) (Thread-safety reference)
