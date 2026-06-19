# Architecture Research — VietMedVoice Phase 2 Enhancement

**Domain:** Vietnamese Medical Code-Switching ASR Evaluation Pipeline Extension
**Researched:** 2026-06-19
**Confidence:** HIGH

## Executive Summary

Phase 2 extends the existing Python CLI evaluation pipeline with ICD-10 ingestion, medical term inventory expansion, LLM conversation generation, TTS synthesis, voice pool management, and ASR/diarization evaluation. The architecture follows a **layered data flow pipeline** where each stage produces artifacts consumed by downstream stages, maintaining the existing modular `src/<module>` pattern. The critical integration chain is: ICD-10 → Term Inventory → Coverage Audit → Gap Analysis → Conversation Specs → TTS Input → Synthetic Audio → ASR Evaluation.

---

## Architecture Overview

### System Layers

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              PHASE 2 PIPELINE OVERVIEW                                    │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────────────────────────┐     │
│  │  Layer 4: Evaluation & Reporting                                                │     │
│  │  ┌──────────────┐  ┌──────────────────┐  ┌───────────────────────────────┐       │     │
│  │  │ ASR Metrics  │  │ Diarization Eval │  │ Final Report Generator        │       │     │
│  │  │ (extended)   │  │ (pyannote/WhisperX) │  │ (Vietnamese output)          │       │     │
│  │  └──────────────┘  └──────────────────┘  └───────────────────────────────┘       │     │
│  ├─────────────────────────────────────────────────────────────────────────────────┤     │
│  │  Layer 3: Synthesis & Generation                                                  │     │
│  │  ┌──────────────┐  ┌──────────────────┐  ┌───────────────────────────────┐       │     │
│  │  │ TTS Generator │  │ Voice Pool Mgr   │  │ Conversation Generator       │       │     │
│  │  │              │  │                  │  │ (LLM-based)                  │       │     │
│  │  └──────────────┘  └──────────────────┘  └───────────────────────────────┘       │     │
│  ├─────────────────────────────────────────────────────────────────────────────────┤     │
│  │  Layer 2: Inventory & Audit                                                      │     │
│  │  ┌──────────────┐  ┌──────────────────┐  ┌───────────────────────────────┐       │     │
│  │  │ Term Inventory│  │ Coverage Audit   │  │ VietMed Feasibility           │       │     │
│  │  │ (extended)    │  │                  │  │                              │       │     │
│  │  └──────────────┘  └──────────────────┘  └───────────────────────────────┘       │     │
│  ├─────────────────────────────────────────────────────────────────────────────────┤     │
│  │  Layer 1: Ingestion & Foundation                                                  │     │
│  │  ┌──────────────┐  ┌──────────────────┐  ┌───────────────────────────────┐       │     │
│  │  │ ICD-10       │  │ External Lexicon │  │ Dataset Clients               │       │     │
│  │  │ Ingestion    │  │ Ingestion        │  │ (ViMedCSS, VietMed)          │       │     │
│  │  └──────────────┘  └──────────────────┘  └───────────────────────────────┘       │     │
│  └─────────────────────────────────────────────────────────────────────────────────┘     │
│                                                                                                 │
│  SHARED INFRASTRUCTURE (cross-cutting)                                                          │
│  ┌─────────────────┐  ┌────────────────┐  ┌──────────────────┐  ┌─────────────────────┐     │
│  │ AppConfig       │  │ setup_logger    │  │ Pydantic Schemas │  │ CLI Subcommands     │     │
│  │ (YAML-driven)   │  │                 │  │ (validation)     │  │ (argparse)          │     │
│  └─────────────────┘  └────────────────┘  └──────────────────┘  └─────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Implementation Pattern | Feeds Into |
|-----------|---------------|----------------------|------------|
| `icd10_ingestion/` | Fetch, parse, join EN/VI ICD-10 from KCB endpoint | HTTP client + HTML parser + JSONL writer | `term_inventory/` |
| `term_inventory/` | Extended taxonomy: disease + drug/lab/procedure/abbreviation | Merges ICD-10 + external lexicons + LLM candidates | `coverage_audit/` |
| `coverage_audit/` | Match ViMedCSS terms against inventory; compute coverage rates | Term matching + statistics + Vietnamese report | `gap_analysis/` |
| `vietmed_feasibility/` | License/access audit of VietMed dataset | Metadata inspection + overlap analysis | `gap_analysis/` |
| `llm_generation/` | Generate doctor-patient conversations from ICD/specs | LLM API calls with structured output + JSON validation | `tts_generation/` |
| `voice_pool/` | Manage voice profiles: metadata, license, selection | CSV/JSONL inventory with confidence flags | `tts_generation/` |
| `tts_generation/` | Generate synthetic audio from conversations + voices | TTS API/local model + round-trip ASR validation | `asr_evaluation/` |
| `asr_evaluation/` (extended) | Compute WER/CER/CS-WER/Term Recall by domain/entity | Extends existing `src/asr/metrics.py` | `reporting/` |
| `diarization_evaluation/` | Speaker diarization with pyannote 3.1 + WhisperX | RTTM generation + DER/JER metrics | `reporting/` |
| `model_training/` | PhoWhisper fine-tuning experiments (E0-E3) | Training harness with config versioning | `asr_evaluation/` |

