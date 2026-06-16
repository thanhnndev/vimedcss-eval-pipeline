# Technology Stack

**Analysis Date:** 2026-06-16

## Languages

**Primary:**
- Python (tested on Python 3.14 / 3.8+) - All application code and tests.

**Secondary:**
- YAML - Configuration files.
- Makefile - Build, installation, test, and utility execution commands.
- Markdown - Documentation and reports.

## Runtime

**Environment:**
- Python virtual environment (`.venv`) on Linux.

**Package Manager:**
- pip - Package installer for Python, referencing `requirements.txt`.
- No lockfile present.

## Frameworks

**Core:**
- None (vanilla Python package).

**Testing:**
- pytest >= 7.0.0 - Test runner for unit tests.

**Build/Dev:**
- Makefile - Command orchestration for setup, downloads, audits, and testing.

## Key Dependencies

**Critical:**
- `pandas` >= 2.0.0 - Loading, parsing, and exporting tabular metadata.
- `huggingface_hub` >= 0.20.0 - Interacting with Hugging Face Hub (listing, downloading files).
- `pydantic` >= 2.0 - Schema validation for LLM inputs/outputs and metadata.
- `openai` >= 1.0.0 - LLM interaction for medical term classification.
- `jiwer` >= 3.0.0 - Word Error Rate (WER) and Character Error Rate (CER) metric calculations.
- `pyyaml` >= 6.0 - Parsing YAML configuration files.

**Infrastructure:**
- `numpy` >= 1.24.0 - Numerical processing and stats calculations.
- `pyarrow` >= 12.0.0 - Underlying Parquet format support for pandas and HF downloads.

## Configuration

**Environment:**
- None required for local CLI, but LLM classifier requires `OPENAI_API_KEY` for OpenAI API calls.

**Build/Run:**
- `configs/dataset.yaml` - Dataset repository, splits, and schema column mapping.
- `configs/taxonomy.yaml` - Term classification frequency thresholds and validation rules.
- `configs/llm.yaml` - LLM provider, model model, structured output, and batch configuration.
- `configs/asr.yaml` - ASR baseline model selection, normalizations, and splits to evaluate.
- `configs/report.yaml` - Language, format, and destination directory configuration for report generation.

## Platform Requirements

**Development:**
- Linux (user environment). Requires internet connectivity to reach Hugging Face Hub and OpenAI API.

**Production:**
- Standard Python environment running the package CLI commands.

---

*Stack analysis: 2026-06-16*
*Update after major dependency changes*
