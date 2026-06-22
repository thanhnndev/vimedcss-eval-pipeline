# Roadmap: ViMedCSS Evaluation Pipeline

## Overview

This roadmap details the phases to implement a complete pipeline evaluating medical term coverage and ASR baseline performance on English/Vietnamese code-switching dataset `tensorxt/ViMedCSS`, and to build the VietMedVoice Phase 2 Enhancement (v1.1) data generation and evaluation system.

## Phases

- [x] **Phase 1: CS Term Extraction & Normalization** — Parse CS terms from ViMedCSS, normalize, export inventory.
- [x] **Phase 2: Term Taxonomy & LLM Classification** — Classify terms by entity category and medical domain using OpenAI.
- [x] **Phase 3: External Reference Match** — Match terms against ICD-10, ATC, Meddict lexicons.
- [x] **Phase 4: ASR Baseline Evaluation** — Run faster-whisper, compute WER/CER/CS metrics.
- [x] **Phase 5: Vietnamese Report Generation** — Generate Vietnamese markdown report summarizing findings.
- [x] **Phase 6a: ICD-10 Dual-Language Ingestion** — Ingest disease backbone EN/VI from KCB ICD-10 endpoint.
- [ ] **Phase 6b: Medical Term Inventory Extended** — Build multi-source inventory (disease, drug, lab, procedure, etc.).
- [ ] **Phase 6c: ViMedCSS Coverage Audit** — Audit ICD-10 and non-ICD coverage rates.
- [ ] **Phase 6d: VietMed Feasibility Audit** — Assess VietMed dataset for real medical ASR expansion.
- [ ] **Phase 6e: LLM Conversation Generation** — Generate structured doctor-patient conversations (JSONL).
- [ ] **Phase 6f: LLM Model Cost Analysis** — Benchmark models, measure JSON validity and cost per conversation.
- [ ] **Phase 6g: TTS Model Research** — Evaluate local/API TTS for Vietnamese + English medical term readability.
- [ ] **Phase 6h: Voice Pool Research** — Build voice pool inventory with gender/age/region metadata (evidence-based).
- [ ] **Phase 6i: Synthetic TTS Generation Pilot** — Convert validated conversations to synthetic speech with round-trip ASR check.
- [ ] **Phase 6j: ASR Evaluation by Domain/Entity** — WER/CER/CS-WER broken down by medical domain and entity type.
- [ ] **Phase 6k: TV3 ASR & Diarization Harness** — PhoWhisper fine-tuning + pyannote/WhisperX diarization eval on real medical audio.
- [ ] **Phase 6l: Dataset Card & Release Plan** — Draft dataset card, license report, privacy checklist, release plan.

## Phase Details

### Phase 1: CS Term Extraction & Normalization

**Goal**: Parse and extract unique code-switching medical terms and occurrences, generating standard normalized dictionary and mappings.
**Mode**: mvp
**Depends on**: Nothing
**Requirements**: TERMS-01, TERMS-02, TERMS-03
**Success Criteria**:

  1. Unique CS terms are parsed and clean dictionary is saved to `outputs/term_coverage/cs_terms_inventory.csv`.
  2. Mappings of terms to examples and segment IDs are written to `outputs/term_coverage/cs_term_examples.jsonl`.

**Plans**: 1 plan

Plans:

- [x] 01-01: Implement CS term parser, cleaner, and mapping exporter.

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

- [x] 02-01: Develop LLM-based structured classifier and audit logging.

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

- [x] 03-01: Implement external dictionary loader and coverage calculator.

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

- [x] 04-01: Implement audio downloader and run baseline ASR transcribing.
- [x] 04-02: Compute WER/CER and classify ASR errors on CS terms.

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

- [x] 05-01: Implement markdown report generator.

### Phase 6a: ICD-10 Dual-Language Ingestion