---

## Data Flow Architecture

### Primary Pipeline: ICD-10 → Term Inventory → Coverage → Generation → TTS → ASR

```
┌──────────────┐     ┌──────────────────┐     ┌───────────────────┐
│ ICD-10       │────▶│ Medical Term     │────▶│ Coverage Audit    │
│ Ingestion    │     │ Inventory        │     │                   │
│ (FR1)        │     │ (FR2)            │     │ (FR3)             │
└──────────────┘     └──────────────────┘     └─────────┬─────────┘
                                                        │
                    ┌──────────────────────────────────┴──────────┐
                    │                                              │
                    ▼                                              ▼
          ┌──────────────────┐                      ┌───────────────────┐
          │ VietMed          │                      │ Gap Analysis      │
          │ Feasibility      │                      │ (implicit)       │
          │ (FR4)           │                      │ Missing terms    │
          └────────┬─────────┘                      │ → generation    │
                   │                                └────────┬────────┘
                   │                                         │
                   │                                         ▼
                   │                              ┌───────────────────┐
                   └─────────────────────────────▶│ LLM Conversation  │
                                                │ Generation        │
                                                │ (FR5)             │
                                                └────────┬──────────┘
                                                         │
                    ┌────────────────────────────────────┴────────────┐
                    │                                                 │
                    ▼                                                 ▼
          ┌──────────────────┐                            ┌───────────────────┐
          │ Voice Pool       │──────────────────────────▶│ TTS Generation    │
          │ Research (FR8)   │                            │ (FR9)            │
          └──────────────────┘                            └─────────┬─────────┘
                                                                      │
                    ┌─────────────────────────────────────────────────┘
                    │
                    ▼
          ┌──────────────────┐     ┌───────────────────┐     ┌───────────────────┐
          │ Round-Trip       │────▶│ ASR Evaluation    │────▶│ TV3 PhoWhisper   │
          │ ASR Check        │     │ (FR10)            │     │ Fine-Tuning      │
          │                  │     │ WER/CER/CS-WER    │     │ (FR11)           │
          └──────────────────┘     └─────────┬─────────┘     └─────────┬─────────┘
                                              │                          │
                                              ▼                          ▼
                                    ┌───────────────────┐     ┌───────────────────┐
                                    │ Diarization       │     │ Ablation Study    │
                                    │ pyannote+WhisperX │     │ E0/E1/E2/E3      │
                                    │ DER/JER (FR11)    │     │ Comparison        │
                                    └───────────────────┘     └─────────┬─────────┘
                                                                       │
                                          ┌────────────────────────────┘
                                          ▼
                                ┌───────────────────┐
                                │ Final Reports     │
                                │ Dataset Card      │
                                │ (Vietnamese)      │
                                └───────────────────┘
```

### Data Flow: File-Based Contract Pattern

Each stage communicates via **immutable JSONL/CSV artifacts** with explicit schemas:

| Stage Pair | Output Artifact | Schema Source | Downstream Consumer |
|------------|----------------|---------------|---------------------|
| ICD-10 Ingestion → Term Inventory | `data/icd10/icd10_dual_language.jsonl` | FR1 schema in PRD | Term classifier, coverage audit |
| Term Inventory → Coverage Audit | `data/terms/medical_term_inventory.csv` | FR2 schema in PRD | Coverage matching |
| Coverage Audit → Gap Analysis | `data/coverage/vimedcss_missing_terms.csv` | FR3 output | Conversation spec selector |
| VietMed Feasibility → Gap Analysis | `data/coverage/vietmed_icd10_coverage.csv` | FR4 output | Same consumer |
| Gap Analysis → LLM Generation | `data/conversations/conversation_specs.jsonl` | FR5 input | LLM conversation generator |
| LLM Generation → TTS Generation | `data/conversations/doctor_patient_conversations.jsonl` | FR5 output | TTS synthesizer |
| Voice Pool → TTS Generation | `data/voice_pool/voice_profile_cards.jsonl` | FR8 output | Voice assignment |
| TTS Generation → ASR Evaluation | `data/synthetic_tts/synthetic_tts_manifest.jsonl` | FR9 output | Fine-tune training set |
| ASR Evaluation → TV3 | `data/asr/asr_metrics_by_domain.csv` | FR10 output | Ablation analysis |

