---
phase: "06B"
plan: "04"
type: tdd
wave: 3
depends_on: ["06B-02"]
files_modified:
  - "src/term_inventory/classifier.py"
  - "src/term_inventory/schemas.py"
autonomous: true
requirements:
  - "FR2-04"
  - "FR2-05"
---

<objective>
Build the LLM-assisted entity_type and medical_domain classification for non-authoritative source terms. Authoritative sources (ICD-10, RxNorm, openFDA) already carry their own entity metadata — only non-authoritative terms (vimedcss_seed, abbreviation_list, nlm_lab) need LLM classification. All LLM-classified terms are flagged `llm_generated_candidate=true` and `review_status=not_verified` until human review.

Purpose: The LLM classifier extends authoritative source metadata to supplementary terms. The critical constraint: LLM-generated candidates must be clearly distinguishable from verified terms in the output inventory.
Output: `src/term_inventory/classifier.py` with LLM classification, flagged terms ready for human review queue.
</objective>

<execution_context>
@$HOME/.cursor/get-shit-done/workflows/execute-plan.md
</execution_context>

<context>
@src/llm/classifier.py
@src/llm/schemas.py
@src/term_inventory/schemas.py
@.planning/phases/06B-medical-term-inventory-extended/06B-01-PLAN.md
@.planning/phases/06B-medical-term-inventory-extended/06B-02-PLAN.md

## Phase 2 TermClassifier Pattern (to reuse)

From `src/llm/classifier.py`:
- Uses `openai.OpenAI` with `response_format=TermClassificationBatchResponse`
- Batch size: 50 terms per API call
- Confidence threshold: 0.80 → `needs_human_review = True` below this
- Audit log: writes JSONL with request/response payloads
- Retry logic: 3 attempts, exponential backoff
- Model fallback: configured model → gpt-4o-mini

## FR2-04 Entity Types (14 values from Plan 01)

disease, drug, lab_test, procedure, anatomy, symptom, abbreviation, hormone, biomarker, pathogen, device, unit, dosage, unknown

## Medical Domains (from Phase 2 MedicalDomain enum)

Medical Sciences, Pathology & Pathogens, Treatments, Nutrition, Diagnostics, unknown

## Key Requirements

1. Only classify terms where `source_name` is NOT in: icd10, rxnorm, openfda
2. ICD-10 disease terms → entity_type=disease (already set by loader)
3. RxNorm drug terms → entity_type=drug (already set by loader)
4. openFDA device terms → entity_type=device (already set by loader)
5. All LLM-classified terms → `llm_generated_candidate=True`, `review_status=not_verified`
6. Confidence threshold 0.80 → below this, `needs_human_review=True`
7. Classify both `entity_type` and `medical_domain`
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: RED — Write tests for LLM term classifier</name>
  <files>tests/test_term_inventory_classifier.py</files>
  <action>
Create `tests/test_term_inventory_classifier.py`:

```python
import pytest
from src.term_inventory.classifier import MedicalTermClassifier
```

Write test cases for `MedicalTermClassifier`:

1. `test_classify_only_non_authoritative_terms()`:
   - Create DataFrame with mixed sources: rxnorm (authoritative), vimedcss_seed (non-authoritative)
   - Mock LLM client returns classification for vimedcss_seed terms
   - Assert: rxnorm terms NOT sent to LLM (preserve authoritative entity_type)
   - Assert: vimedcss_seed terms ARE sent to LLM

2. `test_authoritative_terms_preserved()`:
   - DataFrame with icd10, rxnorm, openfda rows
   - After classification: assert entity_type unchanged for all authoritative rows

3. `test_llm_candidate_flag_set()`:
   - Non-authoritative term → LLM classification
   - Assert: `llm_generated_candidate=True`
   - Assert: `review_status=not_verified`

4. `test_confidence_threshold_review()`:
   - Mock LLM returns confidence=0.75 (< 0.80 threshold)
   - Assert: `needs_human_review=True` for that term
   - Mock LLM returns confidence=0.85 (>= 0.80)
   - Assert: `needs_human_review=False` for that term

5. `test_batch_classification_batching()`:
   - 75 terms (3 batches of 25)
   - Verify 3 API calls made

6. `test_skip_when_already_classified()`:
   - DataFrame where non-authoritative term already has entity_type != unknown
   - Should still classify (medical_domain may be missing)

Run tests initially — expect FAIL (classifier not yet implemented).
</action>
  <verify>
cd /home/thanhnndev/develop/projects/vimedcss-eval-pipeline && python -m pytest tests/test_term_inventory_classifier.py -v --collect-only 2>&1 | head -20 && python -m pytest tests/test_term_inventory_classifier.py -v --tb=short 2>&1 | tail -20
</verify>
  <done>Test file created, tests fail (classifier not yet implemented). RED phase complete.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: GREEN — Implement MedicalTermClassifier</name>
  <files>src/term_inventory/classifier.py</files>
  <action>
Create `src/term_inventory/classifier.py`:

```python
"""LLM-assisted term classification for Phase 6b medical term inventory.

Only non-authoritative source terms (vimedcss_seed, abbreviation_list, nlm_lab)
are sent to LLM for entity_type and medical_domain classification.
Authoritative sources (icd10, rxnorm, openfda) already carry entity metadata.
"""
import os
import json
import time
from typing import Dict, Any, List, Optional
import pandas as pd
from openai import OpenAI
from src.term_inventory.schemas import EntityType, ReviewStatus, TermSource, InventoryConfig
from src.shared.logging import setup_logger

logger = setup_logger("term_inventory.classifier")

AUTHORITATIVE_SOURCES = {"icd10", "rxnorm", "openfda"}
```

