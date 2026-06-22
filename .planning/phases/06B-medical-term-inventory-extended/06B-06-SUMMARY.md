# Phase 06B Plan 06: Test Scaffolding for Normalizer and Loaders — Summary

## Metadata

| Field | Value |
|---|---|
| Phase | 06B |
| Plan | 06 |
| Subsystem | term_inventory |
| Type | execute |
| Wave | 6 |
| Tags | test, normalizer, loaders, pipeline |
| Dependency graph | depends_on: [06B-02, 06B-03, 06B-04, 06B-05] |
| Tech stack added | pytest, pandas |
| Key files created | tests/test_term_inventory_normalizer.py, tests/test_term_inventory_loaders.py |
| Key files modified | src/term_inventory/normalizer.py |
| Decisions | Unit normalization must run before Greek-to-ASCII to avoid µ→mu→"mug"→"mmcg" double-substitution |
| Requirements | FR2-02, FR2-05, FR2-06 |
| Duration | ~60s (3 commits) |
| Completed | 2026-06-22 |

## Objective

Create test scaffolding for the `normalizer` and `loaders` modules. This plan
completes after Plan 05 (builder/reporter integration) and provides the test
coverage that validates the term inventory pipeline outputs.

## One-liner

Test scaffolding for normalizer (8+ cases) and loaders (6+ cases) with all 29 pytest tests passing, plus a critical bug fix in the normalization pipeline.

## Tasks Completed

| # | Name | Status | Commit |
|---|---|---|---|
| 1 | Create test scaffolding for normalizer and loaders | Done | 05688bf |

### Task 1: Test scaffolding for normalizer and loaders

**Files created:**
- `tests/test_term_inventory_normalizer.py` — 14 test cases across 8 classes
- `tests/test_term_inventory_loaders.py` — 12 test cases across 6 classes

**Test cases (normalizer, 14 total):**
1. `TestGreekToAscii::test_beta_blocker` — β-blocker → beta-blocker
2. `TestGreekToAscii::test_alpha_thalassemia` — α-thalassemia → alpha-thalassemia
3. `TestGreekToAscii::test_mu_microgram` — μg → mcg (after pipeline fix)
4. `TestGreekToAscii::test_gamma_globulin` — γ-globulin → gamma-globulin
5. `TestNfcNormalization::test_combining_accent_removed` — metformin\u0301 → metformin
6. `TestNfcNormalization::test_cafe_with_combining_accent` — cafe\u0301 → cafe
7. `TestCaseFolding::test_uppercase_to_lowercase` — METFORMIN → metformin
8. `TestCaseFolding::test_mixed_case_folded` — DiAbEtEs → diabetes
9. `TestUnitNormalization::test_insulin_units_suffix` — "insulin 100units" contains "unit"
10. `TestUnitNormalization::test_metformin_mg_suffix` — "metformin 500mg" contains "mg"
11. `TestUnitNormalization::test_microgram_to_mcg` — "dosage μg" → "mcg"
12. `TestApplyNormalization::test_apply_normalization_returns_both_dataframes`
13. `TestApplyNormalization::test_only_transformed_rows_in_map`
14. `TestDeduplicateSameEntityType::test_same_entity_type_same_normalized_keeps_one`
15. `TestDeduplicateSameEntityType::test_verified_source_wins` — rxnorm beats vimedcss_seed
16. `TestDeduplicateCrossEntityType::test_same_normalized_different_entity_type_preserves_both` — insulin as drug AND biomarker
17. `TestDeduplicationRateWarning::test_high_deduplication_rate_warns`

