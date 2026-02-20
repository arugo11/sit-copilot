# rank-bm25 Library Reference

## Overview

**Package:** `rank-bm25`  
**Version:** 0.2.2 (Released: Feb 16, 2022)  
**License:** Apache 2.0  
**Repository:** [dorianbrown/rank_bm25](https://github.com/dorianbrown/rank_bm25)

A lightweight Python implementation of BM25 algorithms for document ranking and search engines.

## Installation

```bash
pip install rank-bm25
```

## API Reference

### Classes

#### BM25Okapi

Standard Okapi BM25 implementation.

```python
from rank_bm25 import BM25Okapi

bm25 = BM25Okapi(
    corpus: list[list[str]],  # Tokenized documents
    k1: float = 1.5,          # Term frequency saturation
    b: float = 0.75,          # Length normalization
    epsilon: float = 0.25     # IDF lower bound
)
```

**Parameters:**
- `corpus`: List of tokenized documents (each document is list of strings)
- `k1`: Controls term frequency saturation (higher = less saturation)
- `b`: Controls length normalization impact (0 = no normalization, 1 = full)
- `epsilon`: Floor value for IDF (prevents division by zero)

#### BM25L

BM25 with length normalization variant.

#### BM25Plus

Improved BM25 addressing zero-score issues for documents with no query terms.

#### BM25Adpt

Adaptive BM25 with dynamic parameter adjustment.

#### BM25T

BM25 with term-specific parameters.

### Methods

#### get_scores()

```python
def get_scores(self, query: list[str]) -> np.ndarray:
    """Return BM25 scores for all documents in corpus."""
```

**Returns:** NumPy array of scores (same length as corpus)

#### get_top_n()

```python
def get_top_n(
    self, 
    query: list[str], 
    documents: list[Any], 
    n: int = 5
) -> list[Any]:
    """Return top-n documents sorted by BM25 score."""
```

**Parameters:**
- `query`: Tokenized query
- `documents`: Original documents (can be different from indexed corpus)
- `n`: Number of results to return

## Usage Examples

### Basic Usage

```python
from rank_bm25 import BM25Okapi

corpus = [
    "Hello there good man!",
    "It is quite windy in London",
    "How is the weather today?"
]

tokenized_corpus = [doc.split(" ") for doc in corpus]
bm25 = BM25Okapi(tokenized_corpus)

query = "windy London"
tokenized_query = query.split(" ")

# Get scores
doc_scores = bm25.get_scores(tokenized_query)
# array([0., 0.93729472, 0.])

# Get top-n
top_docs = bm25.get_top_n(tokenized_query, corpus, n=1)
# ['It is quite windy in London']
```

### With Preprocessing

```python
import re
from rank_bm25 import BM25Okapi

def preprocess(text: str) -> list[str]:
    # Lowercase
    text = text.lower()
    # Remove punctuation
    text = re.sub(r'[^\w\s]', '', text)
    # Tokenize
    tokens = text.split()
    return tokens

tokenized_corpus = [preprocess(doc) for doc in corpus]
bm25 = BM25Okapi(tokenized_corpus)

query_tokens = preprocess("Windy London")
results = bm25.get_top_n(query_tokens, corpus, n=3)
```

### Lecture QA Pattern

```python
from rank_bm25 import BM25Okapi
from typing import list, dict

class LectureSearchIndex:
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.bm25: BM25Okapi | None = None
        self.chunks: list[dict] = []
        self.k1 = k1
        self.b = b
    
    def add_chunks(self, chunks: list[dict]):
        """Add lecture chunks and rebuild index."""
        for chunk in chunks:
            self.chunks.append(chunk)
        self._rebuild_index()
    
    def _rebuild_index(self):
        """Rebuild BM25 index from all chunks."""
        tokenized = [self._tokenize(c["text"]) for c in self.chunks]
        self.bm25 = BM25Okapi(tokenized, k1=self.k1, b=self.b)
    
    def _tokenize(self, text: str) -> list[str]:
        """Simple whitespace tokenization (replace with proper tokenizer)."""
        return text.lower().split()
    
    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """Search for relevant chunks."""
        if not self.bm25:
            return []
        
        query_tokens = self._tokenize(query)
        top_indices = self.bm25.get_top_n(
            query_tokens,
            list(range(len(self.chunks))),
            n=top_k
        )
        return [self.chunks[i] for i in top_indices]
```

## Algorithm Details

### BM25 Score Formula

```
score(D, Q) = Σ IDF(qi) × (f(qi, D) × (k1 + 1)) / (f(qi, D) + k1 × (1 - b + b × |D| / avgdl))
```

Where:
- `qi`: Query term
- `f(qi, D)`: Frequency of qi in document D
- `|D|`: Length of document D
- `avgdl`: Average document length
- `k1`: Term frequency parameter (typically 1.2-2.0)
- `b`: Length normalization parameter (typically 0.75)
- `IDF(qi)`: Inverse document frequency

## Parameter Tuning

### k1 (Term Frequency Saturation)

- **Range:** 1.2 to 2.0
- **Lower values (1.0-1.5):** Less saturation, term frequency matters more
- **Higher values (1.5-2.5):** More saturation, diminishing returns on repeated terms
- **Default:** 1.5

### b (Length Normalization)

- **Range:** 0.0 to 1.0
- **0.0:** No length normalization (longer documents not penalized)
- **0.75:** Standard normalization (default)
- **1.0:** Full normalization (shorter documents favored)

### Tuning for Japanese

```python
# For Japanese text with shorter documents
bm25 = BM25Okapi(tokenized_corpus, k1=1.2, b=0.5)
```

## Limitations

1. **No Incremental Updates:** Must rebuild entire index when documents added/removed
2. **No Built-in Tokenization:** Requires custom preprocessing
3. **Single Language:** Designed for space-separated languages (English)
4. **Memory:** Entire corpus loaded in memory
5. **No Persistence:** Index must be rebuilt on restart

## Alternatives

- **bm25s:** Faster implementation using sparse matrices
- **retriv:** Production-scale retrieval package (recommended by author)
- **Rankify:** Full-featured search engine with BM25

## Performance

Typical performance on moderate corpora:
- 1,000 documents: < 1ms per query
- 10,000 documents: ~10ms per query
- 100,000 documents: ~100ms per query

## Japanese Tokenization

For Japanese text, integrate with tokenizer:

```python
# Using SudachiPy (example)
from sudachipy import tokenizer, dictionary

tokenizer_obj = dictionary.Dictionary().create()

def tokenize_japanese(text: str) -> list[str]:
    return [m.surface() for m in tokenizer_obj.tokenize(text)]

tokenized_corpus = [tokenize_japanese(doc) for doc in corpus]
bm25 = BM25Okapi(tokenized_corpus)
```
