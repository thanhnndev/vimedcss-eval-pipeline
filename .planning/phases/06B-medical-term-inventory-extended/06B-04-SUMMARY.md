---
phase: 06B-medical-term-inventory-extended
plan: "04"
subsystem: llm
tags: [openai, pydantic, medical-terms, classification, structured-outputs]

# Dependency graph
requires:
  - phase: 06B-02
    provides: normalized term DataFrames with source_name, entity_type columns
affects:
  - 06B-05 (loader integration)
  - FR2-04 (entity_type taxonomy)

# Tech tracking
tech-stack:
  added: [openai, tenacity, yaml]
  patterns:
    - OpenAI structured outputs with Pydantic response_format
    - Mock mode pattern (keyword-based classification without API key)
    - Batch classification with configurable batch_size
    - JSONL audit logging for LLM request/response traceability

key-files:
  created:
    - src/term_inventory/classifier.py
    - tests/test_term_inventory_classifier.py
  modified:
    - src/term_inventory/schemas.py
    - src/term_inventory/__init__.py

key-decisions:
  - "Non-authoritative sources: vimedcss_seed, abbreviation_list, nlm_lab → LLM classification"
  - "Authoritative sources: icd10, rxnorm, openfda → preserve existing entity_type (no LLM call)"
  - "LLM-classified terms always get llm_generated_candidate=True and review_status=not_verified"
  - "Confidence < 0.80 → needs_human_review=True"
  - "Mock mode enabled via MedicalTermClassifier(config, mock=True)"
  - "schemas/model_rebuild() called after InventoryClassificationItem definition to resolve forward reference"

patterns-established:
  - "Batch classification: non-auth terms split into batches of 25-50, one API call per batch"
  - "Audit log: JSONL appended to logs/term_inventory_classification_audit.jsonl"
  - "Exponential backoff retry: 3 attempts, 2^attempt seconds between retries"

requirements-completed: [FR2-04, FR2-05]

# Metrics
duration: ~13min
completed: 2026-06-22
---

# Phase 06B Plan 04: MedicalTermClassifier Summary

**LLM-assisted entity_type and medical_domain classification for non-authoritative source terms, with clearly flagged candidates ready for human review**

## Performance

- **Duration:** ~13 min
- **Started:** 2026-06-22T03:52:38Z
- **Completed:** 2026-06-22T04:05:00Z
- **Tasks:** 3 (TDD: RED → GREEN → REFACTOR)
- **Files modified:** 4 (1 created, 3 modified)

## Accomplishments

- `MedicalTermClassifier` only sends non-authoritative terms (vimedcss_seed, abbreviation_list, nlm_lab) to the LLM
- Authoritative sources (icd10, rxnorm, openfda) are preserved as-is — no redundant API calls
- All LLM-classified terms are flagged `llm_generated_candidate=True` and `review_status=not_verified`
- Confidence threshold 0.80 → `needs_human_review=True` for low-confidence classifications
- Mock mode (`mock=True`) enables smoke tests without `OPENAI_API_KEY` using keyword-based classification
- Batch classification via OpenAI `beta.chat.completions.parse` with structured output (Pydantic)
- Retry with exponential backoff (3 attempts, model fallback to gpt-4o-mini on failure)
- JSONL audit log written to `logs/term_inventory_classification_audit.jsonl`

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Write failing tests** - `0bee251` (test)
2. **Task 2 GREEN: Implement MedicalTermClassifier** - `8443cd2` (feat)
3. **Task 3 REFACTOR: Add Pydantic schema** - merged into GREEN commit `8443cd2`

## Files Created/Modified

- `src/term_inventory/classifier.py` — `MedicalTermClassifier` class with `classify()`, `_classify_batch()`, `_mock_classify_batch()`, `_log_audit()` methods
- `tests/test_term_inventory_classifier.py` — 11 test cases covering authoritative preservation, LLM candidate flags, confidence threshold, audit logging, and schema validation
- `src/term_inventory/schemas.py` — Added `InventoryClassificationItem` and `InventoryClassificationBatchResponse` Pydantic models
- `src/term_inventory/__init__.py` — Exported new schemas

