---
phase: "06B"
plan: "02"
type: execute
wave: 2
depends_on: ["06B-01"]
files_modified:
  - "src/term_inventory/normalizer.py"
autonomous: true
requirements:
  - "FR2-03"
---

<objective>
Build the normalization pipeline that transforms raw ingested terms into canonical normalized forms, tracks every transformation in `term_normalization_map.csv`, and performs within-entity-type deduplication to prevent merge conflicts.

Purpose: Normalization is the foundation for deduplication and matching. Without it, "β-blocker" and "beta-blocker" would be counted as different terms. The normalization map provides full traceability for every transformation.
Output: `data/terms/term_normalization_map.csv`, deduplicated `medical_term_inventory.csv` with `term_normalized` column populated.
</objective>

<execution_context>
@$HOME/.cursor/get-shit-done/workflows/execute-plan.md
</execution_context>

<context>
@src/term_inventory/schemas.py
@src/term_inventory/loaders/icd10_backbone.py
@.planning/phases/06B-medical-term-inventory-extended/06B-RESEARCH.md
@.planning/phases/06B-medical-term-inventory-extended/06B-01-PLAN.md

## Normalization Requirements (from 06B-RESEARCH.md)

1. **Unicode NFC normalization** — `unicodedata.normalize("NFC", s)` before any comparison
2. **Case folding** — lowercase
3. **Punctuation stripping** — strip common punctuation but preserve medical hyphens
4. **Greek-to-ASCII mapping** — β→beta, α→alpha, μ→mu, γ→gamma, δ→delta, Ω→omega, °→degree
5. **Within entity_type deduplication** — "insulin" as drug and "insulin" as biomarker are separate; deduplicate only when same entity_type AND normalized string matches
6. **Preserve non-matching translations** — EN "hypertension" ≠ VI "tăng huyết áp"

## Normalization Map Schema

The `term_normalization_map.csv` has columns:
- `raw_form`: Original term as ingested
- `normalized_form`: Canonical normalized form
- `entity_type`: Which entity type this normalization applies to
- `transformation`: Description of transformation applied
- `term_id`: Reference to term in inventory

## Key Anti-Patterns from Research

- "β-blocker" (Greek beta) and "beta-blocker" (ASCII) must normalize to the same form
- "Metformin" and "metformin" must deduplicate
- Do NOT deduplicate across entity types — "insulin" can legitimately be both drug AND biomarker
- "hypertension" (EN) and "tăng huyết áp" (VI) are NOT the same — only deduplicate when normalized string matches
</context>

<tasks>

<task type="auto">
  <name>Task 1: Implement normalize_term() function with Unicode NFC + Greek-to-ASCII</name>
  <files>src/term_inventory/normalizer.py</files>
  <action>
Create `src/term_inventory/normalizer.py`:

1. **Imports**: `import unicodedata`, `import re`, `from typing import Optional`

2. **GREEK_TO_ASCII** constant dict:
   - "α"→"alpha", "β"→"beta", "γ"→"gamma", "δ"→"delta", "ε"→"epsilon"
   - "ζ"→"zeta", "η"→"eta", "θ"→"theta", "ι"→"iota", "κ"→"kappa"
   - "λ"→"lambda", "μ"→"mu", "ν"→"nu", "ξ"→"xi", "ο"→"omicron"
   - "π"→"pi", "ρ"→"rho", "σ"→"sigma", "τ"→"tau", "υ"→"upsilon"
   - "φ"→"phi", "χ"→"chi", "ψ"→"psi", "ω"→"omega"
   - "Α"→"Alpha", "Β"→"Beta", "Γ"→"Gamma", "Δ"→"Delta", "Ε"→"Epsilon" (uppercase)
   - "Η"→"Eta", "Θ"→"Theta", "Ι"→"Iota", "Κ"→"Kappa", "Λ"→"Lambda"
   - "Μ"→"Mu", "Ν"→"Nu", "Ξ"→"Xi", "Ο"→"Omicron", "Π"→"Pi"
   - "Ρ"→"Rho", "Σ"→"Sigma", "Τ"→"Tau", "Υ"→"Upsilon", "Φ"→"Phi"
   - "Χ"→"Chi", "Ψ"→"Psi", "Ω"→"Omega"
   - "°"→"degree"

