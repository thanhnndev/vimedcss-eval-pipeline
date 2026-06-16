# Testing Patterns

**Analysis Date:** 2026-06-16

## Test Framework

**Runner:**
- `pytest` (referenced in `requirements.txt` as `pytest>=7.0.0`).
- No separate pytest configuration file; executed using system paths.

**Assertion Library:**
- Standard python `assert` statements.
- Matchers: `==`, `in`, `len()`, and dictionary comparison checks.

**Run Commands:**
```bash
make test                            # Run all tests in the suite
PYTHONPATH=. .venv/bin/pytest        # Alternate command to run all tests
PYTHONPATH=. .venv/bin/pytest tests/test_config.py  # Run tests in a single file
```

## Test File Organization

**Location:**
- All test scripts are placed in the `tests/` directory at the project root.
- No collocated test files inside `src/`.

**Naming:**
- Files: `test_*.py` (e.g., `test_config.py`, `test_auditor.py`).
- Functions: `test_*` (e.g., `test_metadata_auditor_stats_and_issues`).

**Structure:**
```
tests/
├── test_auditor.py       # Tests for MetadataAuditor
├── test_config.py        # Tests for AppConfig
└── test_hf_client.py     # Tests for HFDatasetClient
```

## Test Structure

**Fixture Organization:**
- Uses pytest fixtures defined near the top of the test files (e.g. `@pytest.fixture def mock_config():`).
- Fixtures provide sample config parameters, paths, and raw CSV contents.

**Example Structure (`tests/test_config.py`):**
```python
import pytest
from src.shared.config import AppConfig

def test_app_config_load():
    # Arrange & Act
    config = AppConfig(config_dir="configs")
    
    # Assert
    assert config.dataset is not None
    assert config.get_dataset_config()["repo_id"] == "tensorxt/ViMedCSS"
```

## Mocking

**Framework:**
- Built-in `pytest` features, particularly the `tmp_path` and `MonkeyPatch` fixtures.
- No third-party mocking libraries (like `unittest.mock` or `pytest-mock`) are currently imported.

**Mocking Patterns:**
- **File System Mocking:** Use the standard `tmp_path` fixture to write test files (like a mock CSV or config) and redirect the configuration paths to point to this temporary directory.
- **Function Mocking:** Use `pytest.MonkeyPatch` context managers to stub file operations or directory creations during tests:
```python
with pytest.MonkeyPatch.context() as mp:
    def mock_makedirs(*args, **kwargs):
        pass
    mp.setattr(os, "makedirs", mock_makedirs)
    # execute test
```

## Fixtures and Factories

**Test Data:**
- CSV test tables are declared as raw strings in fixtures:
```python
@pytest.fixture
def sample_csv_content():
    return (
        "segment_id,duration_seconds,segment_text,cs_terms_list,topic,start_time,end_time\n"
        "Med_CS-100-1,10.5,Bệnh nhân dùng metformin điều trị,metformin,Treatments,01:10,01:20\n"
    )
```
- Saved to a path during test initialization using `tmp_path`.

## Coverage

- **Enforcement:** No minimum coverage targets are set or checked in CI.
- **Tracking:** No configuration for test coverage (e.g., `pytest-cov`, `coverage.py`) is registered in `requirements.txt` or the `Makefile`. Tests are currently evaluated strictly on pass/fail.

## Test Types

**Unit/Component Tests:**
- Tests verify specific helper classes and configuration mappings in isolation.
- Integration endpoints (like calling external APIs on Hugging Face) are mocked by stubbing or passing targeted configurations.

---

*Testing analysis: 2026-06-16*
*Update when test patterns change*
