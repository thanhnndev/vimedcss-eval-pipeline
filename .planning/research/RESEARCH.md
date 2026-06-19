# VietMedVoice Phase 2 Enhancement — Research Synthesis

**Project:** VietMedVoice Phase 2 Enhancement v1.1  
**Synthesized:** 2026-06-19  
**Confidence:** MEDIUM-HIGH  
**Sources:** STACK.md, FEATURES.md, ARCHITECTURE.md, PITFALLS.md, STATE.md, icd10-api-kcb.md

---

## 1. Executive Summary

Phase 2 of VietMedVoice extends the existing Python CLI evaluation pipeline (v1.0) with six new capability areas: ICD-10 dual-language ingestion, extended medical term taxonomy, LLM-generated doctor-patient conversation synthesis, Vietnamese TTS with English code-switching support, voice pool management, and PhoWhisper fine-tuning with ASR/diarization evaluation.

The research covers four dimensions: **technology stack** (40+ packages), **11 functional requirements** (FR1–FR11), **system architecture** (4-layer pipeline with 8 new modules), and **12 critical pitfalls**. The core challenge is the **ICD-10 → Term Inventory → Gap Analysis → Conversation Generation → TTS → ASR** integration chain, where each stage depends on the quality of the previous stage's output. A single bad assumption in FR1 propagates through all downstream stages.

**Critical path items (must resolve before Phase 2 build):**
1. ICD-10 EN/VI join by **code**, not label (Pitfall 1 — highest impact)
2. VietMed dataset license verification before any data access (Pitfall 4, 11)
3. TTS code-switching pronunciation validation before committing to a model (Pitfall 5)
4. PhoWhisper LoRA fine-tuning design (not full-parameter) to prevent catastrophic forgetting (Pitfall 7)
5. Real-only test set segregation from synthetic audio (Pitfall 11)

**Overall implementation confidence: MEDIUM-HIGH.** Core tooling (OpenAI/Anthropic SDKs, PEFT, pyannote, WhisperX) is Context7-verified. Vietnamese-specific tooling (PhoWhisper, VieNeu-TTS, vietnormalizer) is verified via web search and recent papers (2025–2026). Some Vietnamese TTS voice datasets have licensing constraints that require team sign-off.

---

## 2. Technology Stack

### 2.1 Core LLM API Clients

| Technology | Version | Purpose | Rationale |
|------------|--------|---------|-----------|
| **openai** | ≥1.68.0 | LLM conversation generation via `gpt-4o`, `gpt-4o-mini` | `chat.completions.parse()` for Pydantic-validated JSON output; streaming via `async with client.chat.completions.stream()` |
| **anthropic** | ≥0.40.0 | Claude 3.5/3.7 for higher-quality medical text | `output_format=PydanticModel` for streaming JSON parsing; better medical nuance |
| **huggingface_hub** | ≥0.26.0 | Access PhoWhisper, viVoice, PhoAudiobook | Unified HF API for model/dataset downloads with progress hooks |

### 2.2 ASR & Fine-tuning

| Technology | Version | Purpose | Rationale |
|------------|--------|---------|-----------|
| **transformers** | ≥4.46.0 | PhoWhisper model loading | `pipeline("automatic-speech-recognition", model="vinai/PhoWhisper-small")` |
| **peft** | ≥0.14.0 | LoRA/QLORA fine-tuning | `get_peft_model()` + `LoraConfig`; required to avoid catastrophic forgetting (see Pitfall 7) |
| **accelerate** | ≥1.0.0 | Distributed training, multi-GPU | Required for PhoWhisper fine-tuning at scale |
| **bitsandbytes** | ≥0.44.0 | 8-bit/4-bit quantization | `load_in_8bit=True` for PhoWhisper-large on consumer GPUs |
| **vinai/PhoWhisper-small** | 244M | Vietnamese ASR base model | WER: 11.08% (CMV-Vi), 6.33% (VIVOS); fine-tuned from Whisper-small on 844h Vietnamese |
| **vinai/PhoWhisper-medium** | 769M | Higher-accuracy variant | WER: 8.27% (CMV-Vi); requires 24GB+ VRAM |
| **jiwer** | ≥3.0.0 | WER/CER computation | Standard ASR evaluation metrics |
| **librosa** | ≥0.10.0 | Audio loading/preprocessing | `librosa.load(path, sr=16000)` for ASR input |

### 2.3 Speaker Diarization

| Technology | Version | Purpose | Rationale |
|------------|--------|---------|-----------|
| **pyannote.audio** | ≥3.1.0 | Speaker diarization pipeline | `Pipeline.from_pretrained("pyannote/speaker-diarization-3.1")`; requires HF token acceptance |
| **whisperx** | ≥3.3.0 | Word-level timestamps + speaker attribution | Complete pipeline: `transcribe()` → `align()` → `assign_word_speakers()` |

### 2.4 TTS (Vietnamese + English Code-Switching)