**Goal**: Ingest ICD-10 disease backbone in English and Vietnamese from the KCB ICD-10 endpoint, build a bilingual code-to-label inventory with full chapter/section/type/disease hierarchy.
**Mode**: mvp
**Depends on**: Nothing (foundation for all subsequent phases)
**Requirements**: FR1-01, FR1-02, FR1-03, FR1-04, FR1-05, FR1-06
**Success Criteria**:

  1. ICD-10 records fetched for both EN and VI languages with `code` as the join key.
  2. Bilingual inventory saved to `data/icd10/icd10_dual_language.csv` and `.jsonl`.
  3. Ingestion errors logged to `data/icd10/icd10_ingestion_errors.csv`.
  4. Report written to `reports/icd10_ingestion_report.md` with statistics and error summary.

**Plans**: 1 plan

Plans:

- [ ] 06A-01-ICD10-INGEST-PLAN.md — Implement ICD-10 dual-language ingestion pipeline with EN/VI join by code

### Phase 6b: Medical Term Inventory Extended

**Goal**: Build a comprehensive medical term inventory from ICD-10 (disease backbone) plus supplementary lexicons (drug, lab test, procedure, abbreviation, hormone, biomarker, device, unit, dosage).
**Mode**: mvp
**Depends on**: Phase 6a
**Requirements**: FR2-01, FR2-02, FR2-03, FR2-04, FR2-05, FR2-06
**Success Criteria**:

  1. All supplementary lexicons ingested with explicit source and license.
  2. Terms normalized and deduplicated; `term_normalization_map.csv` created.
  3. Every term has `entity_type` and `medical_domain` labels.
  4. LLM-generated candidates flagged as `not_verified`.
  5. Files: `data/terms/medical_term_inventory.csv`, `term_sources.csv`, `term_normalization_map.csv`, `human_review_terms.csv`.

**Plans**: 6 plans

Plans:
**Wave 1**

- [x] 06B-01: Schema + CLI skeleton + ICD-10 backbone loader + RxNorm loader

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 06B-02: Normalization pipeline + Greek-to-ASCII + term_normalization_map.csv
- [x] 06B-03: Supplementary loaders (NLM lab, openFDA device, abbreviations, ViMedCSS seed)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 06B-04: LLM classifier for non-authoritative terms with provenance flagging

**Wave 5** *(blocked on Wave 3 completion)*

- [ ] 06B-05: InventoryBuilder orchestrator + 4 CSV exports + reporter

**Wave 6** *(blocked on Wave 5 completion)*

- [ ] 06B-06: Reporter completion + human_review_terms export + test scaffolding

### Phase 6c: ViMedCSS Coverage Audit

**Goal**: Measure how much of ViMedCSS CS term coverage is explained by ICD-10 diseases and supplementary medical lexicons.
**Mode**: mvp
**Depends on**: Phase 6b
**Requirements**: FR3-01, FR3-02, FR3-03, FR3-04, FR3-05, FR3-06
**Success Criteria**:

  1. Unique CS terms from ViMedCSS matched against ICD-10 and supplementary inventories.
  2. Coverage rates computed by domain/entity/split/topic.
  3. Missing and hard terms exported to CSV.
  4. Vietnamese coverage report written with numbers, examples, and metric provenance tiers.

**Plans**: (not yet planned)

### Phase 6d: VietMed Feasibility Audit

**Goal**: Determine whether VietMed dataset can be used to expand real medical ASR training data; audit license, access, overlap with ViMedCSS.
**Mode**: mvp
**Depends on**: Phase 6b, Phase 6c
**Requirements**: FR4-01, FR4-02, FR4-03, FR4-04, FR4-05, FR4-06
**Success Criteria**:

  1. VietMed dataset page, paper, metadata, and license reviewed.
  2. Audio/transcript fields and metadata (ICD-10/domain/accent/speaker) documented.
  3. Overlap with ViMedCSS and ICD-10 inventory analyzed.
  4. Feasibility report written with pass/fail recommendation and conditions.

**Plans**: (not yet planned)

