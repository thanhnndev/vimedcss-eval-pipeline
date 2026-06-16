# Phase 3 Plan: External Reference Match

**Phase:** 3 of 5  
**Mode:** mvp  
**Depends on:** Phase 2  
**Requirements:** EXT_REF-01, EXT_REF-02  
**Plan ID:** 03-01  

## Goal

Register a pilot external medical reference lexicon and compute coverage of ViMedCSS code-switching terms against that lexicon. Deliverables are a source registry, an external inventory, and a coverage comparison table with missing high-priority terms identified.

## Inputs

- `outputs/term_coverage/cs_terms_inventory.csv` (Phase 1/2)
- `configs/taxonomy.yaml`
- `configs/dataset.yaml`
- Optional: `outputs/term_coverage/cs_terms_by_entity_category.csv`, `cs_terms_by_domain.csv` (Phase 2)

## Outputs

1. `outputs/term_coverage/external_sources_registry.csv`
2. `outputs/term_coverage/external_medical_term_inventory.csv`
3. `outputs/term_coverage/vimedcss_vs_external_coverage.csv`
4. `outputs/term_coverage/external_coverage_summary.md`

## Scope Constraints

- Phase 3 is a **pilot** external match. Do not build a full ICD-10 or ATC downloader/indexer unless the source license explicitly permits redistribution and the team approves the access model.
- Only include sources with verified access/license metadata. If a source cannot be redistributed, record its URL and access note in the registry but do not embed its full term list in the repo.
- Do not fabricate counts. All coverage numbers must be computed from local files only.

## Tasks

### Task 1: Add `configs/external.yaml`

Add configuration for external references, aligned with existing config patterns (`dataset.yaml`, `taxonomy.yaml`).

Required keys:
- `enabled`: bool
- `pilot_sources`: list of source dicts with `name`, `source_url`, `license_or_access_note`, `include_in_pilot`
- `inventory_dir`: path under `data/raw/external/` or configurable
- `output_dir`: default `outputs/term_coverage`
- `match_mode`: `exact_case_insensitive` for Phase 3 pilot
- `min_commonness_for_high_priority`: enum or flag controlling which terms count as missing high-priority

### Task 2: Create `src/terms/external.py`

Implement `ExternalReferenceMatcher` following existing codebase conventions:
- Class name: `PascalCase`
- Methods: `snake_case`
- Logger: module-level `setup_logger("terms.external")`
- Config injection: accept dataset/taxonomy/external configs via constructor (mirror `TermClassifier` pattern)
- Fail fast: validate config and input files in `__init__` or early in `run()`

Core responsibilities:
1. **Registry builder** (`_build_registry`): write `external_sources_registry.csv` with pilot source metadata.
2. **Inventory loader** (`_load_inventory`): load pilot external CSVs from `inventory_dir`. For Phase 3, expect a normalized CSV with schema:
   - `term_id`, `canonical_term`, `language`, `entity_category`, `medical_domain`, `specialty`, `source_name`, `commonness_level`, `include_in_pilot`
3. **Matcher** (`_match_terms`): case-insensitive exact match between `normalized_term` in inventory and `canonical_term` in external inventory. Preserve all ViMedCSS terms; unmatched terms get `external_match_status = missing`.
4. **Coverage calculator** (`_compute_coverage`):
   - Per `entity_category` and `medical_domain`: compute `external_term_count`, `vimedcss_covered_count`, `coverage_ratio`.
   - Identify `missing_high_priority_terms` using config thresholds.
   - Compute overall coverage ratio.
5. **Summary writer** (`_write_summary`): generate `external_coverage_summary.md` in Vietnamese with:
   - Overall coverage ratio
   - Breakdown by entity category and medical domain
   - List of top missing high-priority terms
   - Explicit disclaimer that this is a pilot inventory and does not represent full medical taxonomy

Public API:
- `run()` -> dict of stats

### Task 3: Integrate CLI command

Add `match-external` subcommand in `src/cli.py`:
- Optional flags: `--mock`, `--limit`
- `--mock`: use a built-in pilot inventory fixture for smoke tests
- Load `config.get_external_config()` after adding accessor in `AppConfig`