| Technology | Version | Purpose | Rationale |
|------------|--------|---------|-----------|
| **VieNeu-TTS-v3-Turbo** | 2026 | Primary Vietnamese TTS with code-switching | 48kHz, instant voice cloning (3–5s), built-in sea-g2p phonemizer for EN/VI code-switching; **best for medical CS content** |
| **VieNeu-TTS-v2** | 2025 | Proven stable alternative | 24kHz, Podcast/Conversation mode; GGUF variants for CPU inference |
| **Coqui XTTS-v2** | ≥2.0.2 | Zero-shot multilingual TTS | Vietnamese via `thivux/xtts-v2-vietnamese`; ACL 2025 paper confirms outperforms VALL-E/VoiceCraft on PhoAudiobook |
| **vietnormalizer** | ≥1.0.0 | Vietnamese text preprocessing for TTS | **Critical dependency.** Converts numbers, dates, acronyms, medical abbreviations to pronounceable forms. Use before ANY TTS input. |

### 2.5 ICD-10 Ingestion

| Technology | Version | Purpose | Rationale |
|------------|--------|---------|-----------|
| **httpx** | ≥0.28.0 | Async HTTP client | Async support for concurrent ICD-10 queries; `httpx.AsyncClient` with retry + timeout |
| **beautifulsoup4** | ≥4.12.0 | HTML parsing | Parse nested HTML from KCB endpoint response |
| **lxml** | ≥5.0.0 | Fast HTML parser backend | Required for complex nested HTML from ICD-10 endpoint |

**KCB ICD-10 Endpoint (reverse-engineered):**
- Base: `https://ccs.whiteneuron.com/api/ICD10/search/<query>`
- Parameters: `lang=vi|en`, `vol1=1`, `vol3=0`, `html=true` (required)
- Response: JSON with `html` field containing nested `<ul>/<li>` structure
- **Critical caveat:** `html=false` returns HTTP 500; rate-limit ≥200ms between requests
- Vietnamese free-text search is unreliable — **always use code search first, then cross-ref with lang=vi**

### 2.6 Data Processing

| Technology | Version | Purpose |
|------------|--------|---------|
| **datasets** | ≥3.2.0 | HF dataset loading, streaming for ViMedCSS, viVoice, PhoAudiobook |
| **pandas** | ≥2.2.0 | CSV/JSONL tabular operations |
| **pydantic** | ≥2.9.0 | JSON schema validation for all pipeline artifacts |

### 2.7 Voice Pool / Dataset Access

| Resource | Size | Speakers | Key Metadata | License | Notes |
|----------|------|----------|--------------|---------|-------|
| **viVoice** (capleaf/viVoice) | 1,017h | 243 | gender, age, region | CC-BY-4.0 | Check before use |
| **PhoAudiobook** (thivux/phoaudiobook) | 941h | 735 | speaker IDs | Research-only | ACL 2025; optimized for zero-shot TTS; IPA phonemized |
| **VieNeu-TTS-140h** (pnnbao-ump) | 140.7h | 193 | gender explicitly | Apache 2.0 | Clean WAV 24kHz; **recommended for voice pool** |
| **VietSuperSpeech** (thanhnew2001/VietSuperSpeech) | 267h | ~27k | — | Open | For ASR fine-tuning (not TTS primary); pseudo-labeled |

### 2.8 Supporting Libraries

| Library | Version | Purpose |
|---------|---------|---------|
| `python-dotenv` | ≥1.0.0 | API key management (never commit keys) |
| `tenacity` | ≥8.4.0 | Retry logic with exponential backoff for ICD-10 endpoint |
| `tqdm` | ≥4.66.0 | Progress bars for generation loops |
| `loguru` | ≥0.7.0 | Structured logging replacing `print()` |
| `pyyaml` | ≥6.0.0 | Config file management |
| `soundfile` | ≥0.12.0 | Audio I/O for WAV save/load |

### 2.9 Development Environment

| Tool | Purpose |
|------|---------|
| **CUDA 12.x + cuDNN 8.9+** | GPU acceleration; PhoWhisper-small + 8-bit requires ~16GB VRAM; medium requires ~24GB |
| **Python 3.10+** | Runtime; 3.12 recommended for async performance |
| **uv** | Package manager; use `uv pip install` or `uv sync` |
| **Weights & Biases** | Optional experiment tracking for fine-tuning |
| **Docker** | Reproducible environments for ICD-10 ingestion, TTS, ASR evaluation |

### 2.10 What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Google Cloud TTS | English-centric, poor Vietnamese tonality, expensive | VieNeu-TTS-v3-Turbo (local) |
| Microsoft Azure Speech | Commercial license, no Vietnamese advantage | VieNeu-TTS for local, OpenAI TTS API fallback |
| Standard Whisper (not PhoWhisper) | PhoWhisper achieves 30–40% lower WER on Vietnamese | PhoWhisper-small/medium |
| Raw `requests` library | No async support for bulk ICD-10 queries | `httpx.AsyncClient` |
| Manual HTML regex parsing | Fragile, breaks on HTML changes | BeautifulSoup + lxml |
| Fake JSON from LLM without validation | High invalid-JSON rate | `response_format=PydanticModel` (OpenAI) or `output_format=Model` (Anthropic) |
| Full fine-tune of PhoWhisper-large | 1.55B params requires 40GB+ VRAM; catastrophic forgetting risk | PhoWhisper-small + LoRA |

