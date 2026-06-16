# Phase 4 Plan: ASR Baseline Evaluation

**Phase:** 4 of 5  
**Mode:** mvp  
**Depends on:** Phase 3  
**Requirements:** ASR_EVAL-01, ASR_EVAL-02, ASR_EVAL-03, ASR_EVAL-04  
**Plans:** 2 plans (04-01, 04-02)

## Goal

Run faster-whisper baseline transcription on ViMedCSS splits, compute WER/CER/CS-term metrics, classify ASR errors on code-switching terms, and export reproducible evaluation artifacts. Deliverables include ASR manifests, hypothesis transcripts, metric tables, and error taxonomy reports.

## Inputs

- `outputs/audit/hf_file_manifest.json` (Phase 0)
- `outputs/audit/local_dataset_stats.json`, `split_stats.csv` (Phase 0)
- `outputs/term_coverage/cs_terms_inventory.csv` (Phase 1/2)
- `outputs/term_coverage/cs_terms_by_entity_category.csv`, `cs_terms_by_domain.csv` (Phase 2)
- `outputs/term_coverage/vimedcss_vs_external_coverage.csv` (Phase 3)
- `configs/dataset.yaml`, `configs/asr.yaml`, `configs/external.yaml`
- Optional: `configs/report.yaml`

## Outputs

### Plan 04-01: Audio Manifest & ASR Transcription
1. `outputs/asr_eval/eval_manifest_<split>.jsonl` — verified audio manifests per split
2. `outputs/asr_eval/hypotheses_<split>.jsonl` — ASR hypotheses with segment metadata
3. `outputs/asr_eval/asr_model_registry.csv` — model metadata, device, compute_type, batch_size

### Plan 04-02: Metrics & Error Classification
4. `outputs/asr_eval/metrics_summary.csv` — per-split WER, CER, CS-term recall, missing rate, substitution rate
5. `outputs/asr_eval/errors/top_failed_terms.csv` — top failed CS terms ranked by frequency
6. `outputs/asr_eval/errors/asr_error_taxonomy.csv` — per-utterance error labels (phonetic Vi, spelling, missing, other)
7. `outputs/asr_eval/asr_evaluation_summary.md` — Vietnamese markdown summary with pilot scope disclaimer

## Scope Constraints

- Phase 4 is a **baseline evaluation** using `faster-whisper`. Do not fine-tune models or add multiple ASR backends unless the team explicitly requests it.
- All metrics must be computed from actual local audio and reference transcripts. No fabricated numbers.
- Support `sample_first` smoke test mode (`configs/asr.yaml.run_mode`) before running full splits.
- Preserve separation of `paper_reported`, `hf_reported`, `local_verified`, and `llm_inferred` metrics per project requirements.
- Do not assume audio file formats; inspect actual file tree and metadata columns before downloading.

## Plan 04-01: Audio Manifest & ASR Transcription

### Task 1: Update `configs/asr.yaml`

Add configuration keys aligned with existing config patterns.

Required keys:
- `enabled`: bool
- `run_mode`: `sample_first` or `full`
- `sample_size`: int (used when `run_mode == "sample_first"`)
- `splits`: list of splits to evaluate (e.g., `test`, `hard`)
- `models`: list of model dicts with `name`, `type`, `model_id`
- `device`: `cpu`, `cuda`, or `auto`
- `compute_type`: `float16`, `int8`, or `auto` (int8 recommended for CPU)
- `batch_size`: int for BatchedInferencePipeline (default 8 for CPU, 16 for GPU)
- `beam_size`: int (default 5)
- `vad_filter`: bool (default true for batched inference)
- `normalization`: dict with `lowercase`, `keep_medical_abbreviations`, `keep_numbers_units`
- `audio_verification`: dict with `expected_extensions`, `min_duration_seconds`, `max_duration_seconds`
- `output_dir`: default `outputs/asr_eval`

### Task 2: Create `src/asr/transcriber.py`

Implement `ASRTranscriber` following existing codebase conventions:
- Class name: `PascalCase`
- Methods: `snake_case`
- Logger: module-level `setup_logger("asr.transcriber")`
- Config injection: accept dataset/asr configs via constructor
- Fail fast: validate config and input files in `__init__` or early in `run()`

Core responsibilities:
1. **Manifest builder** (`_build_manifest`): read metadata CSVs from `local_raw_dir`, resolve audio paths, verify audio files exist and meet duration constraints, write `eval_manifest_<split>.jsonl`.
2. **Model loader** (`_load_model`): initialize `faster_whisper.WhisperModel` with config-driven device/compute_type/model_id. Support `BatchedInferencePipeline` for throughput.
3. **Transcriber** (`_transcribe_split`): iterate manifest entries, run transcription, collect segments, write `hypotheses_<split>.jsonl`.
4. **Registry writer** (`_write_model_registry`): write `asr_model_registry.csv` with model metadata, device, compute_type, batch_size, timestamp.
5. **Smoke test mode** (`_run_sample_first`): process only `sample_size` entries per split, log that this is a smoke test, and stop.