---

## Project Structure

### Extended Directory Layout

```
vimedcss-eval-pipeline/
├── configs/                         # [EXTENDED] New config files for Phase 2
│   ├── icd10_ingestion.yaml        # KCB endpoint config, retry params
│   ├── term_taxonomy.yaml          # Extended taxonomy (already exists, extended)
│   ├── llm_generation.yaml          # Conversation prompt, model selection
│   ├── tts_models.yaml             # TTS model registry, local/API config
│   ├── asr_eval.yaml               # [EXTENDED] PhoWhisper config, fine-tune params
│   ├── voice_pool.yaml             # Voice selection criteria, diversity targets
│   └── diarization.yaml            # pyannote/WhisperX config
│
├── data/                            # [NEW] Structured data directory
│   ├── raw/
│   │   ├── vimedcss/               # (existing)
│   │   ├── vietmed/                # [NEW] VietMed metadata if accessible
│   │   └── icd10/                  # [NEW] Raw ICD-10 cache
│   ├── icd10/
│   │   ├── icd10_dual_language.jsonl
│   │   ├── icd10_dual_language.csv
│   │   └── icd10_ingestion_errors.csv
│   ├── terms/
│   │   ├── medical_term_inventory.csv    # Extended inventory
│   │   ├── term_sources.csv
│   │   ├── term_normalization_map.csv
│   │   └── human_review_terms.csv
│   ├── coverage/
│   │   ├── vimedcss_icd10_coverage.csv
│   │   ├── vimedcss_non_icd_coverage.csv
│   │   ├── vimedcss_domain_coverage_matrix.csv
│   │   ├── vimedcss_missing_terms.csv
│   │   ├── vimedcss_hard_terms.csv
│   │   ├── vietmed_icd10_coverage.csv
│   │   └── vietmed_vs_vimedcss_overlap.csv
│   ├── conversations/
│   │   ├── conversation_specs.jsonl
│   │   ├── doctor_patient_conversations.jsonl
│   │   └── conversation_validation_errors.jsonl
│   ├── voice_pool/
│   │   ├── voice_pool_inventory.csv
│   │   └── voice_profile_cards.jsonl
│   ├── synthetic_tts/
│   │   ├── synthetic_tts_manifest.jsonl
│   │   └── roundtrip_asr_check.jsonl
│   ├── asr/
│   │   ├── asr_predictions.jsonl
│   │   ├── asr_metrics_by_domain.csv
│   │   ├── asr_term_error_analysis.csv
│   │   ├── phowhisper_zero_shot_predictions.jsonl  # [NEW]
│   │   ├── phowhisper_finetune_runs.jsonl          # [NEW]
│   │   └── asr_predictions_by_run.jsonl            # [NEW]
│   ├── diarization/                                 # [NEW]
│   │   ├── pyannote_predictions.rttm
│   │   └── whisperx_word_speakers.jsonl
│   └── model_eval/
│       ├── llm_generation_benchmark.csv
│       ├── tts_model_comparison.csv
│       └── tts_term_pronunciation_test.csv
│
├── src/                             # [EXTENDED] New modules
│   ├── icd10_ingestion/             # [NEW] FR1
│   │   ├── __init__.py
│   │   ├── fetcher.py              # HTTP client for KCB endpoint
│   │   ├── parser.py               # JSON/HTML parser for ICD-10 response
│   │   └── joiner.py              # EN/VI join by code
│   │
│   ├── term_inventory/             # [NEW] FR2 — extends existing term module
│   │   ├── __init__.py
│   │   ├── lexicon_merger.py       # Merge ICD-10 + drug/lab/procedure lists
│   │   ├── classifier.py            # LLM-based entity/domain classification
│   │   └── normalizer.py           # Term normalization pipeline
│   │
│   ├── coverage_audit/              # [NEW] FR3 — extends existing auditor
│   │   ├── __init__.py
│   │   ├── matcher.py               # Term-to-inventory matching
│   │   ├── statistics.py            # Coverage rate computation
│   │   └── reporter.py              # Vietnamese coverage report
│   │
│   ├── vietmed_feasibility/         # [NEW] FR4
│   │   ├── __init__.py
│   │   ├── auditor.py               # License/access check
│   │   └── overlap_analyzer.py      # ICD-10/ViMedCSS overlap
│   │
│   ├── llm_generation/              # [NEW] FR5 — extends existing llm module
│   │   ├── __init__.py
│   │   ├── conversation_generator.py # Doctor-patient dialogue generation
│   │   ├── prompt_builder.py        # Spec-to-prompt conversion
│   │   ├── validator.py             # JSON schema + term validation
│   │   └── cost_analyzer.py         # FR6: LLM cost benchmarking
│   │
│   ├── tts_generation/              # [NEW] FR7/FR9
│   │   ├── __init__.py
│   │   ├── synthesizer.py           # TTS API/local model interface
│   │   ├── voice_assigner.py        # Role → voice mapping
│   │   └── roundtrip_checker.py     # ASR round-trip validation
│   │
│   ├── voice_pool/                  # [NEW] FR8
│   │   ├── __init__.py
│   │   ├── inventory.py             # Voice profile management
│   │   └── selector.py             # Voice diversity selection
│   │
│   ├── asr_evaluation/              # [EXTENDED] FR10/FR11
│   │   ├── __init__.py
│   │   ├── metrics_extended.py      # CS-WER, Medical-Term Recall
│   │   ├── domain_slicer.py         # WER by domain/entity/specialty
│   │   ├── phowhisper_eval.py       # FR11: PhoWhisper evaluation harness
│   │   └── finetune_runner.py       # FR11: PhoWhisper fine-tuning
│   │
│   ├── diarization/                # [NEW] FR11
│   │   ├── __init__.py
│   │   ├── pyannote_runner.py       # pyannote 3.1 diarization
│   │   ├── whisperx_aligner.py      # WhisperX word timestamps
│   │   └── metrics.py               # DER/JER computation
│   │
│   ├── model_training/             # [NEW] FR11
│   │   ├── __init__.py
│   │   ├── phowhisper_trainer.py    # PhoWhisper-Small fine-tuning
│   │   └── experiment_tracker.py    # E0/E1/E2/E3 run registry
│   │
│   ├── reporting/                   # [EXTENDED]
│   │   ├── report_generator.py       # (existing, extended for Phase 2)
│   │   ├── report_coverage.py       # Coverage report sections
│   │   ├── report_tts.py            # TTS quality report
│   │   └── report_tv3.py           # TV3 ablation report
│   │
│   ├── hf_client/                  # (existing)
│   ├── terms/                      # (existing, some methods reused)
│   ├── llm/                        # (existing, extended with new schemas)
│   ├── asr/                        # (existing, extended with new metrics)
│   ├── audit/                      # (existing)
│   ├── shared/                     # (existing: config, logging)
│   └── cli.py                      # (existing, extended with new subcommands)
│
├── outputs/                        # (existing, extended structure)
│   ├── audit/                     # (existing)
│   ├── term_coverage/             # (existing)
│   ├── asr_eval/                  # (existing, extended)
│   ├── reports/                   # (existing)
│   ├── icd10/                     # [NEW] ICD-10 ingestion outputs
│   ├── coverage/                  # [NEW] Coverage audit outputs
│   ├── conversations/              # [NEW] LLM generation outputs
│   ├── synthetic_tts/             # [NEW] TTS pilot outputs
│   ├── voice_pool/                 # [NEW] Voice pool outputs
│   ├── diarization/               # [NEW] Diarization outputs
│   └── tv3/                       # [NEW] TV3 experiment outputs
│
└── tests/                         # [EXTENDED]
    ├── test_icd10_ingestion.py    # [NEW]
    ├── test_term_inventory.py     # [NEW]
    ├── test_coverage_audit.py     # [NEW]
    ├── test_llm_generation.py     # [NEW]
    ├── test_tts_generation.py     # [NEW]
    ├── test_voice_pool.py         # [NEW]
    ├── test_asr_evaluation.py     # [EXTENDED]
    ├── test_diarization.py        # [NEW]
    └── test_phowhisper_eval.py    # [NEW]
```

