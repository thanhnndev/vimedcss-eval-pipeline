# Requirements: ViMedCSS Evaluation Pipeline

**Defined:** 2026-06-16
**Last updated:** 2026-06-19 (v1.1 scope added)
**Core Value:** Accurate, traceable medical term coverage analysis and ASR error taxonomy for English/Vietnamese code-switching data to guide future dataset construction.

## v1 Requirements

Requirements for initial release (Phases 1–5). All complete.

### Ingestion & Auditing (INGEST)
- [x] **INGEST-01**: Download dataset CSV metadata from Hugging Face and write file manifest (`hf_file_manifest.json`).
- [x] **INGEST-02**: Run metadata schema auditing, map actual columns to standard columns, and generate stats.
- [x] **INGEST-03**: Identify data quality issues (duplicate segment_ids, missing transcript/audio/cs_terms).
- [x] **INGEST-04**: Generate localized schema mapping report (`metadata_schema_report.md`).

### CS Term Extraction & Normalization (TERMS)
- [x] **TERMS-01**: Parse `cs_terms_list` fields from metadata CSV in various formats.
- [x] **TERMS-02**: Clean terms (lowercase, strip punctuation, trim whitespace) while protecting medical abbreviations.
- [x] **TERMS-03**: Generate unique CS terms inventory CSV and mapping to example segment IDs (`cs_terms_inventory.csv`, `cs_term_examples.jsonl`).

### Term Taxonomy & LLM Classification (CLASSIFY)
- [x] **CLASSIFY-01**: Classify unique CS terms into primary/secondary entity categories using OpenAI Structured Output API.
- [x] **CLASSIFY-02**: Classify unique CS terms into primary/secondary medical domains/specialties.
- [x] **CLASSIFY-03**: Segment terms into frequency buckets and split/topic presence lists.
- [x] **CLASSIFY-04**: Save taxonomy files and audit logs containing raw LLM requests, responses, confidence scores, and review flags.

### External Reference Integration (EXT_REF)
- [x] **EXT_REF-01**: Register pilot external medical reference lexicons (ICD-10, ATC, Meddict) with source URLs and licenses.
- [x] **EXT_REF-02**: Match ViMedCSS CS terms against external lexicons to compute coverage ratios.

### ASR Baseline Evaluation (ASR_EVAL)
- [x] **ASR_EVAL-01**: Download and verify audio files locally to generate ASR evaluation manifests.
- [x] **ASR_EVAL-02**: Execute `faster-whisper` baseline transcribing on splits, supporting CPU/GPU and smoke test modes.
- [x] **ASR_EVAL-03**: Compute WER, CER, CS-term exact recall, missing rate, and substitution rate metrics.
- [x] **ASR_EVAL-04**: Classify ASR errors on CS terms and save error reports.

### Report Generation (REPORT)
- [x] **REPORT-01**: Aggregate all audited data quality issues, term coverage distributions, external matches, and ASR evaluation metrics.
- [x] **REPORT-02**: Generate a comprehensive Vietnamese markdown report summarizing findings and dataset limitations.

## v1.1 Requirements

Requirements for Phase 2 Enhancement milestone (FR1–FR11). Each maps to roadmap phases.

### FR1 — ICD-10 Dual-Language Ingestion

**Goal:** Create bilingual (EN/VI) disease backbone inventory from KCB ICD-10 endpoint.

- [ ] **FR1-01**: Query KCB ICD-10 endpoint with `lang=en` and `lang=vi`, `vol1=1`, `vol3=0`, `html=true`.
- [ ] **FR1-02**: Parse JSON responses and HTML trees to extract `chapter`, `section`, `type`, `disease` hierarchy per code.
- [ ] **FR1-03**: Join EN and VI records by `code` (NOT by label text); log failures and retry with backoff.
- [ ] **FR1-04**: Save `icd10_dual_language.jsonl`, `icd10_dual_language.csv`, and `icd10_ingestion_errors.csv`.
- [ ] **FR1-05**: Generate `reports/icd10_ingestion_report.md` with statistics and error summary.
- [ ] **FR1-06**: Every record must have: `code`, `level`, `label_en`, `label_vi`, `parent_code`, `chapter_code`, `source_url`, `fetched_at`.

