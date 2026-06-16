# Phase 5 Plan: Vietnamese Report Generation

**Phase:** 5 of 5  
**Mode:** mvp  
**Depends on:** Phase 4  
**Requirements:** REPORT-01, REPORT-02  
**Plans:** 1 plan (05-01)

## Goal

Generate reproducible, source-faithful Vietnamese markdown reports that aggregate Phase 0–4 artifacts into actionable research findings. The generator must read only local artifacts, preserve provenance categories (`paper_reported`, `hf_reported`, `local_verified`, `llm_inferred`), support conditional ASR sections when Phase 4 outputs exist, and expose `generate-report` through the existing CLI/Makeflow conventions.

## Inputs

- `outputs/audit/*` — dataset statistics, schema mapping, download manifest, data quality issues
- `outputs/term_coverage/*` — term inventory, splits/topics/domains/entity categories, LLM audit, external coverage
- `outputs/asr_eval/*` — manifests, hypotheses, metrics, error taxonomy (optional/conditional)
- `configs/report.yaml`, `configs/dataset.yaml`, `configs/taxonomy.yaml`, `configs/asr.yaml`, `configs/external.yaml`
- Existing markdown summary conventions from earlier phases for tone/style consistency

## Outputs

1. `src/reports/report_generator.py` — Jinja-backed generator reading CSV/JSONL artifacts and rendering Vietnamese markdown
2. `src/reports/__init__.py` — package initializer
3. `src/reports/report_data_sources.py` — source provenance registry writer
4. `src/reports/report_limitations.py` — limitation/disclaimer writer
5. `outputs/reports/report_vi_vimedcss_term_coverage_and_asr_weakness.md` — main Vietnamese report
6. `outputs/reports/report_data_sources.md` — source registry and verification status
7. `outputs/reports/report_limitations.md` — explicit limitations and scope caveats
8. `tests/test_report_generator.py` — deterministic tests with `tmp_path` fixtures
9. `configs/report.yaml` — extended report configuration with section ordering and toggles
10. `Makefile` — `report` target invoking `python src/cli.py generate-report`
11. `src/cli.py` — `generate-report` subcommand with `--skip-asr` and `--output-dir` flags

## Scope Constraints

- Do not hard-code metrics or statistics; read them from existing CSV/JSON/JSONL artifacts only.
- Preserve the project's provenance contract: clearly mark `paper_reported`, `hf_reported`, `local_verified`, and `llm_inferred` values in every relevant section.
- ASR sections must be conditional: if `outputs/asr_eval/metrics_summary.csv` or `outputs/asr_eval/errors/top_failed_terms.csv` are missing, omit ASR result sections and emit a scoped disclaimer stating the pipeline state.
- Follow existing conventions: `setup_logger("reports.generator")`, PascalCase class (`ReportGenerator`), snake_case methods, config injection via constructor.
- Vietnamese tone: use technical English terms only when necessary, explain them in Vietnamese, and match the existing summary style from earlier phases.
- Support smoke-test generation: `generate-report --skip-asr` must produce all non-ASR report files without Phase 4 outputs.

## Plan 05-01: Report Generator, CLI, and Validation

### Task 1: Extend `configs/report.yaml`

Add structured configuration for report generation while preserving existing keys.