### Task 4: Add config accessor

Update `src/shared/config.py`:
- Add `self.external = self._load_yaml("external.yaml")`
- Add `get_external_config()` method

### Task 5: Output schemas and file contracts

`external_sources_registry.csv`:
- `source_name`, `source_url`, `license_or_access_note`, `include_in_pilot`, `coverage_notes`

`external_medical_term_inventory.csv`:
- `term_id`, `canonical_term`, `language`, `entity_category`, `medical_domain`, `specialty`, `source_name`, `commonness_level`, `commonness_source`, `include_in_pilot`, `notes`

`vimedcss_vs_external_coverage.csv`:
- `entity_category` or `medical_domain`, `external_term_count`, `vimedcss_covered_count`, `coverage_ratio`, `missing_high_priority_count`

`external_coverage_summary.md`:
- Vietnamese markdown with tables and bullet lists. Must include a clear limitations section stating the pilot scope.

### Task 6: Validation and edge cases

- Missing inventory file: raise `FileNotFoundError`
- Empty external inventory: write empty registry and zero coverage without crashing
- Duplicate canonical terms in external inventory: deduplicate deterministically (first occurrence wins) and log warning
- Terms with non-string values in `normalized_term`: skip or normalize with `.astype(str)` and warn

## Acceptance Criteria

- EXT_REF-01:
  - `external_sources_registry.csv` exists and contains at least one pilot source with `source_url` and `license_or_access_note` populated.
  - All pilot sources have `include_in_pilot = true`.
- EXT_REF-02:
  - `external_medical_term_inventory.csv` exists with the required schema.
  - `vimedcss_vs_external_coverage.csv` exists with per-category coverage ratios.
  - Coverage ratios are computed from local CSVs only (no hard-coded numbers).
  - Missing high-priority terms are explicitly listed or aggregated by category.
  - `external_coverage_summary.md` includes a pilot-inventory disclaimer.

## Test Strategy

Add Nyquist-style tests in `tests/test_external_reference.py`:
- Missing inventory raises `FileNotFoundError`
- Empty external inventory produces zero coverage and empty registry
- Case-insensitive exact match works for simple terms
- Unmatched terms are marked `missing` and do not drop from output
- Coverage ratios are computed correctly for a tiny synthetic dataset
- Registry CSV contains required columns and at least one pilot source
- Summary markdown contains expected Vietnamese section headings
- CLI `match-external --mock --limit N` processes only N terms and writes expected files

Test patterns to mirror:
- Use `tmp_path` fixtures
- Use `monkeypatch.setenv` if needed
- Keep tests deterministic and fast

## Best Practices Applied

- **Config-driven design:** All paths, thresholds, and source lists live in YAML. No hard-coded URLs or paths in source code.
- **Reproducibility:** Raw request/response style audit is not needed here because there is no LLM call, but every match decision is traceable via the coverage CSV. Source URLs are preserved in the registry.
- **No fabricated data:** Coverage numbers come from pandas merges on local CSVs.
- **Pilot scope honesty:** Summary explicitly states the inventory is a pilot, not a complete medical taxonomy.
- **Code reuse:** Mirror `TermClassifier` constructor and config patterns to keep the module surface consistent.

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| External source license blocks redistribution | Store only metadata and a small curated pilot; do not bulk-copy proprietary lexicons |
| Fuzzy matching drifts into guesswork | Use exact case-insensitive matching for Phase 3; document as a known limitation |
| Inventory CSV is large and slow | Use vectorized pandas merge/groupby; avoid row-wise Python loops |
| Missing columns in external CSV | Validate schema at load time and raise descriptive `ValueError` |

## Verification

- [ ] `.planning/phases/03/PLAN.md` reviewed and approved
- [ ] `configs/external.yaml` created
- [ ] `src/terms/external.py` implemented
- [ ] `src/shared/config.py` updated
- [ ] `src/cli.py` updated with `match-external`
- [ ] `tests/test_external_reference.py` added and passing
- [ ] Outputs generated and inspected locally in smoke test mode
