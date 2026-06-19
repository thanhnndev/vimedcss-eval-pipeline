# Stack Research

**Domain:** Vietnamese Medical Code-Switching Speech Pipeline (ASR/TTS/LLM)
**Project:** VietMedVoice Phase 2 Enhancement v1.1
**Researched:** 2026-06-19
**Confidence:** MEDIUM-HIGH

> **Scope Note:** This stack covers ONLY the v1.1 Phase 2 additions: ICD-10 ingestion, medical term inventory, LLM conversation generation, TTS, voice pool, and ASR/diarization evaluation. Existing validated pipeline (ViMedCSS metadata, CS term extraction, LLM classification) uses established tooling from v1.0.

---

## Recommended Stack

### Core LLM API Clients

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|----------------|
| **openai** | `>=1.68.0` | LLM conversation generation via `gpt-4o`, `gpt-4o-mini`, `o4-mini` | OpenAI SDK provides `chat.completions.parse()` for Pydantic-validated JSON output, streaming events, and structured outputs. Use `response_format=MathResponse` pattern for conversation JSONL generation. Streaming via `async with client.chat.completions.stream()` context manager. |
| **anthropic** | `>=0.40.0` | Claude 3.5/3.7 for higher-quality medical text, structured output | Anthropic SDK supports `messages.stream()` with `output_format=PydanticModel` for streaming JSON parsing. Better for nuanced medical dialogue. Use `claude-3-5-sonnet-latest` or `claude-sonnet-4-5`. |
| **huggingface_hub** | `>=0.26.0` | Access PhoWhisper, viVoice, PhoAudiobook datasets | Unified HF API for model/dataset downloads with progress hooks. Use for PhoWhisper model loading and voice dataset metadata. |

### ASR / Fine-tuning

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|----------------|
| **transformers** | `>=4.46.0` | PhoWhisper model loading, pipeline API | Native support for PhoWhisper via `pipeline("automatic-speech-recognition", model="vinai/PhoWhisper-small")`. Fine-tuning via `WhisperForConditionalGeneration`. Supports `AutoProcessor` for audio/text. |
| **peft** | `>=0.14.0` | LoRA/QLORA fine-tuning of PhoWhisper | PEFT provides `get_peft_model()` + `LoraConfig` for parameter-efficient fine-tuning. Use with `BitsAndBytesConfig(load_in_8bit=True)` for VRAM reduction. LoRA targets: `q_proj, v_proj, k_proj, o_proj`. Merge with `merge_and_unload()` for inference. |
| **accelerate** | `>=1.0.0` | Distributed training, multi-GPU | Required for PhoWhisper fine-tuning at scale. Use `accelerate launch` for training scripts. |
| **bitsandbytes** | `>=0.44.0` | 8-bit/4-bit quantization | Enables `load_in_8bit=True` for Whisper-large fine-tuning on consumer GPUs. Use `bnb_config = BitsAndBytesConfig(load_in_8bit=True)`. |
| **vinai/PhoWhisper-small** | `244M params` | Vietnamese ASR base model | State-of-the-art Vietnamese ASR from VinAI. Fine-tuned from Whisper-small on 844h diverse Vietnamese accents. WER: 11.08% (CMV-Vi), 6.33% (VIVOS). Use as fine-tuning base for medical domain adaptation. |
| **vinai/PhoWhisper-medium** | `769M params` | Higher-accuracy Vietnamese ASR | If GPU budget allows (24GB+ VRAM). WER: 8.27% (CMV-Vi). Fallback if small underperforms on medical terms. |

### Speaker Diarization

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|----------------|
| **pyannote.audio** | `>=3.1.0` | Speaker diarization pipeline | `Pipeline.from_pretrained("pyannote/speaker-diarization-3.1")` for turn-level speaker segmentation. Output is `pyannote.core.Annotation`. Supports `num_speakers=2` hint for doctor-patient. Requires HF token acceptance. Community variant `pyannote/speaker-diarization-community-1` for open access. |
| **whisperx** | `>=3.5.0` | Word-level timestamps + speaker attribution | Complete pipeline: `transcribe()` → `align()` → `assign_word_speakers()`. Leverages faster-whisper + wav2vec2 alignment + pyannote diarization. Produces `segments` with `words` array, each with `speaker` label. Key for doctor-patient turn analysis. |