### Phase 6e: LLM Doctor-Patient Conversation Generation

**Goal**: Generate structured doctor-patient conversations in JSONL format, controlled by ICD code, medical domain, and required terms, with safety flags and human review sampling.
**Mode**: mvp
**Depends on**: Phase 6b, Phase 6c
**Requirements**: FR5-01, FR5-02, FR5-03, FR5-04, FR5-05, FR5-06, FR5-07, FR5-08, FR5-09
**Success Criteria**:

  1. Conversation schema validated: `conversation_id`, `icd10_code`, `domain`, `turns` with `speaker_role`, `medical_terms`, `safety_flags`.
  2. JSONL output with valid schema on ≥95% of generated conversations.
  3. Every conversation traceable to ICD/domain/term source.
  4. At least 5% of conversations manually reviewed.
  5. Safety flags populated on every conversation (empty array if no flags).

**Plans**: (not yet planned)

### Phase 6f: LLM Model Cost and Validity Analysis

**Goal**: Benchmark candidate LLM models for conversation generation; measure JSON validity rate and cost per conversation.
**Mode**: mvp
**Depends on**: Phase 6e
**Requirements**: FR6-01, FR6-02, FR6-03, FR6-04, FR6-05, FR6-06
**Success Criteria**:

  1. At least 3 models benchmarked on 100 fixed prompts.
  2. JSON validity rate and medical consistency measured per model.
  3. Cost per conversation computed with explicit token assumptions.
  4. Report and benchmark CSV exported.

**Plans**: (not yet planned)

### Phase 6g: TTS Model Research

**Goal**: Evaluate candidate TTS models (local and API) for Vietnamese text reading and English medical term pronunciation in code-switched sentences.
**Mode**: mvp
**Depends on**: Phase 6e
**Requirements**: FR7-01, FR7-02, FR7-03, FR7-04, FR7-05, FR7-06, FR7-07
**Success Criteria**:

  1. Comparison table produced: local/API, license, GPU, Vietnamese quality, English term quality, cost, limitations.
  2. Round-trip ASR check run as proxy quality measure.
  3. TTS input text preprocessed with `vietnormalizer`.
  4. Pronunciation test results on English medical terms (MRI, CT, ECG, HbA1c, eGFR, metformin, amoxicillin) exported.

**Plans**: (not yet planned)

### Phase 6h: Voice Pool Research

**Goal**: Build a voice pool inventory with gender/age/region metadata sourced from dataset evidence or model-based estimation with confidence; no speculation.
**Mode**: mvp
**Depends on**: Phase 6g
**Requirements**: FR8-01, FR8-02, FR8-03, FR8-04, FR8-05, FR8-06
**Success Criteria**:

  1. Voice pool inventory with license and `allowed_use` for each voice.
  2. Metadata status tracked: `provided`, `estimated`, `unknown` — no guessing.
  3. Every voice assigned `synthetic_speaker_id`.
  4. Files: `data/voice_pool/voice_pool_inventory.csv`, `voice_profile_cards.jsonl`.

**Plans**: (not yet planned)

### Phase 6i: Synthetic TTS Generation Pilot

**Goal**: Convert validated conversations into synthetic speech audio with round-trip ASR quality check; strict synthetic/real separation in data manifests.
**Mode**: mvp
**Depends on**: Phase 6e, Phase 6h
**Requirements**: FR9-01, FR9-02, FR9-03, FR9-04, FR9-05, FR9-06, FR9-07, FR9-08
**Success Criteria**:

  1. Audio generated per conversation turn with assigned voice profile.
  2. `vietnormalizer` applied to all TTS input text.
  3. Round-trip ASR check run on all audio; term preservation verified.
  4. Failed pronunciations logged and flagged, not silently retained.
  5. Every audio record traceable to conversation, turn, term, voice, and TTS model.
  6. Synthetic data separated from real data; train/augmentation only, never in final test set.

**Plans**: (not yet planned)