Implement `MedicalTermClassifier`:

1. `__init__(self, config: InventoryConfig)`:
   - Load `llm.yaml` config for OpenAI settings (model, batch_size, max_retries)
   - Initialize OpenAI client if `OPENAI_API_KEY` env var present, else raise ValueError
   - Store `confidence_threshold = config.confidence_threshold` (default 0.80)

2. `classify(df: pd.DataFrame) -> pd.DataFrame`:
   - Identify non-authoritative terms: where `source_name` not in AUTHORITATIVE_SOURCES
   - For those rows, extract terms for batch classification
   - Call `_classify_batch(batch)` for each batch
   - Update DataFrame: set `entity_type`, `medical_domain`, `llm_generated_candidate=True`, `review_status=not_verified`, `needs_human_review` based on confidence
   - Log: "Classified {N} non-authoritative terms from {M} sources"
   - Return updated DataFrame

3. `_classify_batch(batch: List[Dict]) -> List[Dict]`:
   - Build system prompt (Vietnamese) + user prompt JSON with batch terms
   - Make OpenAI `beta.chat.completions.parse` call with `response_format=InventoryClassificationBatchResponse`
   - Retry up to `max_retries` times with exponential backoff
   - Log audit record
   - Return list of classification results

4. `_build_system_prompt() -> str`:
   - Vietnamese language
   - Entity types: disease, drug, lab_test, procedure, anatomy, symptom, abbreviation, hormone, biomarker, pathogen, device, unit, dosage, unknown
   - Medical domains: Medical Sciences, Pathology & Pathogens, Treatments, Nutrition, Diagnostics, unknown
   - Important: classify entity_type and medical_domain; do NOT fabricate source info

5. `_log_audit(request: Dict, response: Dict)`:
   - Append JSONL to `logs/term_inventory_classification_audit.jsonl`
   - Include model, duration, request/response payloads

6. Mock mode (`--mock`): Generate keyword-based mock classifications when `OPENAI_API_KEY` is not set, using Phase 2's mock pattern.

Include `@retry` decorator from `tenacity` for API calls.
</action>
  <verify>
cd /home/thanhnndev/develop/projects/vimedcss-eval-pipeline && python -m pytest tests/test_term_inventory_classifier.py -v --tb=short 2>&1 | tail -30
</verify>
  <done>MedicalTermClassifier implemented. All tests pass.</done>
</task>

<task type="auto">
  <name>Task 3: REFACTOR — Add Pydantic schema for LLM classification response</name>
  <files>src/term_inventory/schemas.py</files>
  <action>
Add to `src/term_inventory/schemas.py`:

```python
class InventoryClassificationBatchResponse(BaseModel):
    """OpenAI structured output schema for batch term classification."""
    items: List["InventoryClassificationItem"] = Field(default_factory=list)

class InventoryClassificationItem(BaseModel):
    """Classification result for a single term."""
    term_original: str = Field(..., description="Original term as submitted")
    entity_type: EntityType = Field(..., description="FR2-04 entity type")
    medical_domain: str = Field(..., description="Medical domain: Medical Sciences, Pathology & Pathogens, Treatments, Nutrition, Diagnostics, unknown")
    confidence: float = Field(..., ge=0.0, le=1.0)
    needs_human_review: bool
    evidence: Optional[str] = Field(None, description="Reasoning for classification")
    uncertainty_reason: Optional[str] = Field(None, description="Why confidence is low")
```

Update `InventoryClassificationBatchResponse` model_rebuild() to fix forward reference.
</action>
  <verify>
python -c "from src.term_inventory.schemas import InventoryClassificationBatchResponse, InventoryClassificationItem; print('Classification schemas OK')"
</verify>
  <done>Pydantic models for LLM classification response defined. Forward reference resolved.</done>
</task>

</tasks>

<verification>
python -c "
from src.term_inventory.classifier import MedicalTermClassifier
from src.term_inventory.schemas import InventoryConfig
from src.llm.schemas import TermClassificationBatchResponse
import pandas as pd

# Verify classifier instantiates without OpenAI key
try:
    config = InventoryConfig()
    # Will fail on classify() without key, but import+instantiate should work
    print('Classifier module loaded OK')
except ValueError:
    print('Classifier loaded (needs API key for live run)')

# Verify schema compatibility
from src.term_inventory.schemas import InventoryClassificationBatchResponse, InventoryClassificationItem
print('All classification schemas imported OK')
"
</verification>

<success_criteria>
- MedicalTermClassifier only sends non-authoritative terms to LLM
- Authoritative source terms (icd10, rxnorm, openfda) preserve their entity_type from the loader
- All LLM-classified terms get `llm_generated_candidate=True` and `review_status=not_verified`
- Confidence below 0.80 sets `needs_human_review=True`
- Audit log written to `logs/term_inventory_classification_audit.jsonl`
- Mock mode generates keyword-based classifications without API key
- All pytest tests pass
</success_criteria>

<output>
Create `.planning/phases/06B-medical-term-inventory-extended/06B-04-SUMMARY.md` when done
</output>