Required keys:
```yaml
language: vi
output_dir: outputs/reports
format: markdown

sections:
  - id: executive_summary
    title: "Tóm tắt kết luận"
    enabled: true
  - id: data_sources
    title: "Nguồn dữ liệu và mức độ kiểm chứng"
    enabled: true
  - id: provenance_breakdown
    title: "Phân tách provenance: paper_reported / hf_reported / local_verified / llm_inferred"
    enabled: true
  - id: term_coverage_overview
    title: "Tổng quan coverage 889 thuật ngữ CS"
    enabled: true
  - id: entity_category_analysis
    title: "Phân loại term theo entity category"
    enabled: true
  - id: domain_analysis
    title: "Phân loại term theo medical domain"
    enabled: true
  - id: frequency_analysis
    title: "Term phổ biến, term hiếm, term hard-only"
    enabled: true
  - id: external_comparison
    title: "Đối chiếu với external medical term inventory"
    enabled: true
  - id: asr_baseline_results
    title: "Kết quả ASR baseline tổng thể"
    enabled: true
    requires_outputs:
      - outputs/asr_eval/metrics_summary.csv
  - id: asr_cs_term_results
    title: "Kết quả ASR trên CS terms"
    enabled: true
    requires_outputs:
      - outputs/asr_eval/errors/top_failed_terms.csv
  - id: asr_error_analysis
    title: "Phân tích lỗi ASR theo entity category và domain"
    enabled: true
    requires_outputs:
      - outputs/asr_eval/errors/asr_error_taxonomy.csv
  - id: error_examples
    title: "Ví dụ lỗi tiêu biểu"
    enabled: true
    requires_outputs:
      - outputs/asr_eval/errors/asr_error_taxonomy.csv
  - id: coverage_assessment
    title: "Đánh giá dataset hiện tại cover tốt/chưa tốt ở đâu"
    enabled: true
  - id: recommendations
    title: "Kết luận và khuyến nghị cho VietMedVoice"
    enabled: true
  - id: limitations
    title: "Giới hạn của phân tích"
    enabled: true

asr_section_policy: "skip_with_disclaimer" # skip | stub | skip_with_disclaimer
```

Validation rules:
- Sections are rendered in declared order.
- If `requires_outputs` files are absent, the section is skipped when policy is `skip_with_disclaimer`.
- Unknown file paths in `requires_outputs` must raise a configuration error on initialization.

### Task 2: Create `src/reports/report_generator.py`

Implement `ReportGenerator` following existing service-layer conventions.

Core responsibilities:
1. **Artifact reader** (`_load_csv`, `_load_json`, `_load_jsonl`): centralized readers that return pandas DataFrames or lists of dicts. Raise descriptive `FileNotFoundError` when required inputs are missing.
2. **Section renderer** (`render_section`): map section IDs to renderer methods using an explicit registry dict (no `globals()`). Each renderer returns a markdown string.
3. **Report assembler** (`generate`): iterate enabled sections in order, render each, join with section separators, write the final report file.
4. **Conditional ASR sections**: if ASR outputs are missing, emit a scoped Vietnamese disclaimer block instead of fabricated tables.

Public API:
```python
class ReportGenerator:
    def __init__(self, dataset_config, taxonomy_config, report_config, external_config):
        ...

    def generate(self, output_dir: str | None = None, skip_asr: bool = False) -> dict:
        ...
```

Recommended renderer map:
```python
_SECTION_RENDERERS = {
    "executive_summary": "_render_executive_summary",
    "data_sources": "_render_data_sources",
    "provenance_breakdown": "_render_provenance_breakdown",
    "term_coverage_overview": "_render_term_coverage_overview",
    "entity_category_analysis": "_render_entity_category_analysis",
    "domain_analysis": "_render_domain_analysis",
    "frequency_analysis": "_render_frequency_analysis",
    "external_comparison": "_render_external_comparison",
    "asr_baseline_results": "_render_asr_baseline_results",
    "asr_cs_term_results": "_render_asr_cs_term_results",
    "asr_error_analysis": "_render_asr_error_analysis",
    "error_examples": "_render_error_examples",
    "coverage_assessment": "_render_coverage_assessment",
    "recommendations": "_render_recommendations",
    "limitations": "_render_limitations",
}
```

Templating approach:
- Use Jinja templates stored under `templates/reports/` for each section to keep rendering logic separate from data logic.
- Keep templates as plain text files with `.md.j2` extension.
- For simple tables, render via string-building helpers using pandas `.to_markdown(index=False)` when markdown output is needed.
- Use Jinja's `joiner` and conditionals for optional rows.

### Task 3: Create `src/reports/report_data_sources.py`

Implement `DataSourceRegistry` to produce `report_data_sources.md`.

