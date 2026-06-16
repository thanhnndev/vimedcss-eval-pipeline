# Stack Research

**Domain:** Medical Code-Switching ASR & Corpus Evaluation
**Researched:** 2026-06-16
**Confidence:** HIGH

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.10+ | Primary runtime environment | Standard for data analysis, machine learning, and AI pipelines. |
| Hugging Face Hub | >= 0.20.0 | Remote dataset downloads and manifest tracking | Official hosting platform of the `tensorxt/ViMedCSS` dataset. |
| pandas | >= 2.0.0 | Tabular metadata manipulation | Industry standard for data auditing and loading CSV metadata. |
| OpenAI API | >= 1.0.0 | LLM-based term classification | Structured JSON output capability with high classification accuracy (via gpt-4o/gpt-5-mini equivalent). |
| jiwer | >= 3.0.0 | ASR metric computations | Standard library for computing WER (Word Error Rate) and CER (Character Error Rate). |
| faster-whisper | >= 1.0.0 | ASR Baseline model runner | Re-implementation of Whisper using CTranslate2, which is up to 4x faster and uses less memory. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pydantic | >= 2.0 | Schema validation | Validating LLM outputs and config schemas. |
| PyYAML | >= 6.0 | YAML config parsing | Parsing dataset, llm, taxonomy, and asr configurations. |
| librosa | >= 0.10.0 | Audio processing and duration validation | Validating audio sample rates, channels, and integrity. |
| soundfile | >= 0.12.0 | Audio reading | Reading raw wav/mp3 metadata for verification. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| pytest | Unit testing framework | Test files under `tests/` to verify normalizer and taxomony. |
| Makefile | Build and CLI command runner | Command shortcut manager for download, audit, test, and run. |

## Installation

```bash
# Core dependencies
pip install pandas huggingface_hub openai jiwer faster-whisper pydantic pyyaml

# Supporting libraries
pip install librosa soundfile

# Dev dependencies
pip install pytest
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| `openai` API | Custom Local LLM (e.g., Llama-3-8B) | When data privacy is absolute, or API costs are a constraint. |
| `faster-whisper` | Hugging Face `transformers` Whisper | When running on platforms without CTranslate2 support or doing complex fine-tuning. |
| `jiwer` | Custom WER implementation | Only if alignment visualization requires custom character alignment mapping rules. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Outdated Python ASR libraries (e.g., SpeechRecognition) | Lack of support for modern Transformer baselines like Whisper and complex multilingual decoders. | `faster-whisper` |
| Manual regex-based term extractors | Too brittle for spelling variants, abbreviations, or list formatting. | Structured Pydantic validation + LLM post-processing. |

## Stack Patterns by Variant

**If GPU is available:**
- Use `faster-whisper` on GPU with `float16` or `int8_float16` precision.
- Because it speeds up ASR baseline decoding by an order of magnitude.

**If CPU-only (Local Laptop):**
- Use `faster-whisper` with `int8` quantization.
- Because it minimizes RAM usage and avoids OOM crashes during baseline runs.

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `pydantic` >= 2.0 | `openai` >= 1.0.0 | OpenAI structured output utilizes Pydantic schemas. |
| `pandas` >= 2.0 | `pyarrow` >= 12.0.0 | Fast CSV parsing backend. |

## Sources

- `tensorxt/ViMedCSS` Dataset Card — Hugging Face
- OpenAI Platform Reference — Structured Outputs Guide
- faster-whisper GitHub docs — System constraints

---
*Stack research for: ViMedCSS Evaluation*
*Researched: 2026-06-16*
