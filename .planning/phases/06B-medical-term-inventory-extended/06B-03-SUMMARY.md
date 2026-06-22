---
phase: "06B-medical-term-inventory-extended"
plan: "03"
subsystem: data-pipeline
tags: [openfda, nlm, icd10, abbreviations, medical-terms, pandas, httpx]

# Dependency graph
requires:
  - phase: "06B-01"
    provides: "BaseLoader interface, EntityType/ReviewStatus/TermSource enums, InventoryConfig schema, REQUIRED_COLS contract"
provides:
  - NLM ICD-10-CM lab test and procedure term loader (30 lab + 26 procedure seeds)
  - openFDA 510(k) medical device term loader with verified status
  - Abbreviation loader with 96-entry expansion map (abbrev + expansion rows)
  - ViMedCSS seed term loader bridging Phase 1 output to Phase 6b inventory
affects: [06B-04, 06B-05, 06B-06]

# Tech tracking
tech-stack:
  added: [httpx, tenacity, pandas]
  patterns:
    - BaseLoader abstract class interface with REQUIRED_COLS validation
    - Source authority order: icd10 > rxnorm > openfda > nlm_lab > abbreviation_list > vimedcss_seed
    - Two-row pattern for abbreviations (abbrev + expansion)
    - Extra columns preserved for downstream normalization (openfda_device_number, phase1_* fields)

key-files:
  created:
    - src/term_inventory/loaders/nlm_lab_loader.py
    - src/term_inventory/loaders/openfda_device_loader.py
    - src/term_inventory/loaders/abbreviation_loader.py
    - src/term_inventory/loaders/vimedcss_seed_loader.py
  modified:
    - src/term_inventory/loaders/__init__.py (exports all 7 loaders)

key-decisions:
  - "NLM ICD-10-CM used for lab/procedure despite being general-purpose — NLM Lab Test result table does not cover procedures, so ICD-10-CM search covers both with needs_review status"
  - "openFDA gets verified status because it is an authoritative government database; all other supplementary sources use needs_review"
  - "Phase2ToFr2EntityTypeMap applied in VimedcssSeedLoader to pre-map entity_category from Phase 1 output"

patterns-established:
  - "Loader returns empty DataFrame with REQUIRED_COLS on empty input (no crash)"
  - "Loader raises FileNotFoundError with guidance if Phase 1 output missing"
  - "Extra columns added per loader: openfda_device_number, phase1_specialty, phase1_entity_category, phase1_occurrence_count, phase1_frequency_bucket"

requirements-completed: [FR2-02, FR2-05]

# Metrics
duration: 5min
completed: 2026-06-22
---

# Phase 06B Plan 03: Supplementary Lexicon Loaders Summary

**Four supplementary lexicon loaders: NLM lab/procedure, openFDA device (verified), abbreviation with expansion map, and ViMedCSS seed bridge to Phase 1**

## Performance

- **Duration:** 5 min
- **Started:** 2026-06-22T03:33:56Z
- **Completed:** 2026-06-22T03:38:00Z
- **Tasks:** 3 (4 files created, 1 file modified)
- **Commits:** 3 (all feat)

## Accomplishments

- `NlmLabLoader`: Searches NLM ICD-10-CM Clinical Table Search API with 56 seed terms (30 lab tests, 26 procedures). Classifies each result by keyword matching. Uses `@retry` with 3 attempts, 200ms delay, returns empty DataFrame on no results.
- `OpenFdaDeviceLoader`: Queries openFDA 510(k) device database for configured categories. Deduplicates by device_name. Sets `review_status=verified` (authoritative government source). 500ms delay, 3 retries.
- `AbbreviationLoader`: Creates two rows per abbreviation (abbrev + expansion). 96-entry `ABBREVIATION_EXPANSION_MAP` covers lab values, disease names, routing abbreviations, and specialty codes. All `needs_review`.
- `VimedcssSeedLoader`: Loads Phase 1 `cs_terms_inventory.csv` as `unknown` entity_type. Pre-maps Phase 2 `entity_category` to FR2-04 `EntityType` via `Phase2ToFr2EntityTypeMap`. Preserves phase1 metadata columns for downstream LLM classification (Plan 04).

## Task Commits

Each task was committed atomically:

1. **Task 1: NLM lab test and procedure loader** - `412b833` (feat)
2. **Task 2: openFDA 510(k) medical device loader** - `9930a33` (feat)
3. **Task 3: Abbreviation and ViMedCSS seed loaders** - `abf00ab` (feat)

## Files Created/Modified

- `src/term_inventory/loaders/nlm_lab_loader.py` - NLM ICD-10-CM API loader for lab_test/procedure terms
- `src/term_inventory/loaders/openfda_device_loader.py` - openFDA 510(k) device loader with verified status
- `src/term_inventory/loaders/abbreviation_loader.py` - Abbreviation loader with expansion map (96 entries)
- `src/term_inventory/loaders/vimedcss_seed_loader.py` - Phase 1 seed term bridge with phase1 metadata columns
- `src/term_inventory/loaders/__init__.py` - Updated to export all 7 loaders (BaseLoader, Icd10BackboneLoader, RxNormLoader, NlmLabLoader, OpenFdaDeviceLoader, AbbreviationLoader, VimedcssSeedLoader)

## Decisions Made

- NLM ICD-10-CM used for both lab tests and procedures since NLM Lab Test Results API does not cover procedures; `needs_review` status applied to both since NLM ICD-10-CM is general-purpose
- openFDA marked `verified` because it is a regulatory authority database; all other supplementary loaders use `needs_review`
- `VimedcssSeedLoader` pre-applies `Phase2ToFr2EntityTypeMap` so downstream Plan 04 LLM classification can focus on Phase 1 `unknown` entries only

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## Next Phase Readiness

- Plan 04 (LLM entity classification) can now consume all supplementary loaders
- `InventoryConfig` fields already configured in `configs/term_inventory.yaml` for all seed lists
- All loaders return DataFrames with `REQUIRED_COLS`; `BaseLoader._validate()` confirms schema compliance
- `VimedcssSeedLoader` depends on Phase 1 output; if `outputs/term_coventory/cs_terms_inventory.csv` is missing, it raises `FileNotFoundError` with guidance

---
*Phase: 06B-medical-term-inventory-extended*
*Completed: 2026-06-22*