### Structure Rationale

- **`src/<feature>/` pattern:** Each functional requirement (FR1-FR11) maps to a module under `src/`, matching the existing `src/asr/`, `src/terms/`, `src/llm/` pattern. This makes the codebase navigable by feature.
- **`data/` for intermediate artifacts:** Raw and processed data lives under `data/` (not `outputs/`), distinguishing between pipeline intermediates and evaluation outputs. This aligns with the existing `data/raw/` structure.
- **`configs/<feature>.yaml`:** Each feature gets its own YAML config, extending the existing `AppConfig` loader pattern. New config files are loaded via `AppConfig.get_<feature>_config()`.
- **`outputs/<feature>/` for reports:** Report artifacts go under `outputs/<feature>/`, consistent with existing `outputs/asr_eval/`, `outputs/term_coverage/`.

---

## Key Architectural Patterns

### Pattern 1: Pipeline Stage with JSONL File Contract

**What:** Each pipeline stage reads input from previous stage's JSONL/CSV output and writes its own JSONL/CSV output with explicit schema.
**When to use:** Primary integration pattern across all Phase 2 stages.
**Trade-offs:** +Explicit contracts, +Debuggable, +Replayable; -Disk I/O overhead, -Schema evolution needs migration.

```python
# Example: ICD-10 ingestion stage
class ICD10Fetcher:
    def run(self, codes: List[str], config: Dict) -> Dict[str, Any]:
        records = []
        for code in codes:
            en_data = self._fetch(code, lang="en")
            vi_data = self._fetch(code, lang="vi")
            record = self._join_by_code(en_data, vi_data)
            records.append(record)
        
        output_path = "data/icd10/icd10_dual_language.jsonl"
        self._write_jsonl(output_path, records)
        return {"output_path": output_path, "record_count": len(records)}

# Example: Term inventory consumes ICD-10
class TermInventoryBuilder:
    def run(self, icd10_path: str, external_paths: List[str]) -> Dict[str, Any]:
        icd10_records = self._read_jsonl(icd10_path)
        external_terms = self._merge_external(external_paths)
        inventory = self._build_inventory(icd10_records, external_terms)
        self._write_csv("data/terms/medical_term_inventory.csv", inventory)
        return {"term_count": len(inventory)}
```

