---
phase: "06B-medical-term-inventory-extended"
plan: "05"
subsystem: data-pipeline
tags: [python, pandas, openai, icd10, rxnorm, openfda, nlm, normalization, deduplication]

requires:
  - phase: "06B-02"
    provides: Icd10BackboneLoader, RxNormLoader, NlmLabLoader, OpenFdaDeviceLoader
  - phase: "06B-03"
    provides: AbbreviationLoader, VimedcssSeedLoader
  - phase: "06B-04"
    provides: MedicalTermClassifier with LLM classification

provides:
  - InventoryBuilder orchestrator wiring all 6 loaders into complete pipeline
  - reporter.py generating Vietnamese-narrative term_inventory_report.md
  - CLI build-inventory command wired to InventoryBuilder.build()

affects: [06B-06, phase-6b, ASR-evaluation]

tech-stack:
  added: []
  patterns:
    - Pipeline orchestration (load → concat → assign term_id → normalize → deduplicate → classify → export)
    - CSV multi-output (4 files per build: inventory, normalization map, human review, sources)
    - Boolean-to-string conversion for CSV output columns

key-files:
  created:
    - src/term_inventory/builder.py — InventoryBuilder class
    - src/term_inventory/reporter.py — report generator
  modified:
    - src/term_inventory/cli.py — wired to InventoryBuilder
    - src/term_inventory/loaders/nlm_lab_loader.py — fixed API response parsing

key-decisions:
  - "Per-loader term_id stripped before concat; builder reassigns globally unique term_000001..N after concat"
  - "Non-authoritative sources (vimedcss_seed, abbreviation_list, nlm_lab) classified by LLM; authoritative sources (icd10, rxnorm, openfda) preserve entity_type"
  - "Normalization map written with term_id attached after apply_normalization() returns"
  - "Boolean columns converted to lowercase 'true'/'false' strings for CSV export via _bool_to_str() helper"

patterns-established:
  - "Pipeline step logging with elapsed time tracking"
  - "Mock mode: keyword-based _mock_classify() with domain=unknown, review_status=not_verified"
  - "Human review queue includes rows with needs_human_review_reason='Flagged for human review' when column absent"

requirements-completed: [FR2-02, FR2-03, FR2-04, FR2-05, FR2-06]

duration: 12min
completed: 2026-06-22
---

# Phase 06B Plan 05: InventoryBuilder Orchestrator Summary

**InventoryBuilder orchestrator wiring all 6 loaders, normalization, deduplication, LLM classification, and CSV export into a single pipeline with full mock mode support**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-06-22T04:15 UTC
- **Completed:** 2026-06-22T04:27 UTC
- **Tasks:** 4/4 complete
- **Files modified:** 5 (2 created, 3 modified)

## Accomplishments

- `InventoryBuilder.build()` orchestrates the complete 8-step pipeline: load → concat → assign term_id → normalize → deduplicate → LLM classify → export CSVs → generate report
- `reporter.py` generates `reports/term_inventory_report.md` with Vietnamese narrative, entity type/source/verification distributions
- CLI `build-inventory` command fully wired to `InventoryBuilder.build()` with --mock, --limit, --output-dir, --config flags
- End-to-end mock pipeline verified: all 4 CSV files exist with valid data, 83 pytest tests pass, Vietnamese report generated

## Task Commits

Each task was committed atomically:

1. **Task 1: InventoryBuilder orchestrator** — `d4c443a` (feat)
2. **Task 2: Reporter module** — `d4c443a` (feat, same commit as Task 1)
3. **Task 3: CLI wiring** — `5612a35` (feat)
4. **Task 4: Checkpoint verification** — `e2c1f5a` (fix)

## Files Created/Modified

- `src/term_inventory/builder.py` — InventoryBuilder class: 8-step pipeline, 6 loaders, _mock_classify, _export_csvs, _load_all_sources, _bool_to_str helper for CSV boolean conversion
- `src/term_inventory/reporter.py` — generate_term_inventory_report: Vietnamese narrative, 5 markdown sections, stats dict
- `src/term_inventory/cli.py` — run_build_inventory() now calls InventoryBuilder.build(), removed manual loader orchestration
- `src/term_inventory/loaders/nlm_lab_loader.py` — fixed API response parsing (response is a list not dict; added isinstance guards)
- `src/cli.py` — already had correct elif block for build-inventory command (no changes needed)

## Decisions Made