### FR2 — Medical Term Inventory Extended

**Goal:** Build a multi-source inventory covering disease, drug, lab test, procedure, abbreviation, hormone, biomarker, device, unit, and dosage terms.

- [ ] **FR2-01**: Ingest ICD-10 dual-language inventory as disease backbone.
- [ ] **FR2-02**: Ingest supplementary lexicons (drug, lab test, procedure, abbreviation lists) from approved sources.
- [ ] **FR2-03**: Normalize and deduplicate terms; create `term_normalization_map.csv`.
- [ ] **FR2-04**: Classify each term by `entity_type` (disease, drug, lab_test, procedure, anatomy, symptom, abbreviation, hormone, biomarker, pathogen, device, unit, dosage) and `medical_domain`.
- [ ] **FR2-05**: Attach source provenance to every term; flag `llm_generated_candidate` terms as `not_verified`.
- [ ] **FR2-06**: Export `data/terms/medical_term_inventory.csv`, `term_sources.csv`, `term_normalization_map.csv`, `human_review_terms.csv`.

### FR3 — ViMedCSS ICD-10 / Non-ICD Coverage Audit

**Goal:** Quantify what fraction of ViMedCSS CS terms are covered by ICD-10 diseases and by supplementary lexicons.

- [ ] **FR3-01**: Extract unique CS terms from ViMedCSS metadata (`cs_terms_list`, `segment_text`).
- [ ] **FR3-02**: Match terms against ICD-10 inventory and supplementary lexicons.
- [ ] **FR3-03**: Group coverage by domain/entity/split/topic; compute coverage rates.
- [ ] **FR3-04**: Identify and export missing terms (`vimedcss_missing_terms.csv`) and hard terms (`vimedcss_hard_terms.csv`).
- [ ] **FR3-05**: Generate `reports/vimedcss_coverage_report_vi.md` with Vietnamese narrative, numbers, examples, and confidence tiers (paper_reported / hf_reported / local_verified).
- [ ] **FR3-06**: Every metric must be traceable to a local verified file; no silent copying from papers or HF cards.

### FR4 — VietMed Feasibility Audit

**Goal:** Determine whether VietMed dataset can be used to expand real medical ASR training data.

- [ ] **FR4-01**: Inspect VietMed dataset page, paper, metadata, license, and available splits/audio/transcripts.
- [ ] **FR4-02**: Verify audio/transcript fields and check for ICD-10/domain/accent/speaker metadata.
- [ ] **FR4-03**: Do NOT download raw audio if license is unclear; audit metadata only if needed.
- [ ] **FR4-04**: Compare overlap with ViMedCSS and ICD-10 inventory.
- [ ] **FR4-05**: Generate `reports/vietmed_feasibility_report.md` with clear pass/fail recommendation and conditions.
- [ ] **FR4-06**: Do not claim VietMed has code-switching without transcript verification.

### FR5 — LLM Doctor-Patient Conversation Generation

**Goal:** Generate structured doctor-patient conversations controlled by ICD/domain/term with safety flags.

- [ ] **FR5-01**: Design conversation schema with `conversation_id`, `icd10_code`, `domain`, `scenario_type`, `code_switch_level`, `required_terms`, `turns`, `safety_flags`, `generation_model`, `prompt_version`.
- [ ] **FR5-02**: Each `turn` must have: `turn_id`, `speaker_role` (doctor/patient), `text`, `medical_terms`, `language_mix`.
- [ ] **FR5-03**: Generate conversations using OpenAI structured output API (`response_format=PydanticModel`) or Anthropic with `output_format=PydanticModel`.
- [ ] **FR5-04**: Validate JSON schema and medical term inclusion on every generated conversation.
- [ ] **FR5-05**: Apply safety policy: flag any non-synthetic medical advice, out-of-scope diagnoses.
- [ ] **FR5-06**: Export `data/conversations/doctor_patient_conversations.jsonl`, `conversation_validation_errors.jsonl`, `conversation_specs.jsonl`.
- [ ] **FR5-07**: Every conversation must be traceable to an ICD/domain/term source.
- [ ] **FR5-08**: Human review sample: at least 5% of conversations manually reviewed.
- [ ] **FR5-09**: Synthetic conversations are NOT for final real test sets.