### Phase 6j: ASR Evaluation by Domain/Entity

**Goal**: Evaluate ASR performance with WER/CER/CS-WER broken down by medical domain and entity type.
**Mode**: mvp
**Depends on**: Phase 6i
**Requirements**: FR10-01, FR10-02, FR10-03, FR10-04, FR10-05, FR10-06
**Success Criteria**:

  1. WER, CER, CS-WER, and medical term recall computed overall and by domain/entity.
  2. Drug/Lab/Disease/Procedure recall measured where entity labels exist.
  3. Top failed terms and term-level error analysis exported.
  4. No improvement claims without controlled ablation experiment.

**Plans**: (not yet planned)

### Phase 6k: TV3 ASR & Diarization Evaluation Harness

**Goal**: Build a reproducible evaluation harness: zero-shot PhoWhisper baseline, fine-tuning ablation (E0/E1/E2/E3), pyannote 3.1 + WhisperX diarization, WER/CER/DER/JER metrics by slice.
**Mode**: mvp
**Depends on**: Phase 6d, Phase 6i, Phase 6j
**Requirements**: FR11-01, FR11-02, FR11-03, FR11-04, FR11-05, FR11-06, FR11-07, FR11-08, FR11-09, FR11-10
**Success Criteria**:

  1. Unified eval manifest with all slice labels (gender, age_bucket, region, specialty, domain, entity_type).
  2. PhoWhisper-Small zero-shot baseline on real test audio.
  3. At least one fine-tune run (E1: synthetic only; E2/E3 if VietMed access granted).
  4. pyannote 3.1 + WhisperX pipeline produces speaker-attributed transcripts.
  5. DER/JER reported only where reference RTTM exists; qualitative proxy otherwise.
  6. Ablation comparing E0/E1/E2/E3 on same real test set; absolute and relative WER changes reported.
  7. `tv3_final_report.md` written with ASR metrics, diarization results, ablation conclusions, and limitations.

**Plans**: (not yet planned)

### Phase 6l: Dataset Card & Release Plan

**Goal**: Prepare documentation for eventual public dataset release: dataset card draft, license report, privacy checklist, and release plan.
**Mode**: mvp
**Depends on**: Phase 6k
**Requirements**: FR12-01, FR12-02, FR12-03, FR12-04
**Success Criteria**:

  1. Dataset card draft with description, splits, license, and reproducibility notes.
  2. License report listing all data sources and their licenses.
  3. Privacy checklist confirming no PII in public artifacts.
  4. Release plan specifying what can be published immediately vs. what needs additional approval.

**Plans**: (not yet planned)

## Progress

|| Phase | Plans Complete | Status | Completed |
||-------|----------------|--------|-----------|
|| 1. CS Term Extraction | 1/1 | Complete | 2026-06-16 |
|| 2. LLM Classification | 1/1 | Complete | 2026-06-16 |
|| 3. External Match | 1/1 | Complete | 2026-06-16 |
|| 4. ASR Evaluation | 2/2 | Complete | 2026-06-16 |
|| 5. Report Generation | 1/1 | Complete | 2026-06-16 |
|| 6a. ICD-10 Dual-Language | 1/1 | Planned | — |
|| 6b. Medical Term Inventory | — | Not Planned | — |
|| 6c. ViMedCSS Coverage Audit | — | Not Planned | — |
|| 6d. VietMed Feasibility | — | Not Planned | — |
|| 6e. LLM Conversation Generation | — | Not Planned | — |
|| 6f. LLM Cost Analysis | — | Not Planned | — |
|| 6g. TTS Model Research | — | Not Planned | — |
|| 6h. Voice Pool Research | — | Not Planned | — |
|| 6i. Synthetic TTS Generation | — | Not Planned | — |
|| 6j. ASR Evaluation by Domain | — | Not Planned | — |
|| 6k. TV3 ASR & Diarization | — | Not Planned | — |
|| 6l. Dataset Card & Release | — | Not Planned | — |