Public API:
- `run()` -> dict of stats

Manifest schema (`eval_manifest_<split>.jsonl`):
```json
{
  "split": "test",
  "segment_id": "...",
  "audio_path": "...",
  "reference_text": "...",
  "duration_seconds": 12.34,
  "cs_terms_list": ["term1", "term2"],
  "topic": "...",
  "source_url": "..."
}
```

Hypothesis schema (`hypotheses_<split>.jsonl`):
```json
{
  "split": "test",
  "segment_id": "...",
  "hypothesis_text": "...",
  "language": "en",
  "duration_seconds": 12.34,
  "start": 0.0,
  "end": 12.34,
  "model_name": "whisper_large_v3",
  "device": "cuda",
  "compute_type": "float16",
  "timestamp": "2026-06-16T..."
}
```

### Task 3: Integrate CLI command

Add `run-asr` subcommand in `src/cli.py`:
- Optional flags: `--mock`, `--limit`
- `--mock`: skip actual transcription and write dummy manifests/hypotheses for smoke testing the pipeline downstream
- `--limit`: process only N segments per split (overrides `sample_first` size)

### Task 4: Add audio verification utilities

Create `src/asr/audio_utils.py` with helper functions:
- `verify_audio_file(path, expected_extensions, min_duration, max_duration)` -> bool
- `resolve_audio_path(metadata_row, local_raw_dir)` -> str
- Use `mutagen` or `soundfile` if available; fallback to extension-only check if not installed. Log warning when falling back.

### Task 5: Validation and edge cases

- Missing audio file: log warning, skip segment, increment `skipped_missing_audio` counter.
- Corrupt audio file: log warning, skip segment, increment `skipped_corrupt_audio` counter.
- Empty manifest: write empty hypotheses file, log info, return zero stats.
- `sample_first` with `sample_size` larger than split size: process all segments, log info.
- Device fallback: if configured device is unavailable, attempt fallback order `cuda -> cpu` and log warning.

## Plan 04-02: Metrics & Error Classification

### Task 6: Create `src/asr/metrics.py`

Implement `ASRMetrics` following existing codebase conventions.

Core responsibilities:
1. **Metric computer** (`compute_metrics`): load reference texts and hypothesis texts from `hypotheses_<split>.jsonl`, compute:
   - WER (word error rate) using `jiwer.wer`
   - CER (character error rate) using `jiwer.cer`
   - CS-term exact recall: fraction of CS terms from `cs_terms_inventory.csv` that appear in hypothesis text (case-insensitive after normalization)
   - Missing rate: fraction of CS terms that are absent from hypothesis
   - Substitution rate: fraction of CS terms that appear but are altered (not exact match)
2. **CS-term normalizer**: reuse normalization logic from Phase 1 (`clean_term`) before matching to ensure fair comparison.
3. **Metric writer** (`write_metrics_summary`): aggregate per-split metrics, write `metrics_summary.csv` with columns:
   - `split`, `segment_count`, `wer`, `cer`, `cs_term_recall`, `cs_term_missing_rate`, `cs_term_substitution_rate`
4. **Top failed terms** (`compute_top_failed_terms`): identify CS terms with lowest recall across splits, write `top_failed_terms.csv` with columns:
   - `term`, `normalized_term`, `total_occurrences`, `recall_count`, `recall_rate`, `entity_category`, `medical_domain`

### Task 7: Create `src/asr/error_taxonomy.py`

Implement `ASRErrorTaxonomy` following existing codebase conventions.

Core responsibilities:
1. **Error classifier** (`classify_errors`): for each utterance where reference CS terms do not match hypothesis, classify error type:
   - `phonetic_vietnamese`: hypothesis contains a Vietnamese phonetic approximation of the English term (e.g., "metformin" -> "mêtphomin")
   - `spelling_mistake`: hypothesis contains a misspelled version of the term
   - `missing_term`: term is completely absent from hypothesis
   - `other`: any other mismatch
2. **Heuristic rules**: use string similarity (Levenshtein ratio), Vietnamese character presence, and dictionary lookup. Mark uncertain cases as `other` with a review flag.
3. **Error writer** (`write_error_taxonomy`): write `asr_error_taxonomy.csv` with columns:
   - `split`, `segment_id`, `term`, `error_type`, `reference_text`, `hypothesis_text`, `confidence`, `needs_human_review`
4. **Aggregate report** (`write_summary`): write `asr_evaluation_summary.md` in Vietnamese with:
   - Per-split WER/CER table
   - CS-term recall/missing/substitution rates
   - Top 10 failed terms by entity category
   - Error type distribution
   - Explicit disclaimer that this is a baseline evaluation and does not represent full medical ASR benchmark

### Task 8: Integrate metrics CLI