### Pattern 2: Config-Driven Module Instantiation

**What:** Modules receive their configuration via `AppConfig.get_<feature>_config()` and are instantiated from CLI subcommands.
**When to use:** All Phase 2 modules follow this pattern to maintain consistency with existing architecture.
**Trade-offs:** +Centralized config, +Testable with mock configs; -YAML boilerplate, -Config drift risk.

```python
# CLI extension: add ICD-10 ingestion command
icd10_parser = subparsers.add_parser("ingest-icd10", help="Ingest ICD-10 dual-language EN/VI")
icd10_parser.add_argument("--codes-file", type=str, help="File with ICD-10 codes to query")
icd10_parser.add_argument("--mock", action="store_true", help="Use mock data")

# In CLI handler
elif args.command == "ingest-icd10":
    from src.icd10_ingestion.fetcher import ICD10Fetcher
    fetcher = ICD10Fetcher(config.get_icd10_config())
    stats = fetcher.run(codes_file=args.codes_file, mock=args.mock)
```

### Pattern 3: Schema-Validated JSONL Streaming

**What:** Use Pydantic models for schema validation when writing and reading JSONL, with streaming for large files.
**When to use:** Conversation generation, TTS manifest, ASR predictions.
**Trade-offs:** +Runtime validation, +IDE support; -Pydantic overhead for very large streams.

```python
# Conversation schema (extends existing src/llm/schemas.py)
class ConversationTurn(BaseModel):
    turn_id: int
    speaker_role: Literal["doctor", "patient", "nurse", "pharmacist"]
    text: str
    medical_terms: List[str] = []
    language_mix: Literal["vi", "en", "mixed"] = "mixed"

class DoctorPatientConversation(BaseModel):
    conversation_id: str
    icd10_code: str
    domain: str
    scenario_type: str
    code_switch_level: Literal["low", "medium", "high"]
    required_terms: List[str]
    turns: List[ConversationTurn]
    safety_flags: List[str] = []
    generation_model: str
    prompt_version: str

class ConversationGenerator:
    def _validate_and_write(self, conversations: List[DoctorPatientConversation], path: str):
        with open(path, "w", encoding="utf-8") as f:
            for conv in conversations:
                # Validate at write time
                f.write(conv.model_dump_json(by_alias=True, ensure_ascii=False) + "\n")
```