### FR6 — LLM Model Cost and Validity Analysis

**Goal:** Benchmark candidate LLM models for conversation generation; report cost per conversation and JSON validity rate.

- [ ] **FR6-01**: Benchmark 3–5 candidate models on a fixed prompt set (100 conversations).
- [ ] **FR6-02**: Measure JSON validity rate (parseable, schema-conformant).
- [ ] **FR6-03**: Measure medical consistency (terms present, no fabrications).
- [ ] **FR6-04**: Compute cost per conversation: input tokens + output tokens × model price.
- [ ] **FR6-05**: Generate `reports/llm_model_cost_report.md` and `data/model_eval/llm_generation_benchmark.csv`.
- [ ] **FR6-06**: Clearly separate text generation cost, TTS cost, and ASR validation cost in reporting.

### FR7 — TTS Model Research

**Goal:** Select TTS model(s) capable of reading Vietnamese conversations with English medical terms.

- [ ] **FR7-01**: Evaluate candidate local and API TTS models on Vietnamese text reading.
- [ ] **FR7-02**: Test English medical term pronunciation within Vietnamese sentences: MRI, CT, ECG, HbA1c, eGFR, metformin, amoxicillin, corticosteroid.
- [ ] **FR7-03**: Evaluate voice control (gender, age, region diversity) if supported.
- [ ] **FR7-04**: Run round-trip ASR check (TTS → faster-whisper) as a proxy quality measure.
- [ ] **FR7-05**: Generate `reports/tts_model_research_report.md` with comparison table: local/API, license, GPU, Vietnamese quality, English term quality, cost, limitations.
- [ ] **FR7-06**: Export `data/model_eval/tts_model_comparison.csv` and `tts_term_pronunciation_test.csv`.
- [ ] **FR7-07**: Preprocess all TTS input with `vietnormalizer` for Vietnamese text normalization before synthesis.

### FR8 — Voice Pool Research

**Goal:** Build a voice pool with metadata (gender/age/region) supported by evidence; no speculation.

- [ ] **FR8-01**: Audit available speech/TTS datasets (viVoice, PhoAudiobook, VieNeu-TTS-140h) for metadata availability.
- [ ] **FR8-02**: For each voice profile: set `gender_status`, `age_status`, `region_status` as `provided`, `estimated`, or `unknown`.
- [ ] **FR8-03**: Use `estimated_*` prefix only with confidence score; never guess without model-based estimation.
- [ ] **FR8-04**: Track license and `allowed_use` (research_only, commercial) for every voice.
- [ ] **FR8-05**: Assign `synthetic_speaker_id` to each synthetic voice.
- [ ] **FR8-06**: Export `data/voice_pool/voice_pool_inventory.csv` and `voice_profile_cards.jsonl`.

### FR9 — Synthetic TTS Generation Pilot

**Goal:** Convert validated conversations into synthetic speech with round-trip ASR quality check.

- [ ] **FR9-01**: Split conversations into turns; assign voice profile to each role.
- [ ] **FR9-02**: Normalize text input with `vietnormalizer` before TTS call.
- [ ] **FR9-03**: Generate audio per turn or full conversation; store audio path per record.
- [ ] **FR9-04**: Run round-trip ASR (faster-whisper) on generated audio; check term preservation.
- [ ] **FR9-05**: Flag failed pronunciations; do not silently retain low-quality audio.
- [ ] **FR9-06**: Export `data/synthetic_tts/synthetic_tts_manifest.jsonl` and `roundtrip_asr_check.jsonl`.
- [ ] **FR9-07**: Every audio record must be traceable to conversation, turn, term, voice, and TTS model.
- [ ] **FR9-08**: Synthetic data is train/augmentation only; final ASR test must be real-only.

### FR10 — ASR Evaluation by Domain/Entity

**Goal:** Evaluate ASR performance not just by WER/CER but broken down by medical domain and entity type.