### 2.11 Stack Patterns by Constraint

**If GPU VRAM < 16GB:**
- PhoWhisper-small + LoRA (8-bit) for fine-tuning
- VieNeu-TTS-v2 GGUF Q4 for CPU TTS inference
- Batch ASR inference with `batch_size=4`

**If GPU VRAM ≥ 24GB:**
- PhoWhisper-medium + LoRA for higher accuracy
- VieNeu-TTS-v3-Turbo PyTorch for best TTS quality

**If API budget is constrained:**
- `gpt-4o-mini` for conversation generation (80% cheaper than gpt-4o)
- OpenAI structured output to avoid retry wasted tokens
- Cache ICD-10 responses locally

**If medical term quality is critical:**
- `claude-3-5-sonnet` for conversation generation
- `vietnormalizer` preprocessing before ALL TTS calls

---

## 3. Feature Landscape

### 3.1 Feature Overview (FR1–FR11)

| # | Feature | Category | Priority | Complexity | Dependencies |
|---|---------|----------|----------|------------|--------------|
| FR1 | ICD-10 dual-language ingestion | Ingestion | P1 | MEDIUM | None |
| FR2 | Extended medical term taxonomy | Inventory | P1 | MEDIUM | FR1 |
| FR3 | ViMedCSS coverage audit | Audit | P1 | LOW | FR2, ViMedCSS metadata |
| FR4 | VietMed feasibility audit | Research | P2 | MEDIUM | None (metadata-only) |
| FR5 | LLM conversation generation | Generation | P1 | HIGH | FR3, FR2 |
| FR6 | LLM cost analysis | Reporting | P2 | LOW | FR5 |
| FR7 | TTS model research | Research | P1 | MEDIUM | None |
| FR8 | Voice pool research | Research | P2 | MEDIUM | None |
| FR9 | Synthetic TTS generation | Generation | P2 | HIGH | FR5, FR7, FR8 |
| FR10 | ASR evaluation by domain/entity | Evaluation | P1 | LOW | FR9, existing ASR infra |
| FR11 | PhoWhisper fine-tuning + diarization | Evaluation | P2 | HIGH | FR4, FR9 |

### 3.2 Table Stakes vs. Differentiators

**Table Stakes** (non-negotiable for a research-grade pipeline):

| Feature | Why Expected | Key Risk if Missing |
|---------|--------------|---------------------|
| ICD-10 dual-language disease inventory | Disease backbone for term taxonomy | Coverage audit has no reference vocabulary |
| Medical term taxonomy (entity types) | Covers diseases, drugs, labs, procedures, abbreviations, biomarkers | Term inventory is ICD-10-only, missing 7+ entity types |
| ViMedCSS coverage audit | Quantifies coverage gaps | Cannot drive conversation generation priorities |
| JSONL conversation schema with safety flags | Structured synthetic data for TTS input | TTS has no validated input format |
| Round-trip ASR pronunciation check | Validates TTS correctly pronounces medical terms | Mispronunciations propagate to ASR training |
| ASR metrics by domain/entity | Identifies which medical areas ASR fails on | Cannot target fine-tuning effectively |
| PhoWhisper zero-shot baseline | Establishes E0 for ablation comparison | Cannot validate fine-tuning improvement |

**Differentiators** (competitive advantage for medical code-switching research):

| Feature | Value Proposition | Complexity |
|---------|-------------------|------------|
| ICD-10 EN/VI ingestion via FHIR | Official, authoritative, 15K+ disease codes with dual-language labels | MEDIUM |
| Medical entity classification (9 types) | Distinguishes disease vs. drug vs. lab vs. procedure vs. abbreviation vs. hormone vs. biomarker vs. device vs. unit | MEDIUM |
| LLM conversation generation with ICD grounding | Generates doctor-patient dialogues anchored to specific ICD codes | HIGH |
| VieNeu-TTS code-switching support | Local Vietnamese TTS that handles EN medical terms within VI sentences | MEDIUM |
| Voice pool with dialect metadata | Diverse synthetic voices covering North/Central/South regions | MEDIUM |
| PhoWhisper fine-tuning with ablation | E0/E1/E2/E3 comparison validating synthetic augmentation value | HIGH |
| pyannote 3.1 + WhisperX speaker attribution | Word-level speaker labels for doctor-patient analysis | MEDIUM |

### 3.3 Anti-Features (Explicitly Excluded)

| Anti-Feature | Why Excluded | Alternative |
|--------------|--------------|-------------|
| LLM output as ground truth | LLM can hallucinate rare terms; no accountability | LLM as candidate label + human review gate |
| All synthetic data for final test set | ASR overfits to synthetic style; invalidates evaluation | Synthetic only for train/augmentation; real-only for final test |
| Claim full ICD-10 coverage | Only 15K disease codes; doesn't cover drugs/labs/procedures | Report verified coverage percentages with evidence |
| Guess speaker gender/age/region | Inference is unreliable; violates data integrity | Use `unknown` or `estimated_*` with confidence level |
| Voice cloning from real doctors/patients | Requires explicit consent; policy not defined | Use synthetic voices from TTS model |
| Public raw audio from YouTube/TikTok | License/PHI issues | Only use licensed sources |

