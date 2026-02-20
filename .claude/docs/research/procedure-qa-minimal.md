# Sprint2 Procedure QA Minimal Research

## Project Brief

- Feature: `procedure-qa-minimal`
- Goal: Implement a minimal campus procedure QA flow first, fixing retrieval/grounding contracts before real Azure integrations.
- In scope:
  - `POST /api/v4/procedure/ask`
  - Retrieval service interface
  - Answerer service interface
  - `qa_turns` persistence
  - Rootless-answer prohibition logic
- Out of scope:
  - Azure AI Search real connection
  - Azure OpenAI real connection
  - UI
- Constraints:
  - TDD-first
  - Start with fake retriever + fake answerer
  - Return fallback when `sources` is empty
  - Always return `confidence`, `sources`, `action_next`

## Contract Constraints from SPEC

From `docs/SPEC.md`:

- Endpoint: `POST /api/v4/procedure/ask`
- Output fields: `answer`, `confidence`, `sources`, `action_next`, `fallback`
- Rule: if `sources` is empty, fallback must be returned.

## Minimal Domain Contract (Recommended)

### Request

- `query: str`
- `lang_mode: Literal["ja", "easy-ja", "en"] = "ja"` (or `str` in minimal first step, with enum hardening later)

### Response

- `answer: str`
- `confidence: Literal["high", "medium", "low"]`
- `sources: list[ProcedureSource]`
- `action_next: str`
- `fallback: str`

### Source Item

- `title: str`
- `section: str`
- `snippet: str`
- `source_id: str`

## Rootless-Answer Guardrail

Deterministic rule for minimal version:

1. Retriever returns candidate sources.
2. If candidate sources are empty:
   - Do not call answerer.
   - Return fallback response with:
     - `answer` = fallback-safe message
     - `confidence` = `"low"`
     - `sources` = `[]`
     - `action_next` = safe guidance to official office/contact
     - `fallback` = non-empty explanation
3. Persist this turn in `qa_turns`.

This locks in the non-rootless policy before introducing LLM variability.

## Persistence Mapping for `qa_turns`

`docs/SPEC.md` defines one shared table for lecture/procedure QA.  
For Sprint2 minimal:

- `feature` = `"procedure_qa"`
- `session_id` = `NULL`
- `question` = request query
- `answer` = returned answer (or fallback message)
- `confidence` = returned confidence
- `citations_json` = serialized procedure `sources`
- `retrieved_chunk_ids_json` = serialized list of `source_id` values
- `latency_ms` = measured end-to-end processing time
- `verifier_supported` = `False` (verifier out of scope for minimal)

## Interface Design (Fake-first)

### Retriever interface

- `retrieve(query: str, lang_mode: str, limit: int = 3) -> list[ProcedureSource]`

### Answerer interface

- `answer(query: str, lang_mode: str, sources: list[ProcedureSource]) -> ProcedureAnswerDraft`

Fake implementations:

- `FakeProcedureRetriever`: static source hit for known keywords, empty list otherwise.
- `FakeProcedureAnswerer`: deterministic answer synthesis from first source snippet.

## Risks and Mitigations

- Risk: contract drift before Azure integration.
  - Mitigation: freeze schema + interface now and test as public contract.
- Risk: fallback paths not persisted.
  - Mitigation: add unit/integration tests that assert `qa_turns` row on both evidence/no-evidence paths.
- Risk: overfitting fake behavior.
  - Mitigation: keep fakes deterministic but minimal; validate only contract, not language quality.