3. **UNIT_SUFFIXES** — list of dosage/unit suffixes to normalize:
   - "mg", "ml", "g", "kg", "mcg", "µg", "ug", "L", "mEq", "IU", "units", "unit"
   - When these suffixes appear at end of term, normalize them consistently

4. **`normalize_term(raw: str, entity_type: Optional[str] = None) -> tuple[str, str]`**:
   - Returns `(normalized_form, transformation_description)`
   - Step 1: Unicode NFC — `unicodedata.normalize("NFC", raw)`
   - Step 2: Greek-to-ASCII — replace all Greek letters using GREEK_TO_ASCII dict
   - Step 3: Case fold — lowercase
   - Step 4: Strip leading/trailing whitespace
   - Step 5: Normalize unit suffixes (e.g., "µg"→"mcg", "ug"→"mcg")
   - Step 6: Collapse multiple spaces
   - Track which transformations were applied as a comma-separated string
   - If no transformation applied, return "none"

5. **`normalize_batch(terms: list[str], entity_types: Optional[list[str]] = None) -> pd.DataFrame`**:
   - For each term, call `normalize_term()`
   - Return DataFrame with columns: `raw_form`, `normalized_form`, `transformation`, `entity_type`
   - If entity_types not provided, use None for all

6. **`apply_normalization(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]`**:
   - Takes a DataFrame with `term_original` column
   - Applies `normalize_term()` to each row
   - Sets `term_normalized` column
   - Returns tuple: `(normalized_df, normalization_map_df)` where normalization_map_df contains only rows where transformation != "none"

Log a warning if >20% of terms have non-"none" transformations (suggests abnormal data).
</action>
  <verify>
python -c "
from src.term_inventory.normalizer import normalize_term, normalize_batch, apply_normalization
import pandas as pd

# Test Greek-to-ASCII
result, trans = normalize_term('β-blocker')
assert result == 'beta-blocker', f'Got: {result}'
result, trans = normalize_term('α-thalassemia')
assert result == 'alpha-thalassemia', f'Got: {result}'
# Test NFC
result, trans = normalize_term('metformin\u0301')  # metformin with combining acute
assert result == 'metformin', f'NFC failed: {result}'
# Test case fold
result, trans = normalize_term('METFORMIN')
assert result == 'metformin', f'Case fold failed: {result}'
# Test unit suffix
result, trans = normalize_term('insulin 100units')
assert 'unit' in result, f'Unit norm failed: {result}'
print('normalize_term tests passed')
"
</verify>
  <done>normalize_term() handles Unicode NFC, Greek-to-ASCII, case folding, unit normalization. normalize_batch() and apply_normalization() produce normalization_map DataFrame.</done>
</task>

<task type="auto">
  <name>Task 2: Implement cross-source deduplication within entity_type</name>
  <files>src/term_inventory/normalizer.py</files>
  <read_first>src/term_inventory/normalizer.py</read_first>
  <action>
Add to `src/term_inventory/normalizer.py`:

1. **`deduplicate_within_entity_type(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]`**:
   - Takes DataFrame with `term_normalized` and `entity_type` columns
   - Groups by `(entity_type, term_normalized)` — deduplication is WITHIN entity type only
   - Conflict resolution when same normalized term appears in same entity_type from multiple sources:
     - `verified` sources win over `needs_review` sources
     - If both are `verified`, prefer authoritative sources in this order: icd10 > rxnorm > openfda > nlm_lab > abbreviation_list > vimedcss_seed > llm_generated
     - Keep the first-occurring row (most authoritative source wins)
   - Returns `(deduplicated_df, duplicate_map_df)` where duplicate_map_df has columns:
     - `canonical_term_id`: The term_id kept
     - `duplicate_term_id`: A term_id that was merged
     - `reason`: Why the duplicate was removed
     - `source_kept`: source_name of the kept term
     - `source_removed`: source_name of the removed term
   - Log summary: "Deduplicated {N} duplicate terms across {M} entity types"
   - Log a warning if >30% of terms were deduplicated (suggests too-aggressive normalization)

2. **`create_deduplication_report(dedup_df: pd.DataFrame) -> pd.DataFrame`**:
   - Group deduplication map by entity_type
   - Count duplicates per entity type
   - Return summary DataFrame with columns: `entity_type`, `total_terms`, `duplicates_removed`, `deduplication_rate`