### 3.4 Feature Dependency Chain

```
[FR1 ICD-10 Ingestion]
    └──requires──> [FR2 Medical Term Inventory]
                           └──requires──> [FR3 ViMedCSS Coverage Audit]

[FR2 Medical Term Inventory]
    └──required-for──> [FR5 LLM Conversation Generation]
                                   └──required-for──> [FR9 Synthetic TTS Generation]

[FR8 Voice Pool Research]
    └──required-for──> [FR9 Synthetic TTS Generation]

[FR9 Synthetic TTS Generation]
    └──required-for──> [FR10 Round-trip ASR Check]
                                 └──required-for──> [FR11 PhoWhisper Fine-tuning]

[FR4 VietMed Feasibility] ──validates──> [FR11 Fine-tuning experiment design]

[FR7 TTS Model Research] ──informs──> [FR9 TTS Generation model selection]
```

### 3.5 Build Order (8-Week Plan)

| Weeks | Phase | FR | Module | Rationale |
|-------|-------|----|--------|-----------|
| 1 | P2.1 | FR1 | ICD-10 Ingestion | Foundation; all downstream uses ICD-10 codes as join keys |
| 1–2 | P2.1 | FR2 | Term Inventory | Extends ICD-10 with drug/lab/procedure lexicons |
| 2 | P2.2 | FR3 | Coverage Audit | Computes coverage rates; needs complete term inventory |
| 3 | P2.2 | FR4 | VietMed Feasibility | Independent; can run in parallel with FR3 |
| 3–4 | P2.3 | FR5 | LLM Conversation Gen | Gap analysis drives conversation specs |
| 4 | P2.3 | FR6 | LLM Cost Analysis | Benchmarking; can run parallel with FR5 generation |
| 5 | P2.4 | FR7 + FR8 | TTS Research + Voice Pool | Independent research; drives FR9 selection |
| 5 | P2.5 | FR9 | TTS Generation Pilot | Requires FR5 conversations + FR7/FR8 model selection |
| 6 | P2.6 | FR10 | ASR Evaluation | Extends existing metrics with domain/entity slicing |
| 7–8 | P2.7 | FR11 | PhoWhisper + Diarization | Gated by VietMed license approval |

---

## 4. System Architecture

### 4.1 Pipeline Overview (4-Layer)

```
┌──────────────────────────────────────────────────────────────────────┐
│  Layer 4: Evaluation & Reporting                                      │
│  ASR Metrics (extended) │ Diarization Eval │ Report Generator (VI)   │
├──────────────────────────────────────────────────────────────────────┤
│  Layer 3: Synthesis & Generation                                     │
│  TTS Generator │ Voice Pool Manager │ Conversation Generator (LLM)  │
├──────────────────────────────────────────────────────────────────────┤
│  Layer 2: Inventory & Audit                                          │
│  Term Inventory │ Coverage Audit │ VietMed Feasibility               │
├──────────────────────────────────────────────────────────────────────┤
│  Layer 1: Ingestion & Foundation                                     │
│  ICD-10 Ingestion │ External Lexicon │ Dataset Clients              │
├──────────────────────────────────────────────────────────────────────┤
│  SHARED INFRASTRUCTURE                                                │
│  AppConfig (YAML) │ setup_logger │ Pydantic Schemas │ CLI Commands  │
└──────────────────────────────────────────────────────────────────────┘
```

### 4.2 Module Responsibilities

| Module | Responsibility | Feeds Into |
|--------|---------------|------------|
| `icd10_ingestion/` | Fetch, parse, join EN/VI ICD-10 from KCB endpoint | `term_inventory/` |
| `term_inventory/` | Extended taxonomy: disease + drug/lab/procedure/abbreviation | `coverage_audit/` |
| `coverage_audit/` | Match ViMedCSS terms against inventory; compute coverage rates | `gap_analysis/` (implicit) |
| `vietmed_feasibility/` | License/access audit of VietMed dataset | `gap_analysis/`, `model_training/` |
| `llm_generation/` | Generate doctor-patient conversations from ICD/specs | `tts_generation/` |
| `voice_pool/` | Manage voice profiles: metadata, license, selection | `tts_generation/` |
| `tts_generation/` | Generate synthetic audio from conversations + voices | `asr_evaluation/` |
| `asr_evaluation/` (extended) | Compute WER/CER/CS-WER/Term Recall by domain/entity | `reporting/` |
| `diarization_evaluation/` | Speaker diarization with pyannote 3.1 + WhisperX | `reporting/` |
| `model_training/` | PhoWhisper fine-tuning experiments (E0–E3) | `asr_evaluation/` |

### 4.3 Directory Structure

