# Coding Conventions

**Analysis Date:** 2026-06-16

## Naming Patterns

**Files:**
- `snake_case.py` for all python source files (`auditor.py`, `download.py`).
- `test_*.py` prefixed with `test_` for test scripts collocated inside the `tests/` directory (`test_config.py`).
- `kebab-case.yaml` for configuration files inside `configs/`.

**Classes:**
- `PascalCase` for all class names (`AppConfig`, `HFDatasetClient`, `MetadataAuditor`).

**Functions & Methods:**
- `snake_case` for all functions and method definitions (`load_and_map_df`, `list_files`, `download_metadata_only`).
- Private methods are prefixed with a single underscore (`_compute_local_stats`, `_resolve_file_path`).

**Variables:**
- `snake_case` for local variables and class attributes (`local_raw_dir`, `schema_mappings`, `merged_df`).
- `UPPER_SNAKE_CASE` for global constants.

## Code Style

**Formatting:**
- Indentation: 4 spaces (standard PEP 8).
- Quotes: Double quotes (`"`) preferred for string literals, single quotes (`'`) used when nesting quotes.
- Line length: Keep under 120 characters where possible.

**Linting:**
- No strict linter configuration file (e.g., `.flake8`, `pyproject.toml`) exists in the workspace.
- Adhere to PEP 8 standards when writing new Python files.

## Import Organization

**Order:**
1. Standard library imports (e.g., `import os`, `import sys`, `import json`, `import datetime`).
2. Third-party packages (e.g., `import pandas as pd`, `import yaml`, `from huggingface_hub import HfApi`).
3. Local/application imports (e.g., `from src.shared.config import AppConfig`, `from src.shared.logging import setup_logger`).

**Grouping:**
- Keep one blank line separating standard library, third-party, and local import groups.
- Sort imports alphabetically within each group.

## Error Handling

**Patterns:**
- **Propagate Exceptions:** Service layer functions should raise descriptive built-in exceptions (e.g., `FileNotFoundError`, `ValueError`) or propagate library exceptions, rather than swallowing them or exiting directly.
- **Top-Level Catching:** Catch and handle all errors at the CLI entry point (`src/cli.py`) or within test wrappers. CLI caught errors must log the message using `logger.error()` and exit using `sys.exit(1)`.
- **Fail Fast:** Validate inputs and configurations early (e.g., during object initialization) and raise errors before starting heavy downloads or audits.

## Logging

**Framework:**
- Standard Python `logging` module initialized through the custom `setup_logger` helper in `src/shared/logging.py`.
- Instantiated at module level: `logger = setup_logger("module-name")`.
- Use correct levels:
  - `logger.info()` for tracking progress milestones (e.g., "Starting local metadata audit...").
  - `logger.warning()` for non-fatal issues (e.g., missing optional fields).
  - `logger.error()` for fatal failures that lead to program termination.
- No raw `print` statements in core source logic (`src/`); only use the logger. stdout printing is restricted to CLI output display in `src/cli.py`.

## Comments

**Docstrings:**
- Required for all classes and public methods. Use triple double-quotes (`"""`) and summarize the inputs, actions, and return values.

**Inline Comments:**
- Explain the "why", not the "what". Avoid obvious comments (e.g., `# check if file exists`).
- Use comments to highlight non-obvious workarounds or mappings (e.g. explain why certain columns map case-insensitively).

**TODO Comments:**
- Format: `# TODO: description` to track tasks that should be addressed in future phases.

## Function Design

- **Early Return:** Use early return guard clauses to handle error states or boundary conditions, reducing nesting levels.
- **Single Responsibility:** Keep functions focused on a single task (e.g. `_compute_split_stats` only aggregates split data, not writing the CSV). Keep functions under 50 lines where practical.

---

*Convention analysis: 2026-06-16*
*Update when patterns change*
