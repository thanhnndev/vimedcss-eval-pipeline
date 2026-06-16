# Architecture

**Analysis Date:** 2026-06-16

## Pattern Overview

**Overall:** CLI Pipeline Application (Layered Architecture).

**Key Characteristics:**
- CLI-driven command execution matching different pipeline phases.
- Stateless execution model where inputs are read from local storage and outputs are written as structured files.
- Decoupled modules organized by functional tasks (Acquisition, Auditing, Taxonomy/Term Analysis, ASR Baseline, Evaluation Metrics, Reporting).

## Layers

**CLI / Entry Layer:**
- Purpose: Parse command line arguments, load configuration, and orchestrate service executions.
- Contains: `src/cli.py`
- Depends on: Service Layer, Shared Layer.
- Used by: User / `Makefile` command commands.

**Service Layer:**
- Purpose: Core pipeline logic for specific phases.
- Contains:
  - `src/hf_client/` - Downloads metadata/audio from Hugging Face and records acquisition manifests.
  - `src/audit/` - Normalizes metadata column schemas and audits data quality/stats.
  - `src/terms/` (planned) - Extracts, normalizes, and filters code-switching medical terms.
  - `src/llm/` (planned) - Performs taxonomy classification of terms using OpenAI API.
  - `src/asr/` (planned) - Runs ASR models (e.g., Whisper) on downloaded audio segments.
  - `src/metrics/` (planned) - Computes evaluation metrics (WER, CER, Term Recall/Missing rates).
  - `src/reports/` (planned) - Generates final Vietnamese markdown reports from audit/evaluation statistics.
- Depends on: Shared Layer.
- Used by: CLI / Entry Layer.

**Shared Layer:**
- Purpose: Common infrastructure utilities like configuration parsing and logging.
- Contains:
  - `src/shared/config.py` - Configuration loading from YAML configs.
  - `src/shared/logging.py` - Standard logging wrapper configurations.
- Depends on: Standard/external python packages only.
- Used by: All layers.

## Data Flow

**Download Metadata Flow:**
1. User calls `make download` or python command `src/cli.py download-metadata`.
2. `src/cli.py` initializes `AppConfig` and instantiates `HFDatasetClient`.
3. `HFDatasetClient` checks remote dataset info, lists repository files, filters metadata CSVs.
4. Client downloads CSV metadata files to `data/raw/vimedcss/ViMedCSS-Metadata/`.
5. Client writes file manifest to `outputs/audit/hf_file_manifest.json` and appends logs to `download_log.jsonl`.

**Metadata Audit Flow:**
1. User calls `make audit` or python command `src/cli.py audit-metadata`.
2. `src/cli.py` initializes `MetadataAuditor`.
3. `MetadataAuditor` locates the metadata CSV files for train, validation, test, and hard splits.
4. Auditor reads CSV files via pandas and maps their columns to standard schema fields (e.g., `Topic` -> `topic`, `duration_seconds` -> `duration`).
5. Auditor calculates global dataset stats, split stats, topic stats, duration distributions, and quality issues (e.g., duplicate IDs, missing transcripts).
6. Auditor exports statistics to `outputs/audit/` and generates the Vietnamese `metadata_schema_report.md`.

**State Management:**
- The pipeline is stateless. It reads state from inputs (e.g., config files, data directory, downloaded metadata) and persists outputs to files. It does not rely on an in-memory database or persistent servers between executions.

## Key Abstractions

**AppConfig (`src/shared/config.py`):**
- Purpose: Dynamic YAML configuration loader. Instantiates dictionary access structures for dataset, taxonomy, llm, asr, and report parameters.
- Pattern: Service configuration container.

**HFDatasetClient (`src/hf_client/download.py`):**
- Purpose: Interaction client wrapping Hugging Face Hub APIs.
- Pattern: Repository facade.

**MetadataAuditor (`src/audit/auditor.py`):**
- Purpose: Data schema mapping, statistics aggregator, and quality validator.
- Pattern: Auditor engine pattern.

## Entry Points

**CLI Command Interface:**
- Location: `src/cli.py`
- Triggers: CLI commands run via bash or Makefile targets.
- Responsibilities: Parses commands (`download-metadata`, `audit-metadata`), sets up config, runs corresponding auditor/client functions.

## Error Handling

**Strategy:** Fail-fast with logging.
- Exceptions thrown at service layers are propagated to the CLI layer.
- `src/cli.py` catches top-level errors, logs the stack/message via the setup logger, and exits with non-zero exit status (`sys.exit(1)`).

## Cross-Cutting Concerns

**Logging:**
- Standard Python `logging` module configured in `src/shared/logging.py`.
- Formatted as `%(asctime)s - %(name)s - %(levelname)s - %(message)s` to console.

**Configuration:**
- Dynamic schema mapping in `MetadataAuditor`. Matches columns by lowercase comparisons against configured lists of fallbacks (e.g. mapping `Topic` to `topic`).

---

*Architecture analysis: 2026-06-16*
*Update when major patterns change*