Add `eval-asr` subcommand in `src/cli.py`:
- Optional flags: `--mock`, `--limit`
- Reads `hypotheses_<split>.jsonl` and reference metadata
- Computes and writes all metrics and error taxonomy files
- `--mock`: generates synthetic hypotheses from reference text with injected errors for smoke testing

### Task 9: Validation and edge cases

- Empty hypotheses file: write empty metrics CSV with header only, log info.
- Missing reference metadata: raise `FileNotFoundError` with descriptive message.
- Zero CS terms in reference: set recall/missing/substitution rates to NaN or 0 with log warning.
- Very long utterances: ensure `jiwer` processing does not OOM; chunk if necessary or log warning.

## Acceptance Criteria

### ASR_EVAL-01
- `eval_manifest_<split>.jsonl` exists for each configured split.
- Each manifest entry contains `segment_id`, `audio_path`, `reference_text`, `duration_seconds`, `cs_terms_list`, `topic`.
- Audio files are verified for existence and basic constraints before manifest is written.

### ASR_EVAL-02
- `hypotheses_<split>.jsonl` exists for each split with non-empty `hypothesis_text`.
- `asr_model_registry.csv` contains model name, device, compute_type, batch_size, and timestamp.
- `run_mode == "sample_first"` processes only `sample_size` entries and logs the smoke test scope.
- CLI `run-asr --mock --limit N` writes expected files without calling faster-whisper.

### ASR_EVAL-03
- `metrics_summary.csv` contains per-split WER, CER, CS-term recall, missing rate, and substitution rate.
- All metrics are computed from local files only (no hard-coded numbers).
- CS-term matching uses normalized terms (lowercase, stripped punctuation) consistent with Phase 1.

### ASR_EVAL-04
- `asr_error_taxonomy.csv` contains per-utterance error classifications with `error_type`, `confidence`, and `needs_human_review`.
- `top_failed_terms.csv` lists failed CS terms ranked by recall rate with entity category and medical domain.
- `asr_evaluation_summary.md` includes Vietnamese headings, metric tables, and a pilot-scope disclaimer.

## Test Strategy

Add Nyquist-style tests in `tests/test_asr_transcriber.py` and `tests/test_asr_metrics.py`:
- Manifest builder skips missing audio and increments counter
- `sample_first` mode processes exactly N entries
- Model registry CSV contains required columns
- Mock transcription writes expected hypothesis schema
- WER/CER computed correctly for known reference/hypothesis pairs
- CS-term recall/missing/substitution computed correctly for synthetic terms
- Error taxonomy classifies missing, phonetic, and spelling errors
- CLI `eval-asr --mock` processes synthetic data and writes all outputs
- Empty manifest produces zero stats without crashing

Test patterns to mirror:
- Use `tmp_path` fixtures
- Use `monkeypatch.setenv` if needed
- Keep tests deterministic and fast (no real model download in unit tests)

## Best Practices Applied

- **Context7-informed ASR evaluation:** faster-whisper with `BatchedInferencePipeline` for high-throughput CPU/GPU transcription; int8 quantization recommended for CPU to reduce RAM usage.
- **Metric computation with jiwer:** use `jiwer.wer` and `jiwer.cer` for standard WER/CER with built-in preprocessing pipelines.
- **Config-driven design:** all paths, model names, devices, and thresholds live in YAML.
- **No fabricated data:** all metrics come from actual audio transcription and pandas/jiwer computation on local files.
- **Smoke test mode:** `sample_first` and `--mock` flags enable testing without full dataset downloads.
- **Pilot scope honesty:** summaries explicitly state baseline limitations and do not claim full medical ASR benchmark status.
- **Code reuse:** mirror `ExternalReferenceMatcher` constructor, config injection, and logging patterns.

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Audio download too large for local disk | Use `sample_first` by default; verify file sizes before full download; support resume |
| faster-whisper model download fails | Cache model in configurable directory; log clear error with model_id |
| CS-term recall inflated by short utterances | Compute recall only on utterances containing at least one CS term |
| Error taxonomy is noisy | Use conservative heuristics; mark uncertain cases as `other` with `needs_human_review=True` |
| Vietnamese text normalization differs from Whisper | Explicitly normalize both reference and hypothesis using Phase 1 `clean_term` before metric computation |

## Verification

- [ ] `.planning/phases/04/PLAN.md` reviewed and approved
- [ ] `configs/asr.yaml` updated with transcription settings
- [ ] `src/asr/transcriber.py` implemented
- [ ] `src/asr/metrics.py` implemented
- [ ] `src/asr/error_taxonomy.py` implemented
- [ ] `src/asr/audio_utils.py` implemented
- [ ] `src/shared/config.py` updated with ASR/eval config accessors
- [ ] `src/cli.py` updated with `run-asr` and `eval-asr`
- [ ] `tests/test_asr_transcriber.py` added and passing
- [ ] `tests/test_asr_metrics.py` added and passing
- [ ] Outputs generated and inspected locally in smoke test mode