### Pattern 4: Mock/Smoke Test Mode

**What:** Every pipeline stage supports `--mock` flag for smoke testing without calling external APIs (LLM, TTS, ASR).
**When to use:** All Phase 2 modules inherit the existing `--mock` pattern from v1.0.
**Trade-offs:** +Rapid iteration, +CI-friendly; -Mock data may not catch integration bugs.

```python
# Follows existing pattern from src/llm/classifier.py and src/asr/transcriber.py
class TTSGenerator:
    def generate(self, conversations_path: str, mock: bool = False) -> Dict[str, Any]:
        if mock:
            logger.info("Mock mode: generating synthetic audio records without TTS API calls")
            return self._generate_mock_manifest(conversations_path)
        # Real TTS generation...
```

---

## Integration Points

### External Service Integrations

| Service | Integration Pattern | Module | Key Considerations |
|---------|---------------------|--------|-------------------|
| **KCB ICD-10 API** | HTTP GET with retry/circuit breaker | `icd10_ingestion/fetcher.py` | Rate limiting, HTML response parsing, no SLA guarantee |
| **OpenAI API** | Structured Outputs (existing pattern) | `llm_generation/conversation_generator.py` | Cost tracking per conversation, JSON validity rate, Vietnam medical prompt safety |
| **TTS API (various)** | HTTP API or local model | `tts_generation/synthesizer.py` | EN term pronunciation quality, Vietnamese fluency, cost per audio minute |
| **HuggingFace** | Dataset download, model loading | Multiple modules | Gated models (pyannote), token management |
| **PhoWhisper** | `faster-whisper` local inference | `asr_evaluation/phowhisper_eval.py` | GPU memory, batch size tuning |
| **pyannote 3.1** | `pyannote.audio` pipeline | `diarization/pyannote_runner.py` | Gated model acceptance on HF, audio preprocessing (mono/16kHz) |

### Internal Module Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `icd10_ingestion` → `term_inventory` | JSONL file (`icd10_dual_language.jsonl`) | Code-joined EN/VI records |
| `term_inventory` → `coverage_audit` | CSV file (`medical_term_inventory.csv`) | Extended taxonomy, source provenance |
| `coverage_audit` → `llm_generation` | CSV/JSONL (`vimedcss_missing_terms.csv`, `conversation_specs.jsonl`) | Gap-driven term selection |
| `llm_generation` → `tts_generation` | JSONL file (`doctor_patient_conversations.jsonl`) | Schema-validated conversations |
| `voice_pool` → `tts_generation` | JSONL file (`voice_profile_cards.jsonl`) | Voice metadata with confidence flags |
| `tts_generation` → `asr_evaluation` | JSONL file (`synthetic_tts_manifest.jsonl`) + actual audio files | Synthetic audio paths with quality status |
| `asr_evaluation` → `diarization` | Shared manifest (`eval_manifest.jsonl`) | Audio paths + ground truth for both ASR and diarization |

---

## Build Order & Dependency Graph

The Phase 2 build order must respect data dependencies. The following table maps FR to build priority:

### Phase 2 Build Sequence

| Phase | Weeks | FR | Module | Dependencies | Rationale |
|-------|-------|----|--------|-------------|-----------|
| **P2.1** | 1 | FR1 | ICD-10 Ingestion | None | Foundation; all downstream uses ICD-10 codes as join keys |
| **P2.1** | 1-2 | FR2 | Term Inventory | FR1, existing ViMedCSS terms | Extends ICD-10 with drug/lab/procedure lexicons; needs ICD-10 backbone |
| **P2.2** | 2 | FR3 | Coverage Audit | FR2, ViMedCSS metadata | Computes coverage rates; needs complete term inventory |
| **P2.2** | 3 | FR4 | VietMed Feasibility | None (metadata-only) | Independent of FR1-FR3 but informs gap analysis; can run in parallel |
| **P2.3** | 3-4 | FR5 | LLM Conversation Gen | FR3 (gap analysis), FR2 (term inventory) | Gap analysis output drives conversation specs; term inventory provides required terms |
| **P2.3** | 4 | FR6 | LLM Cost Analysis | FR5 | Benchmarking on FR5 outputs; can run in parallel with FR5 generation |
| **P2.4** | 5 | FR7 | TTS Model Research | None (research phase) | Independent; can start earlier; drives FR9 TTS selection |
| **P2.4** | 5 | FR8 | Voice Pool Research | None (metadata-only) | Independent; can start earlier; drives voice selection in FR9 |
| **P2.5** | 5 | FR9 | TTS Generation Pilot | FR5 (conversations), FR7 (model), FR8 (voices) | Requires all upstream to be ready; round-trip ASR validates quality |
| **P2.6** | 6 | FR10 | ASR Evaluation | FR9 (synthetic manifest), existing ASR infra | Extends existing metrics with domain/entity slicing |
| **P2.7** | 7-8 | FR11 | TV3 PhoWhisper + Diarization | FR4 (VietMed access), FR9 (synthetic) | Requires VietMed license approval; gated by real audio access |

