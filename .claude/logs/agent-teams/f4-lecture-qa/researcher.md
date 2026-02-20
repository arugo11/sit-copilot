# Researcher Work Log

## Project: F4 Lecture QA
## Role: Researcher
## Date: 2025-02-21

## Tasks Completed

### 1. rank-bm25 Library Research ✓
- Researched rank-bm25 API documentation from PyPI and GitHub
- Identified core classes: BM25Okapi, BM25L, BM25Plus, BM25Adpt, BM25T
- Documented key parameters: k1 (term frequency), b (length normalization), epsilon
- Found usage patterns for index building and retrieval
- Identified limitation: no built-in multi-field search support
- Proposed solutions: concatenated documents, separate indexes with score fusion, hybrid field tags
- Created implementation pattern for LectureSearchIndex class

### 2. Azure OpenAI for RAG-based QA ✓
- Researched Azure OpenAI On Your Data API from Microsoft Learn
- Documented citation response structure (content, title, url, filepath, chunk_id)
- Found source-only constraint prompt patterns
- Identified source formatting requirements with timestamps and type labels
- Documented conversation history pattern for follow-up questions

### 3. LLM-based Verifier Design ✓
- Researched fact-level hallucination detection papers (FactSelfCheck, 2025)
- Found semantic entropy probes for efficient hallucination detection
- Identified verification patterns: claim-by-claim, consistency checking, citation validation
- Documented fallback strategies for verification failures
- Found citation validation approach

### 4. Lecture QA Best Practices ✓
- Identified chunking strategy: 256-512 tokens, 10-20% overlap, semantic boundaries
- Found context window management: top-5 to top-10 chunks, ~2-4K retrieved tokens
- Documented follow-up context handling with conversation history
- Found confidence scoring factors: BM25 score, source count, verification result
- Identified Japanese tokenization requirements (SudachiPy, MeCab)

### 5. Integration with Existing Patterns ✓
- Analyzed procedure_qa_service.py for reuse patterns
- Found service layer separation: RetrievalService, AnswererService, QAService
- Identified QATurn persistence pattern with feature-based storage
- Found fallback handling pattern for no-source scenarios
- Mapped existing models: LectureSession, SpeechEvent, QATurn

## Files Created

1. `.claude/docs/research/f4-lecture-qa.md`
   - Complete research summary covering all 4 research areas
   - Integration guidance with existing patterns
   - Implementation recommendations

2. `.claude/docs/libraries/rank-bm25.md`
   - Complete API reference
   - Usage examples including Lecture QA pattern
   - Parameter tuning guide
   - Japanese tokenization integration

3. `.claude/logs/agent-teams/f4-lecture-qa/researcher.md`
   - This work log

## Key Findings for Architect

### Constraints Identified
1. **BM25 Limitations**: No incremental index updates, requires full rebuild
2. **No Azure AI Search**: Must use local BM25 only
3. **Multi-field Challenge**: rank-bm25 doesn't natively support multi-field ranking (speech + visual)
4. **Japanese Tokenization**: Requires integration with SudachiPy or MeCab
5. **Verifier Latency**: Additional LLM call adds latency to QA pipeline

### Design Recommendations
1. Use separate BM25 indexes with score fusion for speech + visual content
2. Implement VerifierService as separate service layer component
3. Reuse QATurn model with `feature="lecture_qa"` for persistence
4. Apply 256-512 token chunking with 10-20% overlap for transcripts
5. Implement claim-by-claim verification pattern for fact-checking

### Alternatives Considered
- **bm25s**: Faster sparse-matrix implementation (future optimization)
- **retriv**: Production-scale retrieval (rank-bm25 author's recommendation for scale)

## Sources

- [rank-bm25 PyPI](https://pypi.org/project/rank-bm25/)
- [rank-bm25 GitHub](https://github.com/dorianbrown/rank_bm25)
- [Azure OpenAI On Your Data API](https://learn.microsoft.com/en-us/azure/ai-services/openai/references/on-your-data)
- [FactSelfCheck: Fact-Level Hallucination Detection (arXiv 2025)](https://arxiv.org/abs/2503.17229)
- [Semantic Entropy Probes (arXiv 2025)](http://arxiv.org/html/2406.15927v1)
- [Claim Verification in LLMs (arXiv 2024)](https://arxiv.org/html/2408.14317v1)
- [Amazon Bedrock Hallucination Reduction](https://aws.amazon.com/blogs/machine-learning/reducing-hallucinations-in-large-language-models-with-custom-intervention-using-amazon-bedrock-agents/)