### TTS (Vietnamese + English Code-Switching)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|----------------|
| **VieNeu-TTS-v3-Turbo** | `2026` | Primary Vietnamese TTS with code-switching | 48kHz high-fidelity, instant voice cloning (3-5s reference), built-in En-Vi code-switching via `sea-g2p` phonemizer. Trained on 10,000h bilingual data. Pure PyTorch, runs on GPU/CPU. **Best choice for medical CS content.** |
| **VieNeu-TTS-v2** | `2025` | Proven stable Vietnamese TTS | 24kHz, Podcast/Conversation mode for multi-speaker dialogue. GGUF variants for CPU inference. Good fallback if v3 has issues. |
| **Coqui XTTS-v2** | `>=2.0.2` | Zero-shot multilingual TTS | Vietnamese supported via community checkpoints (`thivux/xtts-v2-vietnamese`). ACL 2025 paper shows XTTS-v2 outperforms VALL-E/VoiceCraft on PhoAudiobook. 24kHz output. |
| **vietnormalizer** | `>=1.0.0` | Vietnamese text preprocessing for TTS | **Critical dependency.** Converts numbers, dates, acronyms, medical abbreviations, and foreign loanwords to pronounceable Vietnamese forms. Rule-based, zero-dependency, MIT license. Use before ANY TTS input to improve English term pronunciation. |

### HTML / API Scraping (ICD-10 Ingestion)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|----------------|
| **httpx** | `>=0.28.0` | Async HTTP client for ICD-10 API | Async support for concurrent ICD-10 queries. `httpx.AsyncClient` with retry logic, timeout, and logging. Handles JSON responses + raw HTML from KCB endpoint. |
| **beautifulsoup4** | `>=4.12.0` | HTML parsing for ICD-10 hierarchy | Parse `html` field from API response to extract `chapter`, `section`, `type`, `disease` hierarchy. Use `lxml` parser for speed. |
| **lxml** | `>=5.0.0` | Fast XML/HTML parser backend | Backend for BeautifulSoup. Required for parsing complex nested HTML from ICD-10 endpoint. |

### Data Processing

| Technology | Version | Purpose | When to Use |
|------------|---------|---------|-------------|
| **datasets** | `>=3.2.0` | HuggingFace dataset loading, streaming | Load ViMedCSS, viVoice, PhoAudiobook manifests. `load_dataset("tensorxt/ViMedCSS")`. Use streaming mode for large datasets. |
| **pandas** | `>=2.2.0` | CSV/JSONL tabular operations | ICD-10 CSV export, term inventory, coverage matrices. Use `pyarrow` backend for speed. |
| **jiwer** | `>=3.0.0` | WER/CER computation | Standard for ASR evaluation. `compute_measures(reference, hypothesis)` returns WER, CER, SER. |
| **pydantic** | `>=2.9.0` | JSON schema validation | Validate conversation JSON, ICD-10 records, voice profile cards. Use with `model_validator` for complex nested schemas. |

### Voice Pool / Dataset Access

| Resource | License | Purpose | Access |
|----------|---------|---------|--------|
| **viVoice** (capleaf/viVoice) | CC-BY-4.0 | 1,017h Vietnamese TTS speech, 243 speakers | HF dataset. Speaker metadata: `gender`, `age` (estimated), `region`. Check license before use. |
| **PhoAudiobook** (thivux/phoaudiobook) | Research-only | 941h high-quality Vietnamese, 710 speakers, ACL 2025 | HF dataset. Optimized for zero-shot TTS. IPA phonemized. |
| **VieNeu-TTS-140h** (pnnbao-ump) | Apache 2.0 | 140.7h, 193 speakers, phonemized transcripts | HF dataset. Clean WAV 24kHz. Explicit speaker gender metadata. **Recommended for voice pool.** |
| **VietSuperSpeech** (thanhnew2001/VietSuperSpeech) | Open | 267h conversational Vietnamese, ~27k speakers | HF dataset. For ASR fine-tuning (not TTS primary). Pseudo-labeled transcripts. |