```
vimedcss-eval-pipeline/
├── configs/                     # [NEW] Phase 2 YAML configs
│   ├── icd10_ingestion.yaml
│   ├── llm_generation.yaml
│   ├── tts_models.yaml
│   ├── voice_pool.yaml
│   └── diarization.yaml
├── data/
│   ├── icd10/
│   │   ├── icd10_dual_language.jsonl      # FR1 output
│   │   └── icd10_ingestion_errors.csv
│   ├── terms/
│   │   ├── medical_term_inventory.csv     # FR2 output
│   │   └── term_sources.csv
│   ├── coverage/
│   │   ├── vimedcss_icd10_coverage.csv     # FR3 output
│   │   ├── vimedcss_missing_terms.csv
│   │   └── vimedcss_hard_terms.csv
│   ├── conversations/
│   │   ├── conversation_specs.jsonl         # FR5 input
│   │   └── doctor_patient_conversations.jsonl # FR5 output
│   ├── voice_pool/
│   │   └── voice_profile_cards.jsonl       # FR8 output
│   ├── synthetic_tts/
│   │   ├── synthetic_tts_manifest.jsonl     # FR9 output
│   │   └── roundtrip_asr_check.jsonl
│   ├── asr/
│   │   ├── asr_metrics_by_domain.csv       # FR10 output
│   │   ├── phowhisper_zero_shot_predictions.jsonl
│   │   └── phowhisper_finetune_runs.jsonl
│   └── diarization/
│       ├── pyannote_predictions.rttm        # FR11 output
│       └── whisperx_word_speakers.jsonl
├── src/
│   ├── icd10_ingestion/           # [NEW] FR1
│   ├── term_inventory/            # [NEW] FR2
│   ├── coverage_audit/            # [NEW] FR3
│   ├── vietmed_feasibility/       # [NEW] FR4
│   ├── llm_generation/            # [NEW] FR5
│   ├── tts_generation/            # [NEW] FR7/FR9
│   ├── voice_pool/                # [NEW] FR8
│   ├── asr_evaluation/            # [EXTENDED] FR10/FR11
│   ├── diarization/              # [NEW] FR11
│   ├── model_training/            # [NEW] FR11
│   ├── reporting/                 # [EXTENDED]
│   └── cli.py                     # [EXTENDED] new subcommands
├── outputs/
│   ├── icd10/                     # [NEW]
│   ├── coverage/                  # [NEW]
│   ├── conversations/             # [NEW]
│   ├── synthetic_tts/             # [NEW]
│   ├── voice_pool/                # [NEW]
│   ├── diarization/              # [NEW]
│   └── tv3/                       # [NEW]
└── tests/                         # [EXTENDED]
    ├── test_icd10_ingestion.py    # [NEW]
    ├── test_llm_generation.py     # [NEW]
    ├── test_tts_generation.py     # [NEW]
    └── test_phowhisper_eval.py    # [NEW]
```

### 4.4 Key Architectural Patterns

**Pattern 1 — Pipeline Stage with JSONL File Contract:** Each stage reads from previous stage's JSONL/CSV and writes its own output. Every artifact has an explicit Pydantic schema.

**Pattern 2 — Config-Driven Module Instantiation:** All modules receive configuration via `AppConfig.get_<feature>_config()` and are instantiated from CLI subcommands. Follows existing `src/cli.py` pattern.

**Pattern 3 — Schema-Validated JSONL Streaming:** Pydantic models validate at write time. Key schemas: `DoctorPatientConversation`, `VoiceProfile`, `SyntheticTTSManifest`, `EvalManifest`.

**Pattern 4 — Mock/Smoke Test Mode:** Every pipeline stage supports `--mock` flag for smoke testing without calling external APIs. Follows existing v1.0 pattern.

### 4.5 Integration Points

| Boundary | Communication Method | Notes |
|----------|---------------------|-------|
| `icd10_ingestion` → `term_inventory` | JSONL file (`icd10_dual_language.jsonl`) | Join by code only |
| `term_inventory` → `coverage_audit` | CSV file (`medical_term_inventory.csv`) | Entity type + source provenance |
| `coverage_audit` → `llm_generation` | JSONL (`conversation_specs.jsonl`) | Gap-driven term selection |
| `llm_generation` → `tts_generation` | JSONL (`doctor_patient_conversations.jsonl`) | Schema-validated conversations |
| `voice_pool` → `tts_generation` | JSONL (`voice_profile_cards.jsonl`) | Metadata with confidence flags |
| `tts_generation` → `asr_evaluation` | JSONL manifest + audio files | Quality status per sample |
| `asr_evaluation` ↔ `diarization` | Shared eval manifest | Audio + ground truth for both |

---

## 5. Critical Pitfalls

### 5.1 All 12 Pitfalls — Consolidated View