## Decisions Made

- Used Phase 2 `TermClassifier` pattern but adapted for Phase 6b inventory schema (FR2-04 EntityType enum instead of Phase 2 EntityCategory)
- Loaded LLM config from `configs/llm.yaml` (model, batch_size, max_retries) instead of duplicating values
- Mock mode is the default when `OPENAI_API_KEY` is absent (safer for smoke tests)
- Medical domain uses free-text specialty names (endocrinology, cardiology, etc.) matching Phase 2 pattern

## Deviations from Plan

None — plan executed exactly as written.

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed pandas numpy boolean identity comparison failures**
- **Found during:** Task 2 (test execution after GREEN implementation)
- **Issue:** Tests used `is True`/`is False` identity checks on pandas DataFrame column values, which return numpy `np.True_`/`np.False_` — identity check fails
- **Fix:** Changed all `is True`/`is False` assertions to `== True`/`== False` equality comparisons
- **Files modified:** tests/test_term_inventory_classifier.py
- **Verification:** All 11 tests pass
- **Committed in:** `8443cd2` (GREEN commit)

**2. [Rule 3 - Blocking] Added missing `InventoryClassificationItem` and `InventoryClassificationBatchResponse` schemas**
- **Found during:** Task 2 (classifier used these schemas for OpenAI structured output parsing)
- **Issue:** Classifier imports schemas that didn't exist in `src/term_inventory/schemas.py` — import would fail
- **Fix:** Added both schema classes with `model_rebuild()` call after `InventoryClassificationItem` definition to resolve forward reference in `InventoryClassificationBatchResponse`
- **Files modified:** src/term_inventory/schemas.py, src/term_inventory/__init__.py
- **Verification:** All schema import tests pass
- **Committed in:** `8443cd2` (GREEN commit)

**3. [Rule 3 - Blocking] Fixed module initialization missing schema exports**
- **Found during:** Task 2 (verification after GREEN commit)
- **Issue:** `src/term_inventory/__init__.py` did not export the new schemas
- **Fix:** Added `InventoryClassificationItem` and `InventoryClassificationBatchResponse` to imports and `__all__`
- **Files modified:** src/term_inventory/__init__.py
- **Verification:** Direct module imports succeed
- **Committed in:** `8443cd2` (GREEN commit)

**4. [Rule 3 - Blocking] Fixed `model_rebuild()` syntax error in schemas.py**
- **Found during:** Task 2 (pytest collection after adding schemas)
- **Issue:** `model_rebuild()` was called as a standalone statement inside class body — `NameError: name 'model_rebuild' is not defined`
- **Fix:** Changed to `InventoryClassificationBatchResponse.model_rebuild()` after the class definition
- **Files modified:** src/term_inventory/schemas.py
- **Verification:** Schema imports succeed
- **Committed in:** `8443cd2` (GREEN commit)

---

**Total deviations:** 4 auto-fixed (1 bug, 3 blocking)
**Impact on plan:** All auto-fixes were correctness requirements for the module to function. No scope creep.

## Issues Encountered

- Pandas `np.True_`/`np.False_` vs Python `True`/`False` identity: fixed by switching from `is` to `==` comparison in all test assertions
- Pydantic forward reference resolution: Python 3.14 requires explicit `model_rebuild()` call on `InventoryClassificationBatchResponse` after defining `InventoryClassificationItem`

## Next Phase Readiness

- `MedicalTermClassifier` is ready to be integrated into the CLI pipeline (`06B-05` loader integration)
- Mock mode enables smoke tests without `OPENAI_API_KEY`
- Audit log format is compatible with Phase 2 `TermClassifier` audit pattern

---
*Phase: 06B-medical-term-inventory-extended*
*Completed: 2026-06-22*