---

## Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `python-dotenv` | `>=1.0.0` | Environment variable management | Store `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `HF_TOKEN`. Never commit keys. |
| `tenacity` | `>=8.4.0` | Retry logic for API calls | Wrap ICD-10 endpoint calls with exponential backoff. |
| `tqdm` | `>=4.66.0` | Progress bars | Wrap generation loops for conversation/TTS generation. |
| `loguru` | `>=0.7.0` | Structured logging | Replace `print()` for audit trails, error tracking. |
| `pyyaml` | `>=6.0.0` | Config file management | Store ICD-10 ingestion config, LLM generation prompts, TTS model configs. |
| `librosa` | `>=0.10.0` | Audio loading, preprocessing | Load WAV for ASR/TTS. `librosa.load(path, sr=16000)` for ASR input. |
| `soundfile` | `>=0.12.0` | Audio I/O | Save/load WAV files for TTS output. |

---

## Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| **CUDA 12.x + cuDNN 8.9+** | GPU acceleration for PhoWhisper fine-tuning, TTS | PhoWhisper-small fine-tuning requires ~16GB VRAM with 8-bit. PhoWhisper-medium requires ~24GB. |
| **Python 3.10+** | Runtime | 3.12 recommended for async performance. |
| **uv** | Package manager | Fast, modern. Use `uv pip install` or `uv sync`. |
| **Weights & Biases** | Experiment tracking | Optional for fine-tuning logging. Track WER by step, learning rate, batch size. |
| **Docker** | Reproducible environments | Containerize ICD-10 ingestion, TTS generation, ASR evaluation. Avoid dependency drift. |

---

## Installation

```bash
# Core LLM & API clients
uv pip install openai>=1.68.0 anthropic>=0.40.0 httpx>=0.28.0

# ASR / Fine-tuning
uv pip install transformers>=4.46.0 peft>=0.14.0 accelerate>=1.0.0 bitsandbytes>=0.44.0
uv pip install jiwer>=3.0.0 librosa>=0.10.0 soundfile>=0.12.0

# Diarization & Alignment
uv pip install pyannote.audio>=3.1.0 whisperx>=3.5.0

# TTS (Vietnamese-focused)
uv pip install vietnormalizer>=1.0.0  # Critical for medical term pronunciation

# Data processing
uv pip install datasets>=3.2.0 pandas>=2.2.0 pydantic>=2.9.0 pyyaml>=6.0.0
uv pip install beautifulsoup4>=4.12.0 lxml>=5.0.0

# Utilities
uv pip install python-dotenv>=1.0.0 tenacity>=8.4.0 tqdm>=4.66.0 loguru>=0.7.0
```