### Dependency Diagram (Simplified)

```
[FR1 ICD-10] ──────────────┐
                           ▼
[FR2 Term Inventory] ──────┴──┬──▶ [FR3 Coverage Audit] ──▶ [FR5 Conv Specs] ─┐
                                │                                                     │
[ViMedCSS Metadata] ───────────┘                              │                    │
                                                             ▼                    │
[FR4 VietMed Feasibility] ──────────────────────────▶ [FR5 LLM Generation] ──┤
                                                                           │
[FR8 Voice Pool] ───────────────────────────────────────────────────────┬──▶ [FR9 TTS Gen]
                                                                          │
[FR7 TTS Research] ────────────────────────────────────────────────────┘
                                                                           │
[FR9 Synthetic Audio] ──▶ [FR10 ASR Evaluation] ◀── [VietMed Test Audio] ──┤
                                          │                                 │
                                          │         ┌────────────────────────┘
                                          ▼         ▼
                                   [FR11 TV3 PhoWhisper]
                                          │
                                          ▼
                                   [FR11 Diarization]
                                          │
                                          ▼
                                   [Final Reports]
```

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: In-Memory Chaining Without File Persistence

**What people do:** Pass dataframes/dicts directly between stages in memory, skipping file writes.
**Why it's wrong:** Breaks reproducibility, makes debugging harder, prevents partial re-runs.
**Do this instead:** Always write intermediate artifacts to `data/` or `outputs/` directories. Use file-based contracts even for small datasets.

### Anti-Pattern 2: Label-Based EN/VI ICD-10 Join

**What people do:** Join ICD-10 EN/VI records by matching label text.
**Why it's wrong:** Labels diverge between languages; code is the stable join key per PRD decision.
**Do this instead:** Join by `code` field. The existing codebase decision (KEY DECISION in PROJECT.md) confirms this.

### Anti-Pattern 3: Mixing Synthetic and Real Test Data

**What people do:** Combine synthetic TTS audio with real VietMed/ViMedCSS audio in the same evaluation test set.
**Why it's wrong:** Violates the "synthetic only for train/augmentation" policy. Final test must be real-only.
**Do this instead:** Keep synthetic manifest under `data/synthetic_tts/` with `synthetic_speaker_id` field; real audio under separate manifest. Track `source` field in all evaluation manifests.

### Anti-Pattern 4: Claiming DER/JER Without Reference

**What people do:** Running pyannote and reporting DER/JER without checking for reference RTTM.
**Why it's wrong:** DER/JER requires reference speaker annotations. Without reference, these metrics are undefined.
**Do this instead:** Check for reference RTTM; if absent, report only qualitative/proxy metrics and explicitly state `not_available_reason` in the output file.

### Anti-Pattern 5: Hardcoding LLM/TTS/ASR Credentials

**What people do:** Embedding API keys or tokens directly in config files or source code.
**Why it's wrong:** Security risk, config file committed to git, key rotation breaks pipeline.
**Do this instead:** Read credentials from environment variables (`.env`). Existing codebase already follows this pattern with `OPENAI_API_KEY`.

---

## Scalability Considerations

| Scale | Bottleneck | Approach |
|-------|-----------|----------|
| **Small (<1K conversations)** | LLM API cost and rate limits | Batch LLM calls, implement retry with exponential backoff |
| **Medium (1K-10K conversations)** | TTS generation time | Parallel TTS calls, local model if GPU available |
| **Large (10K+ conversations)** | Disk I/O, manifest management | Streaming JSONL reads/writes, partitioned output directories |
| **Very Large (100K+ audio)** | ASR inference time | PhoWhisper batch inference, GPU clustering |
| **Production TV3 fine-tuning** | GPU memory, training time | Gradient accumulation, checkpointing, experiment tracker |

### Scale-Specific Adjustments