Core responsibilities:
1. Read `outputs/audit/hf_file_manifest.json`, `external_sources_registry.csv`, `llm_classification_audit.jsonl`, and `metadata_schema_report.md` metadata blocks.
2. Build a table with columns: `Nguồn`, `Loại`, `URL / Mô tả`, `Giấy phép / Lưu ý`, `Trạng thái kiểm chứng`.
3. Write Vietnamese markdown with explicit source fidelity notes:
   - `paper_reported` values come from published paper/dataset card only.
   - `hf_reported` values come from Hugging Face metadata.
   - `local_verified` values come from verified local files.
   - `llm_inferred` values come from OpenAI structured output with confidence/review flags.

### Task 4: Create `src/reports/report_limitations.py`

Implement `LimitationWriter` to produce `report_limitations.md`.

Core responsibilities:
1. Emit a fixed but data-informed limitations document in Vietnamese.
2. Include these sections:
   - Phạm vi pilot external inventory (ICD-10/ATC/Meddict pilot scope).
   - Tỷ lệ term cần review (76% from `term_taxonomy_summary.md`).
   - Không dùng UMLS/MeSH API (sandbox offline).
   - Trạng thái ASR evaluation (completed vs pending vs mock).
   - Giới hạn nhãn LLM (confidence, evidence, human review).
   - Dataset snapshot and revision hash from HF manifest.
   - Bias về chủ đề y tế và code-switching intra-sentential.

### Task 5: Create Jinja templates under `templates/reports/`

Create section templates that mirror existing summary tone:

- `executive_summary.md.j2`
- `data_sources.md.j2`
- `provenance_breakdown.md.j2`
- `term_coverage_overview.md.j2`
- `entity_category_analysis.md.j2`
- `domain_analysis.md.j2`
- `frequency_analysis.md.j2`
- `external_comparison.md.j2`
- `asr_baseline_results.md.j2`
- `asr_cs_term_results.md.j2`
- `asr_error_analysis.md.j2`
- `error_examples.md.j2`
- `coverage_assessment.md.j2`
- `recommendations.md.j2`
- `limitations.md.j2`

Template rules:
- Render Vietnamese headings and body text.
- Use `{{ variable }}` for dynamic values; never embed literal metrics.
- Use Jinja `{% if ... %}` for optional tables.
- For tables from DataFrames, accept pre-rendered markdown strings or iterate row dicts.

### Task 6: Integrate `generate-report` CLI command

Add `generate-report` subcommand in `src/cli.py` following existing patterns:

Flags:
- `--skip-asr`: generate report without ASR sections regardless of outputs presence
- `--output-dir`: override `configs/report.yaml.output_dir`
- `--limit`: optional limit for previewing report sections during smoke tests

Behavior:
- Load `AppConfig`.
- Instantiate `ReportGenerator`.
- Call `generate(output_dir=..., skip_asr=args.skip_asr)`.
- Print generated file paths.
- On missing required inputs, log error with path and exit with non-zero status.

### Task 7: Update `Makefile`

Replace stub targets:

```makefile
report:
	PYTHONPATH=. .venv/bin/python src/cli.py generate-report

report-preview:
	PYTHONPATH=. .venv/bin/python src/cli.py generate-report --skip-asr
```

### Task 8: Validation and edge cases

Handle these cases deterministically:
- Missing `outputs/term_coverage/cs_terms_inventory.csv`: raise `FileNotFoundError` with path and suggested fix.
- Empty `cs_terms_inventory.csv` (header only): write report with zero-count tables and log warning.
- ASR outputs partially present (e.g., metrics present but error taxonomy missing): skip missing ASR sections only, render present sections.
- `--skip-asr` with Phase 4 outputs present: still skip ASR sections and log info.
- Large term inventories: ensure DataFrame-to-markdown conversion does not OOM; truncate preview tables to top N rows per section and log the truncation.
- Unicode/encoding: write files with `encoding="utf-8"` and ensure Vietnamese diacritics are preserved.

### Task 9: Tests

Add `tests/test_report_generator.py` following existing Nyquist-style patterns:

Required tests:
- `generate_report_with_all_artifacts_writes_expected_files`
- `generate_report_with_missing_asr_outputs_skips_asr_sections_and_adds_disclaimer`
- `generate_report_with_skip_asr_flag_ignores_present_asr_outputs`
- `missing_core_artifact_raises_file_not_found`
- `empty_term_inventory_writes_zero_count_tables_without_crashing`
- `config_section_ordering_matches_declared_order`
- `make_report_target_invokes_cli_command`
- `report_files_are_valid_utf8_markdown`
- `cli_generate_report_prints_generated_paths`

Test patterns to mirror:
- Use `tmp_path` fixtures for all file IO.
- Use pandas to create minimal fixture CSVs when needed.
- Keep tests deterministic and fast; no external API calls.

## Acceptance Criteria

### REPORT-01
- `outputs/reports/report_vi_vimedcss_term_coverage_and_asr_weakness.md` exists and contains numbered Vietnamese sections.
- Every statistic in the report is traceable to an input artifact path noted in `report_data_sources.md`.
- Provenance labels are preserved and not mixed into unified conclusions.
- Report can be regenerated deterministically from the same artifacts.

### REPORT-02
- `outputs/reports/report_data_sources.md` lists sources, URLs, licenses, and verification statuses.
- `outputs/reports/report_limitations.md` contains explicit limitations and disclaimer sections.
- ASR evaluation results appear only when Phase 4 outputs exist or are explicitly included via configuration.
- `make report` generates all three report files without manual file creation.

## Test Strategy

- Unit tests for `ReportGenerator`, `DataSourceRegistry`, `LimitationWriter`, and CLI integration.
- Smoke test: `PYTHONPATH=. python src/cli.py generate-report --skip-asr` produces all report files from existing Phase 0–3 artifacts.
- Full run: after Phase 4 outputs are produced, `make report` regenerates reports with ASR sections included.
- Validate outputs are UTF-8 markdown files with expected section headings using assertions on file contents.

## Best Practices Applied

- **Jinja2 templating for markdown:** section templates keep rendering logic maintainable and separate from data ingestion, using Jinja conditionals and `joiner` for optional rows.
- **Config-driven report composition:** section ordering, toggles, and ASR section policy live in `configs/report.yaml`.
- **Provenance-first reporting:** explicit separation of `paper_reported`, `hf_reported`, `local_verified`, and `llm_inferred` per project requirements.
- **Defensive ASR integration:** report generator supports missing Phase 4 outputs with scoped disclaimers instead of fabricated tables.
- **Deterministic generation:** tests use `tmp_path` fixtures and fixture CSVs to ensure reproducible outputs without external dependencies.
- **Consistent CLI/Makeflow style:** new subcommand follows existing `argparse`, logging, and `--mock`/`--limit` conventions.

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Report claims ASR results before Phase 4 completes | ASR sections are conditional with `skip_with_disclaimer` policy; no fabricated metrics |
| Large DataFrames cause slow markdown rendering | Truncate preview tables to top N rows; log truncation |
| Provenance categories get mixed in conclusions | Renderer methods receive provenance-tagged values; template labels enforce source attribution |
| Vietnamese diacritics corrupt in file writes | Always write with `encoding="utf-8"` and validate in tests |
| Template drift from code | Keep templates in `templates/reports/` with one-to-one section mapping and explicit registry |
| Smoke tests require Phase 4 outputs | `--skip-asr` flag enables report generation from existing Phase 0–3 artifacts |

## Verification

- [ ] `.planning/phases/05/PLAN.md` reviewed and approved
- [ ] `configs/report.yaml` extended with section ordering and toggles
- [ ] `src/reports/report_generator.py` implemented
- [ ] `src/reports/report_data_sources.py` implemented
- [ ] `src/reports/report_limitations.py` implemented
- [ ] `templates/reports/*.md.j2` created
- [ ] `src/cli.py` updated with `generate-report`
- [ ] `Makefile` updated with `report` and `report-preview`
- [ ] `tests/test_report_generator.py` added and passing
- [ ] `make report` generates all three report files
- [ ] `make report-preview` generates reports without ASR sections