- Per-loader term_id stripped before concat; builder reassigns globally unique IDs after concat (avoids collisions across loaders)
- Non-authoritative sources get llm_generated_candidate=True, medical_domain="unknown", review_status="not_verified" in mock mode
- Human review queue filter: review_status in ["not_verified","needs_review"] OR llm_generated_candidate=True
- Boolean columns converted to lowercase 'true'/'false' strings for CSV via _bool_to_str() helper
- needs_human_review_reason column added as "Flagged for human review" when absent from human_review_terms.csv

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed boolean-to-string CSV conversion in builder.py**
- **Found during:** Task 4 (checkpoint verification)
- **Issue:** Boolean pandas columns (e.g., llm_generated_candidate=True) were written as "True"/"False" strings instead of "true"/"false". NLM lab loader and RxNorm loader produce boolean columns, causing CSV inconsistency.
- **Fix:** Added _bool_to_str() helper in _export_csvs() that maps {True: "true", False: "false"} for all boolean columns. Applied to both medical_term_inventory.csv and human_review_terms.csv. Also fixed authoritative column in term_sources.csv.
- **Files modified:** src/term_inventory/builder.py
- **Verification:** Checkpoint verification confirmed all 4 CSV files have consistent string booleans
- **Committed in:** e2c1f5a (fix)

**2. [Rule 1 - Bug] Fixed NLM lab loader API response parsing**
- **Found during:** Task 4 (checkpoint verification)
- **Issue:** NLM API response is a plain list `[match_count, field_names, ...data_rows]`, not a dict with "data" key. Prior code called `data.get("data", [])` which always returned empty. Also lacked isinstance guards causing TypeError on non-list responses.
- **Fix:** Changed to `results = data` (response is already a list). Added `isinstance(results, list)` guard and `isinstance(entries, list)` guard. Entries iteration now checks `isinstance(entry, list)` before accessing indices.
- **Files modified:** src/term_inventory/loaders/nlm_lab_loader.py
- **Verification:** Checkpoint verification confirmed NLM loader produces rows
- **Committed in:** e2c1f5a (fix)

**3. [Rule 1 - Bug] Fixed reporter.py KeyError on empty DataFrame**
- **Found during:** Task 1 (initial implementation)
- **Issue:** reporter.py assumed source_name column always exists, raising KeyError on empty DataFrame.
- **Fix:** Wrapped all column accesses in `if total_terms > 0 and len(inventory_df.columns) > 0` guard.
- **Files modified:** src/term_inventory/reporter.py
- **Verification:** Smoke test with empty DataFrame passes
- **Committed in:** d4c443a (feat)

**4. [Rule 1 - Bug] Added needs_human_review_reason fallback in human_review_terms.csv**
- **Found during:** Task 4 (checkpoint verification)
- **Issue:** human_review_terms.csv schema requires needs_human_review_reason column but most loaders don't produce it, causing KeyError when filtering.
- **Fix:** Added fallback: `if "needs_human_review_reason" not in hr_df.columns: hr_df["needs_human_review_reason"] = "Flagged for human review"`
- **Files modified:** src/term_inventory/builder.py
- **Verification:** Checkpoint verification confirmed human_review_terms.csv has the column
- **Committed in:** e2c1f5a (fix)

---

**Total deviations:** 4 auto-fixed (4 Rule 1 bugs)
**Impact on plan:** All fixes necessary for correctness and end-to-end functionality. No scope creep.

## Issues Encountered

- None beyond the Rule 1 bugs listed above.

## User Setup Required

None — no external service configuration required for mock mode. Live mode requires `OPENAI_API_KEY` environment variable for LLM classification (loaded by MedicalTermClassifier).

## Next Phase Readiness

- InventoryBuilder is verified and ready for Phase 06B-06
- Pipeline smoke-tested: `python -m src.cli build-inventory --mock --limit 5` produces all 4 CSV files + report
- 83 pytest tests pass (test_term_inventory_normalizer.py, test_term_inventory_loaders.py)
- All 4 output files confirmed: medical_term_inventory.csv, term_normalization_map.csv, human_review_terms.csv, term_sources.csv
- Vietnamese report confirmed at reports/term_inventory_report.md

---
_Phase: 06B-medical-term-inventory-extended_
_Plan: 05_
_Completed: 2026-06-22_
## Self-Check: PASSED

All files and commits verified:
- src/term_inventory/builder.py — FOUND
- src/term_inventory/reporter.py — FOUND
- src/term_inventory/cli.py — FOUND
- src/term_inventory/loaders/nlm_lab_loader.py — FOUND
- .planning/phases/06B-medical-term-inventory-extended/06B-05-SUMMARY.md — FOUND
- Commit d4c443a — FOUND (feat: implement InventoryBuilder orchestrator and reporter module)
- Commit 5612a35 — FOUND (feat: wire CLI build-inventory to InventoryBuilder)
- Commit ee435fd — FOUND (fix: boolean CSV conversion, NLM loader parsing, needs_human_review_reason fallback)