```python
# PhoWhisper inference (existing v1.0 pattern)
from transformers import pipeline
transcriber = pipeline("automatic-speech-recognition", model="vinai/PhoWhisper-small")
output = transcriber(audio_16kHz_path)['text']

# LoRA fine-tuning setup (new v1.1)
from peft import LoraConfig, get_peft_model
from transformers import WhisperForConditionalGeneration, BitsAndBytesConfig

config = BitsAndBytesConfig(load_in_8bit=True)
base_model = WhisperForConditionalGeneration.from_pretrained(
    "vinai/PhoWhisper-small",
    quantization_config=config,
    device_map="auto"
)
lora_config = LoraConfig(
    r=32,
    lora_alpha=64,
    target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
    lora_dropout=0.05,
    bias="none",
    task_type="SEQ_2_SEQ_LM"
)
model = get_peft_model(base_model, lora_config)

# OpenAI structured JSON output (conversation generation)
from pydantic import BaseModel
from openai import OpenAI

class ConversationTurn(BaseModel):
    turn_id: int
    speaker_role: str
    text: str
    medical_terms: list[str]
    language_mix: str

client = OpenAI()
completion = client.chat.completions.parse(
    model="gpt-4o-2024-08-06",
    messages=[...],
    response_format=ConversationTurn,
)
```

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|------------------------|
| **openai** (gpt-4o-mini) | **claude-3-5-sonnet** | Claude if medical consistency is critical (higher quality, slower, more expensive). OpenAI for cost-efficient batch generation. |
| **vinai/PhoWhisper-small** | **openai/whisper-large-v3-turbo** | Whisper-large if PhoWhisper doesn't cover specific accent region. PhoWhisper is better-tuned for Vietnamese. |
| **VieNeu-TTS-v3-Turbo** | **Coqui XTTS-v2** | XTTS if zero-shot voice cloning across languages is primary need. VieNeu-TTS for Vietnamese-native quality + code-switching. |
| **pyannote 3.1** | **whisperx diarization** | WhisperX built-in diarization is simpler but less accurate. pyannote 3.1 for production-grade DER < 10%. |
| **httpx async** | **aiohttp** | httpx is cleaner for mixed sync/async. aiohttp if only pure async needed. |
| **vietnormalizer** | **sea-g2p** (included in VieNeu-TTS) | sea-g2p is already inside VieNeu-TTS. vietnormalizer adds acronym expansion + currency/dates. Use both. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **Google Cloud TTS** | English-centric, poor Vietnamese tonality, expensive API | VieNeu-TTS-v3-Turbo (local) or Soniox (Vietnamese-optimized API) |
| **Microsoft Azure Speech** | Commercial license, expensive, no specific Vietnamese advantage | VieNeu-TTS for local, OpenAI TTS for API fallback |
| **Standard Whisper (not PhoWhisper)** | PhoWhisper is fine-tuned specifically for Vietnamese accents, achieves 30-40% lower WER | PhoWhisper-small/medium for Vietnamese ASR |
| **Raw `requests` library** | No async support, blocking calls for bulk ICD-10 queries | `httpx.AsyncClient` with retry + concurrency |
| **Manual HTML regex parsing** | Fragile, breaks on HTML changes | BeautifulSoup + lxml for robust parsing |
| **Fake JSON from LLM without validation** | High invalid-JSON rate, requires post-hoc patching | Use `response_format=PydanticModel` (OpenAI) or `output_format=Model` (Anthropic) |
| **Full fine-tune of PhoWhisper-large** | 1.55B params requires 40GB+ VRAM, diminishing returns | PhoWhisper-small (244M) + LoRA for domain adaptation |
| **Public YouTube audio scraping** | License/PHI issues, out of scope per PRD | Only use licensed datasets: viVoice, PhoAudiobook, VietMed (if license permits) |

---

## Stack Patterns by Variant

**If GPU VRAM < 16GB:**
- Use PhoWhisper-small + LoRA (8-bit) for fine-tuning
- Use VieNeu-TTS-v2 GGUF Q4 for CPU TTS inference
- Batch ASR inference with `batch_size=4`

**If GPU VRAM >= 24GB:**
- PhoWhisper-medium + LoRA for higher accuracy
- VieNeu-TTS-v3-Turbo PyTorch for best TTS quality
- Larger batch sizes for faster fine-tuning

**If API budget is constrained:**
- Use `gpt-4o-mini` for conversation generation (80% cheaper than gpt-4o)
- Use OpenAI structured output to avoid retry wasted tokens
- Cache ICD-10 responses locally (no need to re-query)

**If medical term quality is critical:**
- Use `claude-3-5-sonnet` for conversation generation (better medical consistency)
- Add `vietnormalizer` preprocessing before ALL TTS calls
- Use `sea-g2p` phonemizer explicitly for edge cases