| Concern | 100 Users | 1K Users | 10K Users |
|---------|-----------|----------|-----------|
| LLM Generation | Sequential API calls | Batch parallelization | Queue-based job system |
| TTS Storage | Local filesystem | External object storage (S3/GCS) | CDN distribution |
| ASR Evaluation | Single GPU | Multi-GPU batch | Distributed inference cluster |
| Metadata | SQLite | PostgreSQL | Data lake (Parquet) |

---

## CLI Extension Design

The Phase 2 CLI extends the existing `src/cli.py` pattern with new subcommands:

```python
# New Phase 2 subcommands (additions to existing CLI)
subparsers.add_parser("ingest-icd10", help="Ingest ICD-10 dual-language EN/VI from KCB endpoint")
subparsers.add_parser("build-term-inventory", help="Build extended medical term inventory")
subparsers.add_parser("audit-coverage", help="Audit ViMedCSS coverage against term inventory")
subparsers.add_parser("check-vietmed", help="Check VietMed feasibility and overlap")
subparsers.add_parser("generate-conversations", help="Generate doctor-patient conversations via LLM")
subparsers.add_parser("benchmark-llm", help="Benchmark LLM cost and JSON validity")
subparsers.add_parser("research-tts", help="Research TTS models for Vietnamese + EN medical terms")
subparsers.add_parser("build-voice-pool", help="Build voice pool inventory")
subparsers.add_parser("generate-tts", help="Generate synthetic TTS audio from conversations")
subparsers.add_parser("eval-asr-domain", help="Evaluate ASR by domain/entity/specialty")
subparsers.add_parser("run-diarization", help="Run pyannote 3.1 + WhisperX diarization")
subparsers.add_parser("finetune-phowhisper", help="Fine-tune PhoWhisper-Small (E0/E1/E2/E3)")
subparsers.add_parser("run-tv3-eval", help="Run full TV3 ASR + diarization evaluation")
subparsers.add_parser("generate-phase2-report", help="Generate Phase 2 consolidated Vietnamese report")
```

Each command follows the existing pattern: instantiate module → call `run()` or `generate()` → print stats → write outputs.

---

## Schema Compatibility Notes

### Existing Schemas to Extend

| Existing Schema | Extension | Backward Compatible |
|-----------------|-----------|---------------------|
| `src/llm/schemas.py` — `EntityCategory`, `MedicalDomain`, `MedicalSpecialty` | Add new enum values if needed for Phase 2 term types | Yes, enum extension is additive |
| `src/llm/schemas.py` — `TermClassificationItem` | Add new fields for Phase 2 provenance | Yes, optional fields only |
| `src/asr/metrics.py` — `ASRMetrics.compute_and_write()` | Add domain/entity slicing; existing WER/CER unchanged | Yes, additive metrics |
| `outputs/term_coverage/cs_terms_inventory.csv` | Extend with `icd10_code`, `source_lexicon`, `review_status` | Yes, new columns are nullable |

### New Schemas Required

| Schema | Location | Purpose |
|--------|----------|---------|
| `ICD10Record` | `src/icd10_ingestion/schemas.py` | ICD-10 EN/VI dual-language record |
| `DoctorPatientConversation` | `src/llm_generation/schemas.py` | LLM-generated dialogue |
| `VoiceProfile` | `src/voice_pool/schemas.py` | Voice metadata with confidence |
| `SyntheticTTSManifest` | `src/tts_generation/schemas.py` | TTS audio generation manifest |
| `EvalManifest` | `src/asr_evaluation/schemas.py` | Unified manifest for ASR + diarization |
| `PhoWhisperRun` | `src/model_training/schemas.py` | Fine-tune experiment metadata |

---

## Sources

- PRD: `docs/prd/PRD_VietMedVoice_Phase2_Enhancement_v1.1.md` (primary requirements)
- Existing codebase patterns: `src/cli.py`, `src/llm/classifier.py`, `src/asr/transcriber.py`, `src/shared/config.py`
- PhoWhisper: VinAI PhoWhisper GitHub (model sizes, WER benchmarks)
- pyannote 3.1: `pyannote/speaker-diarization-3.1` on HuggingFace (gated model)
- WhisperX: GitHub `星光尾/WhisperX` (alignment + diarization integration)
- Existing architecture: Phase 1 codebase structure (modular `src/<module>`, YAML configs, JSONL/CSV outputs)

---

*Architecture research for: VietMedVoice Phase 2 Enhancement*
*Researched: 2026-06-19*