| # | Pitfall | Impact | Phase | Prevention |
|---|---------|--------|-------|------------|
| 1 | **Joining ICD-10 EN/VI by label instead of code** | CRITICAL — empty dual-language inventory | FR1 | Join by `code` field only; log every unmatched code |
| 2 | **ICD-10 endpoint fragility — no retry, no caching, no versioning** | HIGH — incomplete/inconsistent inventory | FR1 | Exponential backoff retry (3–5 attempts); cache raw responses; track `fetched_at` |
| 3 | **Treating ICD-10 as sufficient for all medical terms** | HIGH — fundamentally incomplete taxonomy | FR2 | Design 9 entity types from Day 1; source each type from licensed data |
| 4 | **LLM hallucination in conversations — medical fact fabrication** | CRITICAL — wrong medical patterns in training | FR5 | RAG grounding to ICD/drug/procedure facts; post-generation validation; 5–10% human review |
| 5 | **TTS mispronouncing English medical terms in Vietnamese sentences** | HIGH — corrupts synthetic ASR training signal | FR7 | Round-trip ASR check per term; per-term quality logging; never use Turbo mode for medical terms |
| 6 | **Synthetic audio overwhelming real data in PhoWhisper fine-tuning** | HIGH — model performs worse on real audio | FR11 | Cap synthetic at 20–30% of training volume; rejection sampling; real-only test set |
| 7 | **Catastrophic forgetting in PhoWhisper fine-tuning** | HIGH — loses multilingual/general ASR capabilities | FR11 | Use PEFT (LoRA); freeze lower encoder layers; evaluate on general Vietnamese benchmark |
| 8 | **Claiming DER/JER without reference RTTM** | HIGH — meaningless metric | FR11 | Only report DER/JER when human-annotated RTTM exists; otherwise qualitative only |
| 9 | **Claiming ASR improvement without controlled ablation** | HIGH — invalid improvement claim | FR10/FR11 | Include E0 baseline in every run; test on real-only audio; report absolute + relative change |
| 10 | **Inferring speaker gender/age/region without evidence** | MEDIUM — fabricated demographic labels | FR8 | Default to `unknown`; use `estimated_*` prefix with confidence; never unlabeled |
| 11 | **Mixing synthetic and real audio in test set** | CRITICAL — meaningless WER numbers | FR9/FR10 | Enforce at manifest level: `source` field; preflight check; separate directories |
| 12 | **Conflating ASR-oriented diarization with ground truth** | MEDIUM — inflated DER from annotation mismatch | FR11 | Use forgiveness collar; set `skip_overlap=True`; document annotation limitations in report |

### 5.2 Highest-Risk Cross-Cutting Pitfalls

Three pitfalls have the highest propagation risk because they affect the **core ICD-10 → Term → Conversation → TTS → ASR chain**:

**Pitfall 1 (EN/VI join by label)** cascades into:
- Term inventory has empty VI labels → coverage audit cannot match Vietnamese terms → conversation generation lacks grounded VI medical vocabulary → TTS produces no meaningful synthetic medical audio

**Pitfall 11 (synthetic in test set)** cascades into:
- ASR appears artificially good on synthetic audio → fine-tuning decision based on false signal → real audio performance degrades

**Pitfall 7 (catastrophic forgetting)** cascades into:
- PhoWhisper loses general Vietnamese ASR capability → fine-tuned model regresses on non-medical Vietnamese → entire evaluation pipeline produces unreliable metrics

### 5.3 Technical Debt Patterns

| Shortcut | Never Acceptable For | Why |
|----------|---------------------|-----|
| Joining EN/VI by label text | Production | Empty dual-language inventory |
| Skipping retry on ICD-10 endpoint | Production | Incomplete/non-reproducible inventory |
| Using ICD-10 as sole term source | Production | Missing 7+ entity types |
| Skipping medical fact validation | Production | Fabricated content in dataset |
| Evaluating fine-tune on synthetic test audio | Production | Invalid improvement claim |
| Computing DER without reference RTTM | Production | False precision |
| Using estimated speaker metadata as facts | Production | Fabricated demographic labels |
| Full-parameter PhoWhisper fine-tuning | Production | Catastrophic forgetting |
| Using Turbo TTS mode for medical terms | Production | Garbled English terms |

---

## 6. Key Findings & Insights

### 6.1 Cross-Cutting Insights

**1. The pipeline is only as strong as its weakest stage.**
The ICD-10 → Term → Coverage → Gap → Conversation → TTS → ASR chain means a bad EN/VI join (Pitfall 1) or incomplete term taxonomy (Pitfall 3) silently corrupts everything downstream. Early-stage validation is not optional — it is the only way to catch propagation errors.

**2. Vietnamese medical code-switching is a compounding complexity problem.**
Each complexity layer (Vietnamese tone marks, English medical terminology, code-switching within sentences, TTS pronunciation, ASR recognition) multiplies failure modes. The TTS→ASR round-trip check is not a nice-to-have; it is the only validation mechanism that catches the full stack of failures.

**3. Synthetic data is a tool, not a solution.**
The pipeline generates synthetic TTS audio to expand medical term coverage beyond what ViMedCSS provides. But synthetic data is fundamentally different from real medical speech (Pitfall 6). The ablation study (E0/E1/E2/E3) is the only mechanism that proves synthetic data actually helps — without it, the team is flying blind.

**4. Medical accuracy requires retrieval-augmented grounding, not prompting.**
LLM hallucination (Pitfall 4) in medical contexts is not a model quality issue — it is a fundamental architectural problem. Without RAG grounding each conversation turn in ICD codes, drug references, and procedure facts, the LLM produces fluent but wrong medical content. This must be built into the conversation generation architecture from the start.

