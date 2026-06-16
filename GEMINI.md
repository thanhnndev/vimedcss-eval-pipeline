<!-- GSD:project-start source:PROJECT.md -->
## Project

**ViMedCSS Term Coverage & ASR Code-Switching Evaluation Pipeline**

ViMedCSS Term Coverage & ASR Code-Switching Evaluation Pipeline is a research tool designed to analyze medical term coverage and evaluate ASR baseline performance on English/Vietnamese code-switching dataset `tensorxt/ViMedCSS`. It is used by researchers to identify ASR failures on code-switching terms and plan the dataset design for the subsequent VietMedVoice project.

**Core Value:** Accurate, traceable medical term coverage analysis and ASR error taxonomy for English/Vietnamese code-switching data to guide future dataset construction.

### Constraints

- **Data Integrity**: No fabricated data; separate paper-reported, hf-reported, local-verified, and LLM-inferred metrics.
- **LLM Safety**: Do not treat LLM classification as absolute ground truth; include confidence and review flags.
- **Language**: Final report must be in Vietnamese.
- **Testing**: Every pipeline must support a subset/smoke test mode.
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- Python (tested on Python 3.14 / 3.8+) - All application code and tests.
- YAML - Configuration files.
- Makefile - Build, installation, test, and utility execution commands.
- Markdown - Documentation and reports.
## Runtime
- Python virtual environment (`.venv`) on Linux.
- pip - Package installer for Python, referencing `requirements.txt`.
- No lockfile present.
## Frameworks
- None (vanilla Python package).
- pytest >= 7.0.0 - Test runner for unit tests.
- Makefile - Command orchestration for setup, downloads, audits, and testing.
## Key Dependencies
- `pandas` >= 2.0.0 - Loading, parsing, and exporting tabular metadata.
- `huggingface_hub` >= 0.20.0 - Interacting with Hugging Face Hub (listing, downloading files).
- `pydantic` >= 2.0 - Schema validation for LLM inputs/outputs and metadata.
- `openai` >= 1.0.0 - LLM interaction for medical term classification.
- `jiwer` >= 3.0.0 - Word Error Rate (WER) and Character Error Rate (CER) metric calculations.
- `pyyaml` >= 6.0 - Parsing YAML configuration files.
- `numpy` >= 1.24.0 - Numerical processing and stats calculations.
- `pyarrow` >= 12.0.0 - Underlying Parquet format support for pandas and HF downloads.
## Configuration
- None required for local CLI, but LLM classifier requires `OPENAI_API_KEY` for OpenAI API calls.
- `configs/dataset.yaml` - Dataset repository, splits, and schema column mapping.
- `configs/taxonomy.yaml` - Term classification frequency thresholds and validation rules.
- `configs/llm.yaml` - LLM provider, model model, structured output, and batch configuration.
- `configs/asr.yaml` - ASR baseline model selection, normalizations, and splits to evaluate.
- `configs/report.yaml` - Language, format, and destination directory configuration for report generation.
## Platform Requirements
- Linux (user environment). Requires internet connectivity to reach Hugging Face Hub and OpenAI API.
- Standard Python environment running the package CLI commands.
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Naming Patterns
- `snake_case.py` for all python source files (`auditor.py`, `download.py`).
- `test_*.py` prefixed with `test_` for test scripts collocated inside the `tests/` directory (`test_config.py`).
- `kebab-case.yaml` for configuration files inside `configs/`.
- `PascalCase` for all class names (`AppConfig`, `HFDatasetClient`, `MetadataAuditor`).
- `snake_case` for all functions and method definitions (`load_and_map_df`, `list_files`, `download_metadata_only`).
- Private methods are prefixed with a single underscore (`_compute_local_stats`, `_resolve_file_path`).
- `snake_case` for local variables and class attributes (`local_raw_dir`, `schema_mappings`, `merged_df`).
- `UPPER_SNAKE_CASE` for global constants.
## Code Style
- Indentation: 4 spaces (standard PEP 8).
- Quotes: Double quotes (`"`) preferred for string literals, single quotes (`'`) used when nesting quotes.
- Line length: Keep under 120 characters where possible.
- No strict linter configuration file (e.g., `.flake8`, `pyproject.toml`) exists in the workspace.
- Adhere to PEP 8 standards when writing new Python files.
## Import Organization
- Keep one blank line separating standard library, third-party, and local import groups.
- Sort imports alphabetically within each group.
## Error Handling
- **Propagate Exceptions:** Service layer functions should raise descriptive built-in exceptions (e.g., `FileNotFoundError`, `ValueError`) or propagate library exceptions, rather than swallowing them or exiting directly.
- **Top-Level Catching:** Catch and handle all errors at the CLI entry point (`src/cli.py`) or within test wrappers. CLI caught errors must log the message using `logger.error()` and exit using `sys.exit(1)`.
- **Fail Fast:** Validate inputs and configurations early (e.g., during object initialization) and raise errors before starting heavy downloads or audits.
## Logging
- Standard Python `logging` module initialized through the custom `setup_logger` helper in `src/shared/logging.py`.
- Instantiated at module level: `logger = setup_logger("module-name")`.
- Use correct levels:
- No raw `print` statements in core source logic (`src/`); only use the logger. stdout printing is restricted to CLI output display in `src/cli.py`.
## Comments
- Required for all classes and public methods. Use triple double-quotes (`"""`) and summarize the inputs, actions, and return values.
- Explain the "why", not the "what". Avoid obvious comments (e.g., `# check if file exists`).
- Use comments to highlight non-obvious workarounds or mappings (e.g. explain why certain columns map case-insensitively).
- Format: `# TODO: description` to track tasks that should be addressed in future phases.
## Function Design
- **Early Return:** Use early return guard clauses to handle error states or boundary conditions, reducing nesting levels.
- **Single Responsibility:** Keep functions focused on a single task (e.g. `_compute_split_stats` only aggregates split data, not writing the CSV). Keep functions under 50 lines where practical.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## Pattern Overview
- CLI-driven command execution matching different pipeline phases.
- Stateless execution model where inputs are read from local storage and outputs are written as structured files.
- Decoupled modules organized by functional tasks (Acquisition, Auditing, Taxonomy/Term Analysis, ASR Baseline, Evaluation Metrics, Reporting).
## Layers
- Purpose: Parse command line arguments, load configuration, and orchestrate service executions.
- Contains: `src/cli.py`
- Depends on: Service Layer, Shared Layer.
- Used by: User / `Makefile` command commands.
- Purpose: Core pipeline logic for specific phases.
- Contains:
- Depends on: Shared Layer.
- Used by: CLI / Entry Layer.
- Purpose: Common infrastructure utilities like configuration parsing and logging.
- Contains:
- Depends on: Standard/external python packages only.
- Used by: All layers.
## Data Flow
- The pipeline is stateless. It reads state from inputs (e.g., config files, data directory, downloaded metadata) and persists outputs to files. It does not rely on an in-memory database or persistent servers between executions.
## Key Abstractions
- Purpose: Dynamic YAML configuration loader. Instantiates dictionary access structures for dataset, taxonomy, llm, asr, and report parameters.
- Pattern: Service configuration container.
- Purpose: Interaction client wrapping Hugging Face Hub APIs.
- Pattern: Repository facade.
- Purpose: Data schema mapping, statistics aggregator, and quality validator.
- Pattern: Auditor engine pattern.
## Entry Points
- Location: `src/cli.py`
- Triggers: CLI commands run via bash or Makefile targets.
- Responsibilities: Parses commands (`download-metadata`, `audit-metadata`), sets up config, runs corresponding auditor/client functions.
## Error Handling
- Exceptions thrown at service layers are propagated to the CLI layer.
- `src/cli.py` catches top-level errors, logs the stack/message via the setup logger, and exits with non-zero exit status (`sys.exit(1)`).
## Cross-Cutting Concerns
- Standard Python `logging` module configured in `src/shared/logging.py`.
- Formatted as `%(asctime)s - %(name)s - %(levelname)s - %(message)s` to console.
- Dynamic schema mapping in `MetadataAuditor`. Matches columns by lowercase comparisons against configured lists of fallbacks (e.g. mapping `Topic` to `topic`).
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
