# Codebase Concerns

**Analysis Date:** 2026-06-16

## Tech Debt

**Semicolon vs Comma Term Splitting in Metadata Auditing:**
- Issue: `MetadataAuditor` parses the `cs_terms_list` field by splitting on commas (`,`) only.
- File: `src/audit/auditor.py` (lines ~194, ~223).
- Why: Assumed standard list representation.
- Impact: In the raw metadata files (e.g. `data/raw/vimedcss/ViMedCSS-Metadata/test_set.csv`), rows with multiple code-switching terms separate them using semicolons (e.g. `hormone; estrogen` or `uric; urat`). Because the auditor splits on commas, these multi-term cells are misidentified as a single compound term (`"hormone; estrogen"`), throwing off occurrences metrics (currently reporting 1 term per row exactly).
- Fix approach: Modify the parser in `_compute_split_stats` and `_compute_topic_stats` to replace semicolons with commas before parsing, or split on both `;` and `,`.

**Placeholder/Empty Directories:**
- Issue: Several directories in `src/` are currently empty.
- Paths: `src/terms/`, `src/llm/`, `src/asr/`, `src/metrics/`, `src/reports/`.
- Why: Structural skeleton created during project setup.
- Impact: Main evaluation capabilities (term normalization, LLM-based taxonomy mapping, ASR execution, WER calculations, automatic reports) are not implemented yet.
- Fix approach: Implement the code-switching term coverage and evaluation code in these directories sequentially.

## Known Bugs

- None currently discovered in the existing codebase. The `make test` suite passes successfully.

## Security Considerations

**Hardcoded OpenAI API Connection:**
- Risk: The LLM pipeline requires `OPENAI_API_KEY` to connect to OpenAI's server.
- current mitigation: Stated in config loader that an API key is required. No key is hardcoded.
- Recommendations: Add checks to ensure the API key exists before executing LLM classification, displaying a clear validation error if missing.

## Performance Bottlenecks

- None currently, as only metadata parsing has been implemented, which executes in <1 second. However, running ASR baselines on the full 32.64-hour dataset will require significant GPU runtime. Running subsets/smoke tests first is highly recommended.

## Fragile Areas

- None identified yet.

## Scaling Limits

**OpenAI API Rate Limits:**
- The LLM taxonomy mapping is set to run in batches of 50. If there are 800+ terms, this translates to ~16 API requests. This is well within standard tier limits, but API failures or timeouts must be gracefully handled (e.g., retrying or caching outputs).

## Dependencies at Risk

- **gpt-5-mini Model Selection:**
  - File: `configs/llm.yaml`
  - Risk: The config defaults to `gpt-5-mini`. If this model is not released/available in the target subscription, API calls will fail.
  - Mitigation plan: Ensure the code dynamically parses the model name from config/env and fails gracefully, suggesting fallback models (e.g., `gpt-4o-mini`).

## Missing Critical Features

- **ASR Pipeline & Evaluation:**
  - Problem: Running Whisper ASR baseline and evaluating metrics like Word Error Rate (WER) / Character Error Rate (CER) on code-switching terms is missing.
  - Workaround: None.
  - Complexity: High. Requires downloading audio, invoking the model, normalizing ASR transcripts, and aligning words.

## Test Coverage Gaps

**Integration Testing:**
- What's not tested: Testing against actual Hugging Face downloads and actual OpenAI API returns.
- Risk: Changes to Hugging Face repository structures or OpenAI API payloads could break the system without unit tests failing.
- Priority: Medium.
- Difficulty to test: Requires mocking external HTTP requests/responses.

---

*Concerns audit: 2026-06-16*
*Update as issues are fixed or new ones discovered*