**5. PhoWhisper fine-tuning without PEFT is a losing bet.**
Full-parameter fine-tuning risks catastrophic forgetting (Pitfall 7) and requires more GPU memory than most teams have. LoRA (via PEFT) with frozen lower encoder layers is the correct approach — it enables domain adaptation without erasing general Vietnamese ASR capability.

**6. The KCB ICD-10 endpoint is a reverse-engineered, unversioned, no-SLA dependency.**
Everything built on top of the ICD-10 inventory depends on this endpoint. The pipeline must treat it as an unreliable external service: cache aggressively, version responses, log every failure, and have a manual fallback for critical codes.

**7. Speaker metadata integrity is a sliding scale, not binary.**
The pipeline must distinguish `provided` (from dataset), `estimated` (from inference model with confidence), and `unknown` (no information). Reporting ASR metrics "by gender/region" without this distinction is a data integrity violation that produces fabricated demographic conclusions.

**8. DER evaluation on VietMed is a different problem than ASR evaluation.**
VietMed was designed for ASR, not diarization evaluation. Its speaker annotations are utterance-level, not turn-level. pyannote produces fine-grained segment boundaries. Comparing these directly inflates DER artificially (Pitfall 12). The team should not attempt DER computation without first creating a human-labeled RTTM subset.

**9. Code-switching quality is the pipeline's primary differentiator.**
The entire value proposition rests on correctly handling English medical terms embedded in Vietnamese sentences. TTS must pronounce "MRI", "HbA1c", "metformin" correctly within Vietnamese prosody. ASR must recognize them. If this fails, the pipeline is just another generic TTS/ASR evaluation tool.

**10. Vietnamese TTS tooling has matured significantly but licensing requires diligence.**
 VieNeu-TTS-v3-Turbo (2026) and PhoAudiobook (ACL 2025) represent state-of-the-art Vietnamese TTS. However, licenses vary: CC-BY-4.0 (viVoice), Research-only (PhoAudiobook), Apache 2.0 (VieNeu-TTS-140h). The team must verify each dataset's license before any downstream use.

---

## 7. Open Questions

### Must-Resolve Before Phase 2 Build

| # | Question | Owner | Priority | Blocker For |
|---|----------|-------|----------|-------------|
| O1 | Can the team access VietMed dataset? Under what license? | QA/Ethics | CRITICAL | FR4, FR11 |
| O2 | Is there a budget for OpenAI/Anthropic API credits? Which model tier? | PM | HIGH | FR5 |
| O3 | Is GPU compute available for PhoWhisper fine-tuning? What VRAM? | ASR Engineer | HIGH | FR11 |
| O4 | Who is the medical domain expert for 5–10% human review of conversations? | Research Lead | HIGH | FR5 |
| O5 | What is the approved dataset public license for the final release (Apache 2.0 vs CC-BY-4.0)? | QA/Ethics | HIGH | FR9, FR11 |
| O6 | Does the KCB ICD-10 endpoint support bulk queries, or must every code be queried individually? | Backend | MEDIUM | FR1 |
| O7 | Is there an existing Vietnamese medical lexicon (drug names, lab tests, procedures) with a compatible license? | Research Lead | MEDIUM | FR2 |

### Should-Resolve During Phase 2

| # | Question | Priority | Impact |
|---|----------|----------|--------|
| O8 | What is the minimum human review sampling rate for conversations? (PRD says 5–10%) | MEDIUM | Medical accuracy |
| O9 | Should the team use VietMed raw audio for fine-tuning, synthetic TTS audio for augmentation, or both? | MEDIUM | FR11 design |
| O10 | What is the acceptable CS-WER target for PhoWhisper on medical terms? | MEDIUM | FR11 success criteria |
| O11 | Should the team create a human-labeled RTTM subset for VietMed-test for accurate DER evaluation? | MEDIUM | FR11 reporting |
| O12 | What is the maximum synthetic-to-real ratio in fine-tuning? (20–30% per Pitfall 6) | MEDIUM | FR11 training design |
| O13 | Which TTS quality mode (Turbo/Standard/GPU) should be used for medical term pronunciation validation? | MEDIUM | FR7 evaluation |

### Nice-to-Have

| # | Question | Priority | Impact |
|---|----------|----------|--------|
| O14 | Can the team integrate VN Core FHIR (`vn-icd10-cs`, `vn-snomed-subset-cs`) as an authoritative source? | LOW | FR1 data quality |
| O15 | Should the team implement metric-driven donor dataset selection for Stage 1 fine-tuning (Fréchet DeepSpeech Distance)? | LOW | FR11 training quality |
| O16 | What is the plan for production-scale PhoWhisper fine-tuning if Phase 2 validates the approach? | LOW | v2 roadmap |

---

## 8. Confidence Summary

