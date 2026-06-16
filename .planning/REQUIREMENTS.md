# Requirements: ViMedCSS Evaluation Pipeline

**Defined:** 2026-06-16
**Core Value:** Accurate, traceable medical term coverage analysis and ASR error taxonomy for English/Vietnamese code-switching data to guide future dataset construction.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Ingestion & Auditing (INGEST)
- [x] **INGEST-01**: Download dataset CSV metadata from Hugging Face and write file manifest (`hf_file_manifest.json`).
- [x] **INGEST-02**: Run metadata schema auditing, map actual columns to standard columns, and generate stats (`local_dataset_stats.json`, `split_stats.csv`, `topic_stats.csv`, `duration_stats.csv`).
- [x] **INGEST-03**: Identify data quality issues (duplicate segment_ids, missing transcript/audio/cs_terms) and log to `data_quality_issues.csv`.
- [x] **INGEST-04**: Generate localized schema mapping report (`metadata_schema_report.md`).

### CS Term Extraction & Normalization (TERMS)
- [ ] **TERMS-01**: Parse `cs_terms_list` fields from metadata CSV in various formats (JSON lists, comma-separated lists) and extract raw CS terms.
- [ ] **TERMS-02**: Clean terms (lowercase, strip punctuation, trim whitespace) to create normalized terms while protecting medical abbreviations and spellings.
- [ ] **TERMS-03**: Generate unique CS terms inventory CSV (`cs_terms_inventory.csv`) and mapping to example segment IDs / reference texts (`cs_term_examples.jsonl`).

### Term Taxonomy & LLM Classification (CLASSIFY)
- [ ] **CLASSIFY-01**: Classify unique CS terms into primary/secondary entity categories (e.g. drug, disease, biomarker, anatomy, hormone) using OpenAI Structured Output API.
- [ ] **CLASSIFY-02**: Classify unique CS terms into primary/secondary medical domains/specialties (e.g. endocrinology, cardiology, respiratory) based on context examples.
- [ ] **CLASSIFY-03**: Segment terms into frequency buckets (singleton, rare, medium, common) and split/topic presence lists.
- [ ] **CLASSIFY-04**: Save taxonomy files and audit logs containing raw LLM requests, responses, confidence scores, and review flags (`llm_classification_audit.jsonl`).

### External Reference Integration (EXT_REF)
- [x] **EXT_REF-01**: Register pilot external medical reference lexicons (ICD-10, ATC, Meddict) with source URLs and licenses.
- [x] **EXT_REF-02**: Match ViMedCSS CS terms against external lexicons to compute coverage ratios and identify missing high-priority medical terms.

### ASR Baseline Evaluation (ASR_EVAL)
- [ ] **ASR_EVAL-01**: Download and verify audio files locally to generate ASR evaluation manifests (`eval_manifest_<split>.jsonl`).
- [ ] **ASR_EVAL-02**: Execute `faster-whisper` baseline transcribing on splits, supporting CPU/GPU configurations and `sample_first` smoke test mode.
- [ ] **ASR_EVAL-03**: Compute WER, CER, CS-term exact recall, missing rate, and substitution rate metrics.
- [ ] **ASR_EVAL-04**: Classify ASR errors on CS terms (phonetic Vietnamese transcription, spelling mistakes, missing terms) and save error reports.

### Report Generation (REPORT)
- [ ] **REPORT-01**: Aggregate all audited data quality issues, term coverage distributions, external matches, and ASR evaluation metrics.
- [ ] **REPORT-02**: Generate a comprehensive Vietnamese markdown report summarizing findings, weaknesses, and dataset limitations.

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Model Fine-tuning (TRAIN)
- **TRAIN-01**: Implement automated fine-tuning scripts on the ViMedCSS train split.
- **TRAIN-02**: Support parameter-efficient fine-tuning (LoRA) for Whisper baselines.

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| ASR Model Fine-tuning | Out of scope for baseline evaluation version. |
| Browser/GUI dashboard | Command-line execution and file reports are sufficient for researchers. |
| Full Lexicon Redistribution | Restricted by external license agreements; registry links are kept instead. |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| INGEST-01 | Phase 0 | Complete |
| INGEST-02 | Phase 0 | Complete |
| INGEST-03 | Phase 0 | Complete |
| INGEST-04 | Phase 0 | Complete |
| TERMS-01 | Phase 1 | Pending |
| TERMS-02 | Phase 1 | Pending |
| TERMS-03 | Phase 1 | Pending |
| CLASSIFY-01 | Phase 2 | Pending |
| CLASSIFY-02 | Phase 2 | Pending |
| CLASSIFY-03 | Phase 2 | Pending |
| CLASSIFY-04 | Phase 2 | Pending |
| EXT_REF-01 | Phase 3 | Complete |
| EXT_REF-02 | Phase 3 | Complete |
| ASR_EVAL-01 | Phase 4 | Pending |
| ASR_EVAL-02 | Phase 4 | Pending |
| ASR_EVAL-03 | Phase 4 | Pending |
| ASR_EVAL-04 | Phase 4 | Pending |
| REPORT-01 | Phase 5 | Pending |
| REPORT-02 | Phase 5 | Pending |

**Coverage:**
- v1 requirements: 19 total
- Mapped to phases: 19
- Unmapped: 0 ✓

---
*Requirements defined: 2026-06-16*
*Last updated: 2026-06-16 after initial definition*
