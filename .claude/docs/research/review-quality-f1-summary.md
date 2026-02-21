# Quality Review Report: F1 Azure OpenAI Summary Integration

**Date**: 2026-02-21
**Reviewer**: Quality Reviewer (general-purpose agent)
**Scope**: F1 Azure OpenAI Summary Integration

---

## Executive Summary

Reviewed 3 files (1,170 lines of code) for code quality adherence. Found **6 findings**:
- **High Severity**: 2 (file length violations)
- **Medium Severity**: 3 (code complexity, unnecessary object creation)
- **Low Severity**: 1 (function length)

---

## Files Reviewed

| File | Lines | Status |
|------|-------|--------|
| `app/services/lecture_summary_generator_service.py` | 408 | NEW |
| `app/services/lecture_summary_service.py` | 441 | MODIFIED |
| `app/api/v4/lecture.py` | 321 | MODIFIED |

---

## Findings

### High Severity

#### 1. File Length Violation - lecture_summary_service.py

**Severity**: High
**File**: `app/services/lecture_summary_service.py`
**Line**: 1-441 (441 lines total)

**Issue**:
File exceeds 400-line target (guideline: 200-400 lines, max 800).

**Current Code**:
```python
# File contains 441 lines with multiple responsibilities:
# - Summary window building logic
# - Evidence tag construction
# - Key term extraction
# - Database upsert operations
```

**Suggested Improvement**:
Split into smaller files:
- `lecture_summary_window_builder.py` - Window building logic
- `lecture_summary_evidence_builder.py` - Evidence/tag construction
- Keep service as orchestrator only

---

#### 2. File Length Borderline - lecture_summary_generator_service.py

**Severity**: High
**File**: `app/services/lecture_summary_generator_service.py`
**Line**: 1-408 (408 lines total)

**Issue**:
File at 408 lines, borderline for guideline (200-400 lines target). Long methods contribute to length.

**Current Code**:
```python
# _parse_response method is 78 lines
# _call_openai method is 65 lines
```

**Suggested Improvement**:
Extract helper methods for:
- Response field validation (`_validate_choices`, `_validate_message`, etc.)
- Request building (`_build_request_body`, `_build_headers`)

---

### Medium Severity

#### 3. Unnecessary Object Creation in Loop

**Severity**: Medium
**File**: `app/services/lecture_summary_service.py`
**Line**: 152-156

**Issue**:
`evidence_type_map` dictionary is recreated on every call despite being constant.

**Current Code**:
```python
    async def _build_window(
        self,
        *,
        session_id: str,
        window_end_ms: int,
        persist: bool,
        lang_mode: str = "ja",
    ) -> LectureSummaryLatestResponse:
        # ... code ...
        summary_text = summary_result.summary

        # Map evidence tags from generator result to schema format
        evidence_type_map = {
            "speech": "speech",
            "slide": "slide",
            "board": "board",
        }
```

**Suggested Improvement**:
Move to module-level constant:

```python
# At module level (top of file)
EVIDENCE_TYPE_MAP: dict[str, str] = {
    "speech": "speech",
    "slide": "slide",
    "board": "board",
}

# In method
evidence_type = EVIDENCE_TYPE_MAP.get(tag["type"])
```

---

#### 4. Nested Loop Complexity

**Severity**: Medium
**File**: `app/services/lecture_summary_service.py`
**Line**: 158-172 (21 lines)

**Issue**:
O(n*m) nested loop for matching terms to evidence tags. Could be inefficient with many terms/tags.

**Current Code**:
```python
        key_terms = []
        for term in summary_result.key_terms:
            # Find matching evidence tags for this term
            term_evidence_tags = []
            for tag in summary_result.evidence_tags:
                if term in tag.get("text", ""):
                    evidence_type = evidence_type_map.get(tag["type"])
                    if evidence_type:
                        term_evidence_tags.append(evidence_type)
            # Ensure at least one evidence tag (use "speech" as default)
            if not term_evidence_tags:
                term_evidence_tags = ["speech"]
            key_terms.append(
                LectureSummaryKeyTerm(term=term, evidence_tags=term_evidence_tags)
            )
```

**Suggested Improvement**:
Extract to method and use set for deduplication:

```python
    def _build_key_terms_with_evidence(
        self,
        summary_result: LectureSummaryResult,
        evidence_type_map: dict[str, str],
    ) -> list[LectureSummaryKeyTerm]:
        """Build key terms with associated evidence tags."""
        key_terms = []
        for term in summary_result.key_terms:
            term_evidence_tags = self._find_evidence_tags_for_term(
                term, summary_result.evidence_tags, evidence_type_map
            )
            key_terms.append(
                LectureSummaryKeyTerm(
                    term=term,
                    evidence_tags=term_evidence_tags or ["speech"]
                )
            )
        return key_terms

    def _find_evidence_tags_for_term(
        self,
        term: str,
        evidence_tags: list[dict[str, str]],
        evidence_type_map: dict[str, str],
    ) -> list[str]:
        """Find evidence types that contain this term in their text."""
        evidence_types = set()
        for tag in evidence_tags:
            if term in tag.get("text", ""):
                evidence_type = evidence_type_map.get(tag["type"])
                if evidence_type:
                    evidence_types.add(evidence_type)
        return list(evidence_types)
```

---

#### 5. Long Method with Deep Nesting

**Severity**: Medium
**File**: `app/services/lecture_summary_generator_service.py`
**Line**: 319-408 (78 lines)

**Issue**:
`_parse_response` method is too long with nested try-except and multiple validation steps.

**Current Code**:
```python
    def _parse_response(self, response_json: dict[str, object]) -> LectureSummaryResult:
        """Parse Azure OpenAI JSON response and validate structure."""
        try:
            choices = response_json.get("choices")
            if not isinstance(choices, list) or not choices:
                raise ValueError("missing choices")

            first_choice = choices[0]
            if not isinstance(first_choice, dict):
                raise ValueError("invalid choice payload")

            first_choice_dict = {str(key): value for key, value in first_choice.items()}
            message = first_choice_dict.get("message")
            if not isinstance(message, dict):
                raise ValueError("missing message")

            message_dict = {str(key): value for key, value in message.items()}
            content = message_dict.get("content")
            if not isinstance(content, str):
                raise ValueError("missing content")

            # Parse the JSON content
            result = json.loads(content)

            summary = result.get("summary", "")
            if not isinstance(summary, str):
                raise ValueError("summary must be a string")

            # Enforce 600-char limit server-side
            if len(summary) > self.MAX_SUMMARY_CHARS:
                summary = summary[: self.MAX_SUMMARY_CHARS]

            key_terms = result.get("key_terms", [])
            if not isinstance(key_terms, list):
                raise ValueError("key_terms must be a list")

            # Validate key_terms are strings
            validated_key_terms: list[str] = []
            for term in key_terms:
                if isinstance(term, str) and term.strip():
                    validated_key_terms.append(term.strip())

            evidence = result.get("evidence", [])
            if not isinstance(evidence, list):
                raise ValueError("evidence must be a list")

            # Validate evidence tags
            allowed_types = {"speech", "slide", "board"}
            validated_evidence: list[dict[str, str]] = []
            for tag in evidence:
                if not isinstance(tag, dict):
                    continue

                tag_type = tag.get("type", "")
                if tag_type not in allowed_types:
                    continue

                timestamp = tag.get("timestamp", "")
                text = tag.get("text", "")

                if isinstance(timestamp, str) and isinstance(text, str):
                    validated_evidence.append(
                        {
                            "type": tag_type,
                            "timestamp": timestamp,
                            "text": text,
                        }
                    )

            return LectureSummaryResult(
                summary=summary,
                key_terms=validated_key_terms,
                evidence_tags=validated_evidence,
            )

        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            logger.warning("azure_openai_summary_response_parse_error")
            raise LectureSummaryGeneratorError(
                "azure openai summary response parse failure"
            ) from exc
```

**Suggested Improvement**:
Extract validation helpers:

```python
    def _parse_response(self, response_json: dict[str, object]) -> LectureSummaryResult:
        """Parse Azure OpenAI JSON response and validate structure."""
        try:
            content = self._extract_content_from_response(response_json)
            result = json.loads(content)

            summary = self._validate_and_truncate_summary(result)
            key_terms = self._validate_key_terms(result)
            evidence_tags = self._validate_evidence_tags(result)

            return LectureSummaryResult(
                summary=summary,
                key_terms=key_terms,
                evidence_tags=evidence_tags,
            )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            logger.warning("azure_openai_summary_response_parse_error")
            raise LectureSummaryGeneratorError(
                "azure openai summary response parse failure"
            ) from exc

    def _extract_content_from_response(self, response_json: dict[str, object]) -> str:
        """Extract content string from Azure OpenAI response structure."""
        choices = response_json.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError("missing choices")

        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise ValueError("invalid choice payload")

        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise ValueError("missing message")

        content = message.get("content")
        if not isinstance(content, str):
            raise ValueError("missing content")

        return content

    def _validate_and_truncate_summary(self, result: dict) -> str:
        """Validate summary field and enforce character limit."""
        summary = result.get("summary", "")
        if not isinstance(summary, str):
            raise ValueError("summary must be a string")
        if len(summary) > self.MAX_SUMMARY_CHARS:
            summary = summary[: self.MAX_SUMMARY_CHARS]
        return summary

    def _validate_key_terms(self, result: dict) -> list[str]:
        """Validate and sanitize key_terms list."""
        key_terms = result.get("key_terms", [])
        if not isinstance(key_terms, list):
            raise ValueError("key_terms must be a list")

        validated = []
        for term in key_terms:
            if isinstance(term, str) and term.strip():
                validated.append(term.strip())
        return validated

    def _validate_evidence_tags(self, result: dict) -> list[dict[str, str]]:
        """Validate and sanitize evidence tags list."""
        evidence = result.get("evidence", [])
        if not isinstance(evidence, list):
            raise ValueError("evidence must be a list")

        allowed_types = {"speech", "slide", "board"}
        validated = []

        for tag in evidence:
            if not isinstance(tag, dict):
                continue

            tag_type = tag.get("type", "")
            if tag_type not in allowed_types:
                continue

            timestamp = tag.get("timestamp", "")
            text = tag.get("text", "")

            if isinstance(timestamp, str) and isinstance(text, str):
                validated.append({
                    "type": tag_type,
                    "timestamp": timestamp,
                    "text": text,
                })

        return validated
```

---

### Low Severity

#### 6. Medium-Length Method with Mixed Concerns

**Severity**: Low
**File**: `app/services/lecture_summary_generator_service.py`
**Line**: 234-298 (65 lines)

**Issue**:
`_call_openai` mixes URL building, payload construction, and HTTP execution. Acceptable but could be cleaner.

**Suggested Improvement**:
Extract payload building to helper (optional - current code is acceptable):

```python
    def _build_request_payload(self, prompt: str) -> dict:
        """Build Azure OpenAI request payload."""
        return {
            "messages": [
                {
                    "role": "system",
                    "content": "You are a lecture summarization assistant. "
                              "Always respond with valid JSON only.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
            "response_format": {"type": "json_object"},
        }

    async def _call_openai(self, prompt: str) -> dict[str, object]:
        """Call Azure OpenAI chat completion endpoint with JSON response format."""
        url = self._build_chat_completion_url()
        payload = self._build_request_payload(prompt)
        # ... rest of method
```

---

## Positive Findings

### What Went Well

1. **Type Hints**: All methods have complete type annotations
2. **Error Handling**: Comprehensive exception handling with specific error types
3. **Early Returns**: Good use of early returns in validation methods
4. **Constants**: Magic numbers extracted to class constants (`MAX_SUMMARY_CHARS`, `DEFAULT_MODEL`, etc.)
5. **Docstrings**: All public methods have descriptive docstrings
6. **Protocol Pattern**: Clean interface/implementation separation
7. **Naming**: Clear, descriptive names throughout
8. **Immutability**: No in-place mutations of input data
9. **API Layer**: `lecture.py` is thin and delegates correctly to services
10. **Security**: No hardcoded secrets, uses environment variables

---

## Library Constraints Check

### Azure OpenAI Integration
- [x] JSON response format enforced (`response_format: {"type": "json_object"}`)
- [x] Server-side validation of response structure
- [x] Character limit enforced (600 chars)
- [x] Error handling for HTTP/Network/Parse failures
- [x] Timeout configuration available

### No violations found.

---

## Recommendations

### Priority Actions

1. **Refactor `lecture_summary_service.py`** (High Priority)
   - Split into multiple files to get under 400 lines
   - Extract evidence/tag building to separate module

2. **Extract `_parse_response` helpers** (Medium Priority)
   - Break down 78-line method into 4-5 smaller validators
   - Will also reduce overall file length

3. **Module-level constant for `evidence_type_map`** (Low Priority)
   - Simple fix, removes unnecessary object creation

### Optional Improvements

4. Extract `_build_request_payload` from `_call_openai` (Low Priority - current code acceptable)
5. Consider extracting nested key_terms building logic (Medium Priority for performance with large datasets)

---

## Summary Score

| Criterion | Score | Notes |
|-----------|-------|-------|
| Single Responsibility | 7/10 | File length issues, but class responsibilities clear |
| Early Returns | 9/10 | Good use throughout |
| Type Hints | 10/10 | Complete coverage |
| No Magic Numbers | 10/10 | All constants defined |
| Naming Clarity | 10/10 | Clear, descriptive names |
| Function Length | 7/10 | Some methods too long (_parse_response: 78 lines) |
| Code Quality | 8/10 | Overall solid, room for refactoring |

**Overall**: 8.7/10 - Good quality with actionable improvements identified.