Add unit tests to validate:
- "β-blocker" and "beta-blocker" (same entity_type) → deduplicate to one
- "insulin" as drug AND "insulin" as biomarker → keep both (different entity_type)
- "metformin" from RxNorm AND "metformin" from seed → prefer RxNorm (verified > needs_review)
</action>
  <verify>
python -c "
from src.term_inventory.normalizer import deduplicate_within_entity_type
import pandas as pd

# Test: same entity_type, different raw forms → deduplicate
df = pd.DataFrame([
    {'term_id': 't1', 'term_original': 'beta-blocker', 'term_normalized': 'beta-blocker', 'entity_type': 'drug', 'source_name': 'rxnorm', 'review_status': 'verified'},
    {'term_id': 't2', 'term_original': 'β-blocker', 'term_normalized': 'beta-blocker', 'entity_type': 'drug', 'source_name': 'llm_generated', 'review_status': 'not_verified'},
])
dedup, dmap = deduplicate_within_entity_type(df)
assert len(dedup) == 1, f'Expected 1 row, got {len(dedup)}'
assert dedup.iloc[0]['source_name'] == 'rxnorm', 'Should prefer verified source'
assert len(dmap) == 1, 'Duplicate map should have 1 entry'
print('Deduplication test 1 passed: verified wins')

# Test: same normalized form, different entity_type → keep both
df2 = pd.DataFrame([
    {'term_id': 't3', 'term_original': 'insulin', 'term_normalized': 'insulin', 'entity_type': 'drug', 'source_name': 'rxnorm', 'review_status': 'verified'},
    {'term_id': 't4', 'term_original': 'insulin', 'term_normalized': 'insulin', 'entity_type': 'biomarker', 'source_name': 'nlm_lab', 'review_status': 'needs_review'},
])
dedup2, dmap2 = deduplicate_within_entity_type(df2)
assert len(dedup2) == 2, f'Expected 2 rows (different entity types), got {len(dedup2)}'
print('Deduplication test 2 passed: cross-entity-type preserved')
"
</verify>
  <done>Deduplication groups by (entity_type, normalized_form), resolves conflicts by source authority, produces duplicate_map. Warns if deduplication rate >30%.</done>
</task>

</tasks>

<verification>
python -c "
from src.term_inventory.normalizer import normalize_term, apply_normalization, deduplicate_within_entity_type
import pandas as pd

# Integration test
df = pd.DataFrame([
    {'term_id': 't1', 'term_original': 'METFORMIN', 'entity_type': 'drug'},
    {'term_id': 't2', 'term_original': 'β-blocker', 'entity_type': 'drug'},
    {'term_id': 't3', 'term_original': 'ECG', 'entity_type': 'abbreviation'},
])
norm_df, norm_map = apply_normalization(df)
assert 'metformin' in norm_df.loc[norm_df['term_id']=='t1', 'term_normalized'].values[0]
assert 'beta-blocker' in norm_df.loc[norm_df['term_id']=='t2', 'term_normalized'].values[0]
assert norm_df.loc[norm_df['term_id']=='t3', 'term_normalized'].values[0] == 'ecg'
print('Normalization integration test passed')

dedup_df, dup_map = deduplicate_within_entity_type(norm_df)
print(f'Deduplication: {len(dup_map)} duplicates removed from {len(norm_df)} terms')
print('All tests passed')
"
</verification>

<success_criteria>
- `normalize_term()` handles Unicode NFC, Greek-to-ASCII, case folding, unit normalization, returns transformation description
- `normalize_batch()` applies normalization to a list of terms
- `apply_normalization()` takes DataFrame and returns (normalized_df, normalization_map_df)
- normalization_map_df contains only rows where transformation != "none"
- `deduplicate_within_entity_type()` groups by (entity_type, term_normalized), resolves conflicts by source authority
- `create_deduplication_report()` generates deduplication statistics by entity type
- All unit tests pass
- `term_normalization_map.csv` written with columns: raw_form, normalized_form, transformation, entity_type, term_id
</success_criteria>

<output>
Create `.planning/phases/06B-medical-term-inventory-extended/06B-02-SUMMARY.md` when done
</output>