**Test cases (loaders, 12 total):**
1. `TestBaseLoaderInterface::test_all_loaders_inherit_from_base_loader` — 5 loader classes
2. `TestBaseLoaderInterface::test_all_loaders_have_load_method` — all have load() method
3. `TestIcd10BackboneLoaderColumns::test_icd10_loader_produces_required_columns` — 2 disease rows, required cols present
4. `TestIcd10BackboneLoaderColumns::test_icd10_loader_missing_file_raises` — FileNotFoundError
5. `TestAbbreviationLoaderProducesExpansions::test_abbreviation_loader_produces_rows_for_each_abbreviation` — ECG+MRI+CT = 6+ rows
6. `TestAbbreviationLoaderProducesExpansions::test_abbreviation_loader_contains_expansions` — contains "electrocardiogram" and "magnetic resonance imaging"
7. `TestVimedcssSeedLoaderMissingFile::test_vimedcss_seed_loader_raises_on_missing_file` — FileNotFoundError via VIMEDCSS_SEED_PATH
8. `TestAllLoadersRequiredCols::test_icd10_required_columns` — all REQUIRED_COLS present
9. `TestAllLoadersRequiredCols::test_rxnorm_required_columns` — all REQUIRED_COLS present
10. `TestAllLoadersRequiredCols::test_nlm_lab_required_columns` — all REQUIRED_COLS present
11. `TestAllLoadersRequiredCols::test_abbreviation_required_columns` — all REQUIRED_COLS present
12. `TestAbbreviationSourceName::test_all_abbreviation_rows_have_abbreviation_list_source` — all rows source_name="abbreviation_list"

**Result:** 29 passed, 0 failed

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed normalization pipeline order — unit normalization before Greek-to-ASCII**

- **Found during:** Test `test_mu_microgram` execution
- **Issue:** `normalize_term("μg")` was returning `"mmcg"` instead of `"mcg"`. The pipeline was:
  1. NFC normalization
  2. Greek-to-ASCII: μ → "mu" → "mug"
  3. Case folding
  4. Unit suffix normalization: "ug" → "mcg" → **"mmcg"** (wrong)
- **Fix:** Reordered pipeline so unit suffix normalization (step 2) runs BEFORE Greek-to-ASCII (step 3). Now:
  1. NFC normalization
  2. Unit suffix normalization: μg (via UNIT_SUFFIX_NORM which maps U+00B5 micro sign) → "mcg"
  3. Greek-to-ASCII: (no Greek chars left)
  4. Case folding
- **Files modified:** `src/term_inventory/normalizer.py`
- **Commit:** 05688bf
- **Test updated:** `test_mu_microgram` — now asserts `"mcg" in result` and `"unit_normalization" in desc`

**2. [Rule 2 - Critical] Added missing `REQUIRED_COLS` test coverage for loaders**

- **Found during:** Fixture review
- **Issue:** Existing plan test cases for `test_all_loaders_required_cols` referenced a non-existent `REQUIRED_COLS` module-level constant. The loaders package uses `BaseLoader.REQUIRED_COLS` as a class attribute instead.
- **Fix:** Imported `BaseLoader as ICD10BaseLoader` from the existing `icd10_backbone` submodule and used `ICD10BaseLoader.REQUIRED_COLS` in all column presence assertions. Also created an `icd10_csv` fixture that writes the correct CSV format (`level=type` rows) with proper column headers.

## Known Stubs

None.

## Threat Flags

None.

## Commits

| Hash | Message |
|---|---|
| `05688bf` | fix(term-inventory): reorder normalizer pipeline — unit normalization before Greek-to-ASCII |

## Success Criteria

| Criterion | Status |
|---|---|
| `tests/test_term_inventory_normalizer.py` created with ≥8 test cases | ✅ 14 test cases |
| `tests/test_term_inventory_loaders.py` created with ≥6 test cases | ✅ 12 test cases |
| All pytest tests pass | ✅ 29/29 passed |

## Self-Check: PASSED

- `tests/test_term_inventory_normalizer.py` exists ✓
- `tests/test_term_inventory_loaders.py` exists ✓
- `src/term_inventory/normalizer.py` modified (pipeline order fix) ✓
- Commit `05688bf` present in git log ✓
- 29 tests pass ✓
