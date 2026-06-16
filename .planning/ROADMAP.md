# Roadmap: ViMedCSS Evaluation Pipeline

## Overview

This roadmap details the phases to implement a complete pipeline evaluating medical term coverage and ASR baseline performance on English/Vietnamese code-switching dataset `tensorxt/ViMedCSS`.

## Phases

- [ ] **Phase 1: CS Term Extraction & Normalization** - Extract unique terms and save normalized dictionary.
- [ ] **Phase 2: Term Taxonomy & LLM Classification** - Call LLM to classify terms into entity categories and medical domains.
- [ ] **Phase 3: External Reference Match** - Match terms against ICD-10, ATC, and Meddict reference lexicons.
- [ ] **Phase 4: ASR Baseline Evaluation** - Run faster-whisper transcribing and compute WER/CER/CS metrics.
- [ ] **Phase 5: Vietnamese Report Generation** - Generate final markdown report in Vietnamese.

## Phase Details

### Phase 1: CS Term Extraction & Normalization
**Goal**: Parse and extract unique code-switching medical terms and occurrences, generating standard normalized dictionary and mappings.
**Mode**: mvp
**Depends on**: Nothing (utilizes existing metadata)
**Requirements**: TERMS-01, TERMS-02, TERMS-03
**Success Criteria**:
  1. Unique CS terms are parsed and clean dictionary is saved to `outputs/term_coverage/cs_terms_inventory.csv`.
  2. Mappings of terms to examples and segment IDs are written to `outputs/term_coverage/cs_term_examples.jsonl`.
**Plans**: 1 plan

Plans:
- [ ] 01-01: Implement CS term parser, cleaner, and mapping exporter.

### Phase 2: Term Taxonomy & LLM Classification
**Goal**: Classify unique terms into entity categories and medical domains using OpenAI structured output API.
**Mode**: mvp
**Depends on**: Phase 1
**Requirements**: CLASSIFY-01, CLASSIFY-02, CLASSIFY-03, CLASSIFY-04
**Success Criteria**:
  1. Terms are categorized in `outputs/term_coverage/cs_terms_by_entity_category.csv`.
  2. Terms are mapped to medical domains/specialties in `outputs/term_coverage/cs_terms_by_domain.csv`.
  3. Raw request/response pairs with confidence and human review flags are logged to `outputs/term_coverage/llm_classification_audit.jsonl`.
**Plans**: 1 plan

Plans:
- [ ] 02-01: Develop LLM-based structured classifier and audit logging.

### Phase 3: External Reference Match
**Goal**: Match ViMedCSS terms against external medical dictionaries (ICD-10, ATC, Meddict) to calculate dataset coverage rates.
**Mode**: mvp
**Depends on**: Phase 2
**Requirements**: EXT_REF-01, EXT_REF-02
**Success Criteria**:
  1. Pilot external medical inventory is loaded and matched.
  2. Coverage statistics and missing high-priority items are written to `outputs/term_coverage/vimedcss_vs_external_coverage.csv`.
**Plans**: 1 plan

Plans:
- [ ] 03-01: Implement external dictionary loader and coverage calculator.

### Phase 4: ASR Baseline Evaluation
**Goal**: Download dataset audio files, transcribe using faster-whisper, and calculate WER/CER/CS metrics and error taxonomy.
**Mode**: mvp
**Depends on**: Phase 3
**Requirements**: ASR_EVAL-01, ASR_EVAL-02, ASR_EVAL-03, ASR_EVAL-04
**Success Criteria**:
  1. Audio files are verified and ASR evaluation manifests are created.
  2. ASR hypotheses are generated using faster-whisper under CPU/GPU configurations.
  3. Metric calculations (WER, CER, CS Term Recall/Missing Rate) are computed.
  4. Top failed terms and CS error types are exported to `outputs/asr_eval/errors/top_failed_terms.csv`.
**Plans**: 2 plans

Plans:
- [ ] 04-01: Implement audio downloader and run baseline ASR transcribing.
- [ ] 04-02: Compute WER/CER and classify ASR errors on CS terms.

### Phase 5: Vietnamese Report Generation
**Goal**: Auto-generate the final evaluation report in Vietnamese summarizing term coverage, ASR weaknesses, and dataset gaps.
**Mode**: mvp
**Depends on**: Phase 4
**Requirements**: REPORT-01, REPORT-02
**Success Criteria**:
  1. Automated generator compiles all statistics and quality issues.
  2. Final report is written to `outputs/reports/report_vi_vimedcss_term_coverage_and_asr_weakness.md` with no placeholders.
**Plans**: 1 plan

Plans:
- [ ] 05-01: Implement markdown report generator.

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. CS Term Extraction | 0/1 | Not started | - |
| 2. LLM Classification | 0/1 | Not started | - |
| 3. External Match | 0/1 | Not started | - |
| 4. ASR Evaluation | 0/2 | Not started | - |
| 5. Report Generation | 0/1 | Not started | - |