- [ ] **FR10-01**: Run baseline faster-whisper ASR on evaluation splits.
- [ ] **FR10-02**: Compute WER, CER, CS-WER, and medical term recall metrics.
- [ ] **FR10-03**: Group metrics by domain/entity/split/topic; report Drug/Lab/Disease/Procedure recall.
- [ ] **FR10-04**: Identify and export top failed terms and term-level error analysis.
- [ ] **FR10-05**: Export `data/asr/asr_metrics_by_domain.csv` and `asr_term_error_analysis.csv`.
- [ ] **FR10-06**: Do not claim improvement without a controlled ablation experiment.

### FR11 — TV3 ASR & Diarization Evaluation Harness

**Goal:** Build an evaluation harness for PhoWhisper fine-tuning and pyannote/WhisperX diarization on real medical test audio.

- [ ] **FR11-01**: Build unified eval manifest (`eval_manifest.jsonl`) with `audio_path`, `transcript`, `split`, `source`, `duration`, `domain`, `specialty`, `gender`, `age_bucket`, `region`, `speaker_count`.
- [ ] **FR11-02**: Run zero-shot PhoWhisper-Small baseline on VietMed-test or approved real test audio; save predictions.
- [ ] **FR11-03**: Fine-tune PhoWhisper-Small in experiments: E0 (zero-shot), E1 (synthetic only), E2 (VietMed real only, if licensed), E3 (VietMed + synthetic, if licensed).
- [ ] **FR11-04**: Validate on real test audio only; do NOT validate on synthetic test to claim improvement.
- [ ] **FR11-05**: Compute WER/CER overall and by slice: region, gender, age_bucket, specialty, domain, entity_type.
- [ ] **FR11-06**: Run pyannote.audio 3.1 for speaker diarization; output RTTM format.
- [ ] **FR11-07**: Run WhisperX for word-level timestamps; combine with pyannote output for speaker-attributed transcripts.
- [ ] **FR11-08**: If reference RTTM exists: compute DER/JER with pyannote.metrics. If not: report qualitative/proxy metrics only.
- [ ] **FR11-09**: Ablation report comparing E0/E1/E2/E3 on real test; report absolute and relative WER changes.
- [ ] **FR11-10**: Generate `tv3_final_report.md` covering ASR metrics, diarization, ablation conclusions, and limitations.

### FR12 — Dataset Card and Release Plan

**Goal:** Prepare documentation for eventual public dataset release.

- [ ] **FR12-01**: Draft dataset card (`dataset_card_draft.md`) with description, splits, license, and reproducibility notes.
- [ ] **FR12-02**: Generate license report listing all data sources and their licenses.
- [ ] **FR12-03**: Generate privacy checklist confirming no PII is included in public artifacts.
- [ ] **FR12-04**: Draft release plan specifying what can be published (metadata/code/report) and what requires additional approval (raw audio).

## Traceability

### Phase Mapping

|| Requirement | Phase | Status |
||-------------|-------|--------|
|| FR1-01 – FR1-06 | Phase 6a | Pending |
|| FR2-01 – FR2-06 | Phase 6b | Pending |
|| FR3-01 – FR3-06 | Phase 6c | Pending |
|| FR4-01 – FR4-06 | Phase 6d | Pending |
|| FR5-01 – FR5-09 | Phase 6e | Pending |
|| FR6-01 – FR6-06 | Phase 6f | Pending |
|| FR7-01 – FR7-07 | Phase 6g | Pending |
|| FR8-01 – FR8-06 | Phase 6h | Pending |
|| FR9-01 – FR9-08 | Phase 6i | Pending |
|| FR10-01 – FR10-06 | Phase 6j | Pending |
|| FR11-01 – FR11-10 | Phase 6k | Pending |
|| FR12-01 – FR12-04 | Phase 6l | Pending |

### Coverage

- v1 requirements: 19 total — 19 mapped to phases — 0 unmapped ✓
- v1.1 requirements: 57 total — 57 mapped to phases — 0 unmapped ✓

---

*Requirements defined: 2026-06-16*
*Last updated: 2026-06-19 (v1.1 scope added, 12 feature groups, 57 requirement items)*