**If real-time TTS needed:**
- Use VieNeu-TTS GGUF Q4 on CPU (streaming supported)
- Avoid VieNeu-TTS PyTorch (not streaming-capable)

---

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `transformers>=4.46.0` | `peft>=0.14.0` | PEFT uses `model.generate()` which requires transformers 4.40+ |
| `peft>=0.14.0` | `bitsandbytes>=0.44.0` | 8-bit requires BNB installed separately |
| `whisperx>=3.5.0` | `pyannote.audio>=3.1.0` | WhisperX uses pyannote internally for diarization |
| `pyannote.audio>=3.1.0` | `torch>=2.0.0` | Requires PyTorch. GPU support requires CUDA 12.x |
| ` VieNeu-TTS` (PyTorch) | `torch>=2.0.0`, `CUDA 12.x` | GPU inference via PyTorch. CPU fallback supported |
| `openai>=1.68.0` | Python 3.8+ | SDK uses modern async patterns |
| `anthropic>=0.40.0` | Python 3.9+ | Streaming API requires 3.9+ |

---

## Integration Points with Existing v1.0 Pipeline

The v1.1 stack additions integrate at these points:

| Existing v1.0 Module | v1.1 Integration |
|---------------------|------------------|
| `data/vimedcss/metadata.csv` | FR3: ViMedCSS coverage audit reads CS terms, matches against ICD-10 + term inventory |
| `src/llm_classification/` | FR5: Reuse LLM client pattern for conversation generation with structured JSON output |
| `src/asr_evaluation/` | FR10-11: Extend WER/CER to include CS-WER, term recall. Add PhoWhisper fine-tuning |
| `reports/` (Vietnamese) | FR6: Add LLM cost analysis, TTS quality report, ASR metrics by domain |

**Key file contracts (do not break):**
- All outputs must be JSONL or CSV with explicit schema
- Every artifact must have `source` provenance field
- Synthetic data must have `synthetic=True` label, never mixed with real audio

---

## Sources

- **OpenAI SDK**: `/openai/openai-python` — Context7 ID confirmed, streaming + structured output patterns verified
- **Anthropic SDK**: `/anthropics/anthropic-sdk-python` — Context7 ID confirmed, streaming + output_format patterns verified
- **PEFT LoRA**: `/huggingface/peft` — Context7 ID confirmed, Whisper LoRA examples verified
- **pyannote.audio**: `/pyannote/pyannote-audio` — Context7 ID confirmed, diarization pipeline code verified
- **WhisperX**: `/m-bain/whisperx` — Context7 ID confirmed, complete pipeline with diarization verified
- **PhoWhisper**: `/vinairesearch/phowhisper` — Context7 ID confirmed, WER benchmarks from paper
- **VieNeu-TTS-v3-Turbo**: Web search — 2026 release, 48kHz, code-switching support confirmed
- **vietnormalizer**: arxiv.org/html/2603.04145 — 2026 paper, zero-dependency Vietnamese normalization
- **PhoAudiobook**: aclanthology.org/2025.acl-short.81.pdf — ACL 2025 paper, 941h dataset, XTTS-v2 evaluation
- **viVoice**: Web search — 1,017h, CC-BY-4.0, 243 speakers confirmed

---

## Open Questions (Need Team Decision)

| Question | Owner | Priority |
|----------|-------|----------|
| Use VietMed raw audio for fine-tuning? | QA/Ethics | High |
| Buy API credits for OpenAI/Anthropic? | PM | High |
| GPU budget for PhoWhisper-medium fine-tuning? | ASR Engineer | Medium |
| Human review sampling rate for conversations? | Research Lead | Medium |
| Dataset public license choice (Apache 2.0 vs CC-BY-4.0)? | QA/Ethics | High |

---

*Stack research for: VietMedVoice Phase 2 Enhancement v1.1*
*Researched: 2026-06-19*
*Confidence: MEDIUM-HIGH (Context7 verified for OpenAI/Anthropic/PEFT/pyannote; Web search for Vietnamese TTS/vision datasets — verify before finalizing)*