| Research Area | Confidence | Rationale | Key Gaps |
|--------------|------------|-----------|----------|
| **Technology Stack** | MEDIUM-HIGH | Context7-verified for OpenAI SDK, Anthropic SDK, PEFT, pyannote, WhisperX, PhoWhisper | Vietnamese TTS tooling (VieNeu-TTS, vietnormalizer) from web search only — verify before finalizing |
| **Feature Landscape** | HIGH | Verified against official sources (VN Core FHIR, PhoWhisper GitHub, ViMedCSS LREC 2026 paper) | Some dataset licenses not independently verified |
| **System Architecture** | HIGH | Follows existing codebase patterns; all proposed modules are straightforward extensions | CLI subcommand design not stress-tested with real users |
| **Critical Pitfalls** | MEDIUM-HIGH | Based on documented failure modes from academic papers and industry reports | 12 pitfalls identified but some (e.g., TTS mispronunciation, LLM hallucination) require empirical validation in the actual pipeline |
| **Integration Points** | MEDIUM-HIGH | All external service patterns verified; KCB endpoint documented with live curl examples | ICD-10 endpoint is unversioned — response schema could change without notice |
| **Overall** | **MEDIUM-HIGH** | Strong foundation for Phase 2 build; confidence highest for FR1–FR3 (foundational), lowest for FR5 (LLM hallucination) and FR11 (fine-tuning + diarization) | — |

---

## 9. Verification Checklist

This 21-item checklist condenses the prevention and recovery strategies from all 12 pitfalls. The team should run through this list at the end of each phase.

### FR1 — ICD-10 Ingestion

- [ ] **V1.1:** Manual spot-check of 10 random codes confirms dual-language join works by code, not label. Verify `label_vi` is populated for all 10 codes.
- [ ] **V1.2:** Verify raw cached responses exist for every code in `data/raw/icd10/cache/` with `fetched_at` timestamps.
- [ ] **V1.3:** Ingestion error log exists and shows <10% failure rate. No code silently failed.

### FR2 — Medical Term Inventory

- [ ] **V2.1:** Term inventory covers all 9 entity types (disease, drug, lab_test, procedure, abbreviation, hormone, biomarker, device, unit, dosage). Count rows per `entity_type`; no type has zero records.
- [ ] **V2.2:** All non-ICD terms are traced to a named source with license verification. No `llm_generated_candidate` terms are marked `review_status: verified`.

### FR5 — LLM Conversation Generation

- [ ] **V5.1:** Every conversation in `doctor_patient_conversations.jsonl` has a `icd10_code` and `required_terms` traceable back to FR3 gap analysis.
- [ ] **V5.2:** Conversation validation log captures JSON schema errors, medical fact errors, and safety flag triggers in separate categories. No category is empty.
- [ ] **V5.3:** Medical domain expert has reviewed ≥5% of generated conversations. Review queue exists and has been acted upon.

### FR7 — TTS Model Research

- [ ] **V7.1:** TTS model has been tested on English medical terms in Vietnamese sentences (not just Vietnamese text). Per-term results exist in `tts_term_pronunciation_test.csv`.
- [ ] **V7.2:** English term failure rate is documented per model. Turbo mode has NOT been used for medical terms.

### FR8 — Voice Pool

- [ ] **V8.1:** All voice profile cards have `*_status: provided|estimated|unknown` on every speaker attribute. No attribute is unlabeled.
- [ ] **V8.2:** All datasets in the voice pool have license verification documented in `voice_profile_cards.jsonl`.

### FR9 — Synthetic TTS

- [ ] **V9.1:** Round-trip ASR check flags per-term failures (not just aggregate WER). Failed terms are logged in `roundtrip_asr_check.jsonl`.
- [ ] **V9.2:** Failed pronunciation samples are excluded from training set. Exclusion count is documented.

### FR10 — ASR Evaluation

- [ ] **V10.1:** Test manifest preflight check passes — no row with `source: synthetic` in the evaluation manifest.
- [ ] **V10.2:** Every evaluation run includes E0 zero-shot baseline evaluated on the same test set.
- [ ] **V10.3:** WER improvements are reported with absolute change, relative change, and sample count.

### FR11 — PhoWhisper Fine-tuning + Diarization

- [ ] **V11.1:** PEFT (LoRA/adapter) is confirmed in training config — no full-parameter fine-tuning.
- [ ] **V11.2:** Ablation study (E0/E1/E2/E3) compares all four conditions on the same real test set. Results are not cherry-picked.
- [ ] **V11.3:** Reference RTTM file exists before any DER/JER is reported. If absent, only qualitative metrics are reported.
- [ ] **V11.4:** All pyannote output files are clearly named as `*_hypothesis.rttm` — never as ground truth.

### Privacy & Reporting

- [ ] **V12.1:** VietMed audio access has been approved by QA/Ethics before any download or processing.
- [ ] **V12.2:** All reports separate `paper_reported`, `hf_reported`, and `local_verified` metrics. No claim mixes sources without attribution.
- [ ] **V12.3:** Every artifact has a `source` field (e.g., `source: vietmed`, `source: synthetic`, `source: vimedcss`). No artifact has an empty `source` field.

---

*Research synthesis completed: VietMedVoice Phase 2 Enhancement v1.1*  
*Synthesized from: STACK.md, FEATURES.md, ARCHITECTURE.md, PITFALLS.md, STATE.md, icd10-api-kcb.md*
