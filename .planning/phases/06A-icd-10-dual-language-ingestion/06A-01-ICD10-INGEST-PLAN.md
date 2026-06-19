---
phase: 06A-icd-10-dual-language-ingestion
plan: 01
type: execute
wave: 1
depends_on: []
autonomous: true
files_modified:
  - src/icd10_ingestion/__init__.py
  - src/icd10_ingestion/schemas.py
  - src/icd10_ingestion/fetcher.py
  - src/icd10_ingestion/parser.py
  - src/icd10_ingestion/joiner.py
  - src/icd10_ingestion/reporter.py
  - src/icd10_ingestion/cli.py
  - data/icd10/.gitkeep
  - reports/.gitkeep
requirements:
  - FR1-01
  - FR1-02
  - FR1-03
  - FR1-04
  - FR1-05
  - FR1-06
user_setup: []
must_haves:
  truths:
    - "Every record in icd10_dual_language.jsonl has code, level, label_en, label_vi, parent_code, chapter_code, source_url, fetched_at"
    - "EN and VI records are joined by code field, never by label text"
    - "Failed codes are logged to icd10_ingestion_errors.csv with code, language, error_type, error_message, attempt, timestamp"
    - "Report at reports/icd10_ingestion_report.md contains record count, chapter coverage, error rate"
  artifacts:
    - path: src/icd10_ingestion/schemas.py
      provides: Pydantic model for ICD10Record
    - path: src/icd10_ingestion/fetcher.py
      provides: HTTP client with rate limiting and tenacity retry
    - path: src/icd10_ingestion/parser.py
      provides: HTML tree parsing for chapter/section/type/disease hierarchy
    - path: src/icd10_ingestion/joiner.py
      provides: EN/VI bilingual join by code field
    - path: src/icd10_ingestion/reporter.py
      provides: Markdown report generation
    - path: src/icd10_ingestion/cli.py
      provides: Click CLI with --mock/--full/--resume/--dry-run flags
    - path: data/icd10/icd10_dual_language.jsonl
      provides: Bilingual ICD-10 inventory (JSONL)
    - path: data/icd10/icd10_dual_language.csv
      provides: Bilingual ICD-10 inventory (CSV)
    - path: data/icd10/icd10_ingestion_errors.csv
      provides: Error log for failed fetches
    - path: reports/icd10_ingestion_report.md
      provides: Statistics and error summary
  key_links:
    - from: fetcher.py
      to: KCB ICD-10 API
      via: httpx.get
      pattern: "ccs.whiteneuron.com/api/ICD10/search"
    - from: parser.py
      to: fetcher.py
      via: HTML string in response.html
      pattern: "BeautifulSoup.*html.parser"
    - from: joiner.py
      to: parser.py
      via: EN/VI record dictionaries keyed by code
      pattern: "join_by_code"
    - from: cli.py
      to: fetcher.py/parser.py/joiner.py/reporter.py
      via: module imports
      pattern: "from src.icd10_ingestion"
---

<objective>
Build the complete ICD-10 dual-language ingestion pipeline: query KCB endpoint for EN and VI labels, parse HTML trees to extract chapter/section/type/disease hierarchy, join by code, validate with Pydantic, write JSONL/CSV outputs, and generate a statistics report.
</objective>

<context>
@docs/icd10-api-kcb.md
@src/shared/logging.py
@src/shared/config.py

**API base URL:** `https://ccs.whiteneuron.com/api/ICD10/search/{encoded_query}?lang={en|vi}&vol1=1&vol3=0&html=true`

**Response JSON shape:**
```json
{
  "status": "success",
  "string": "<query>",
  "time": 0.044,
  "html": "<escaped HTML string>"
}
```

**HTML tree structure (inside `html` field):**
```html
<li class="chapter">
  <a href="chapter/A00-B99">
    <span class="code">I</span>
    <span class="label">Certain infectious and parasitic diseases</span>
  </a>
  <ul>
    <li class="section">
      <a href="section/A00-A09">
        <span class="code">A00-A09</span>
        <span class="label">Intestinal infectious diseases</span>
      </a>
      <ul>
        <li class="type">
          <a href="type/A00">
            <span class="code">A00</span>
            <span class="label">Cholera</span>
          </a>
          <ul>
            <li class="disease">
              <a href="disease/A00.0">
                <span class="code">A00.0</span>
                <span class="label">Cholera due to Vibrio cholerae 01</span>
              </a>
            </li>
          </ul>
        </li>
      </ul>
    </li>
  </ul>
</li>
```

**Existing logging pattern (from src/shared/logging.py):**
```python
from src.shared.logging import setup_logger
logger = setup_logger("icd10_ingestion")
```

**Existing Pydantic usage pattern (from src/llm/schemas.py):** Use `BaseModel`, `Field`, `validator` — consistent with existing schema definitions.
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create module structure and Pydantic schema</name>
  <files>src/icd10_ingestion/__init__.py, src/icd10_ingestion/schemas.py</files>
  <read_first>src/llm/schemas.py (for Pydantic usage patterns)</read_first>
  <action>
    Create `src/icd10_ingestion/__init__.py` exporting `ICD10Record`, `ICD10Fetcher`, `ICD10Parser`, `ICD10Joiner`, `ICD10Reporter`, `run_ingestion`.

    Create `src/icd10_ingestion/schemas.py` with:

    ```python
    from pydantic import BaseModel, Field
    from typing import Optional, Literal

    class ICD10Record(BaseModel):
        code: str
        level: Literal["chapter", "section", "type", "disease"]
        label_en: str
        label_vi: str
        chapter_code: str
        chapter_label_en: str
        chapter_label_vi: str
        parent_code: Optional[str] = None
        source: str = "kcb_icd10_tt06"
        source_url: str
        fetched_at: str  # ISO 8601
    ```

    Also create `ICD10ErrorRecord(BaseModel)` for the error log:
    ```python
    class ICD10ErrorRecord(BaseModel):
        code: str
        language: Literal["en", "vi"]
        error_type: str  # "http_error", "parse_error", "status_failure", "timeout"
        error_message: str
        attempt: int
        timestamp: str  # ISO 8601
    ```
  </action>
  <verify>
    python -c "from src.icd10_ingestion import ICD10Record, ICD10ErrorRecord; r = ICD10Record(code='I10', level='type', label_en='Essential hypertension', label_vi='Tăng huyết áp nguyên phát', chapter_code='IX', chapter_label_en='Diseases of the circulatory system', chapter_label_vi='Bệnh của hệ tuần hoàn', source_url='https://ccs.whiteneuron.com/api/ICD10/search/I10?lang=en&vol1=1&vol3=0&html=true', fetched_at='2026-06-19T00:00:00+07:00'); print(r.model_dump())"
  </verify>
  <done>
    ICD10Record and ICD10ErrorRecord are importable and validate correctly; chapter_code is non-null for all levels.
  </done>
</task>

<task type="auto">
  <name>Task 2: Implement HTTP fetcher with rate limiting and retry</name>
  <files>src/icd10_ingestion/fetcher.py</files>
  <read_first>docs/icd10-api-kcb.md</read_first>
  <action>
    Create `src/icd10_ingestion/fetcher.py` implementing `ICD10Fetcher`.

    **Class `ICD10Fetcher`:**

    ```python
    class ICD10Fetcher:
        def __init__(
            self,
            rate_limit_ms: int = 200,
            timeout: int = 30,
            max_retries: int = 3,
            backoff_multiplier: float = 1.0,
            backoff_min: float = 1.0,
            backoff_max: float = 10.0,
        ):
            self.rate_limit_ms = rate_limit_ms
            self.base_url = "https://ccs.whiteneuron.com/api/ICD10"
            self.client = httpx.Client(timeout=timeout)
            self.stats = {"total_requests": 0, "total_failures": 0, "by_language": {"en": 0, "vi": 0}}
        ```

    - `fetch(code: str, language: Literal["en", "vi"]) -> httpx.Response` — Makes one HTTP GET to `{base_url}/search/{code}?lang={language}&vol1=1&vol3=0&html=true`. Raises `httpx.HTTPStatusError` on 4xx/5xx. Raises `httpx.TimeoutException` on timeout.
    - Use `tenacity.retry` decorator on `fetch` with `wait_exponential(multiplier=backoff_multiplier, min=backoff_min, max=backoff_max)` and `stop_after_attempt(max_retries)`. Pass `retry_error_callback` that logs and re-raises.
    - After every successful request (in `fetch`), call `time.sleep(rate_limit_ms / 1000)` before returning.
    - `fetch_many(codes: List[str], language: str) -> Dict[str, httpx.Response]` — Iterates over codes, calls `fetch` for each, collects responses keyed by code, catches and logs errors via `error_callback`.
    - `close()` — closes the httpx client.
    - `get_source_url(code: str, language: str) -> str` — Returns the exact URL string used for a request (used in record.source_url).
    - `_log_error(code: str, language: str, exc: Exception, attempt: int)` — appends an `ICD10ErrorRecord` to `self._errors: List[ICD10ErrorRecord]`.
    - `get_errors() -> List[ICD10ErrorRecord]` — returns the error list.

    **Import `httpx` and `tenacity`.** Use `time.sleep` for rate limiting (not asyncio).
  </action>
  <verify>
    python -c "
import httpx
from tenacity import retry, stop_after_attempt
# Verify httpx and tenacity are available
from src.icd10_ingestion.fetcher import ICD10Fetcher
f = ICD10Fetcher()
print('ICD10Fetcher instantiated OK')
print(f'Source URL: {f.get_source_url(\"I10\", \"en\")}')
print(f'Expected: https://ccs.whiteneuron.com/api/ICD10/search/I10?lang=en&vol1=1&vol3=0&html=true')
f.close()
"
  </verify>
  <done>
    ICD10Fetcher fetches from the correct URL, respects rate limiting, retries on failure, and logs errors.
  </done>
</task>

<task type="auto">
  <name>Task 3: Implement HTML parser for chapter/section/type/disease hierarchy</name>
  <files>src/icd10_ingestion/parser.py</files>
  <read_first>docs/icd10-api-kcb.md</read_first>
  <action>
    Create `src/icd10_ingestion/parser.py` implementing `ICD10Parser`.

    **Class `ICD10Parser`:**

    The parser takes an `httpx.Response` (or raw `dict` from `response.json()`) and extracts structured records.

    ```python
    class ParsedNode:
        code: str
        level: Literal["chapter", "section", "type", "disease"]
        label: str
        parent_code: Optional[str]
        chapter_code: str
        chapter_label: str
    ```

    **`parse_response(response_data: dict, language: str) -> List[ParsedNode]`:**

    1. If `response_data["status"] != "success"`, return empty list and log warning.
    2. Extract `html` string from `response_data["html"]`.
    3. Parse with `BeautifulSoup(html, "html.parser")`.
    4. Walk the `<ul>/<li>` tree depth-first. Track current chapter/section/type as we descend.
    5. For each `<li class="chapter|section|type|disease">`:
       - Find the `<a>` child, then `<span class="code">` and `<span class="label">`.
       - Strip `<b class="highline">` markup from label text (use `soup.get_text()` or regex).
       - Set `chapter_code`/`chapter_label` from the nearest ancestor chapter node.
       - Set `parent_code` from the nearest ancestor type/section node (type's parent is section, disease's parent is type, section's parent is chapter).
       - Append a `ParsedNode`.
    6. Return the list of `ParsedNode` objects.

    **Level determination:**
    - `<li class="chapter">` → level="chapter", code=`span.code` text (e.g. "I")
    - `<li class="section">` → level="section", code=`span.code` text (e.g. "A00-A09")
    - `<li class="type">` → level="type", code=`span.code` text (e.g. "A00")
    - `<li class="disease">` → level="disease", code=`span.code` text (e.g. "A00.0")

    **Chapter code format:** For chapter-level nodes, store the Roman numeral as-is (e.g., "I", "IX"). For all other levels, the chapter code is the chapter node's code (e.g., "I" for circulatory diseases).

    **Import `BeautifulSoup` from `bs4`.** Use `html.parser` parser (not lxml — no additional installation needed).
  </action>
  <verify>
    python -c "
from src.icd10_ingestion.parser import ICD10Parser
p = ICD10Parser()
# Mock a known-success response structure
mock = {
    'status': 'success',
    'string': 'A00',
    'html': '<li class=\"chapter\"><a href=\"chapter/A00-B99\"><span class=\"code\">I</span><span class=\"label\">Chapter I</span></a></li>'
}
nodes = p.parse_response(mock, 'en')
print(f'Parsed {len(nodes)} nodes')
p.close()
"
  </verify>
  <done>
    ICD10Parser correctly extracts chapter/section/type/disease nodes from HTML response and handles status=failure gracefully.
  </done>
</task>

<task type="auto">
  <name>Task 4: Implement EN/VI joiner and writer</name>
  <files>src/icd10_ingestion/joiner.py</files>
  <read_first>src/icd10_ingestion/schemas.py, src/icd10_ingestion/fetcher.py, src/icd10_ingestion/parser.py</read_first>
  <action>
    Create `src/icd10_ingestion/joiner.py` implementing `ICD10Joiner`.

    **Class `ICD10Joiner`:**

    ```python
    class ICD10Joiner:
        def __init__(self, output_dir: str = "data/icd10"):
            self.output_dir = output_dir
            self.errors: List[ICD10ErrorRecord] = []
            self.jsonl_path = os.path.join(output_dir, "icd10_dual_language.jsonl")
            self.csv_path = os.path.join(output_dir, "icd10_dual_language.csv")
            self.error_csv_path = os.path.join(output_dir, "icd10_ingestion_errors.csv")
        ```

    **`build_code_list() -> List[str]`:**
    Generate the complete ICD-10 3-char and 4-char code list:
    1. For each letter A–Z: generate 3-char codes (e.g., A00–Z99). Note: not all ranges are valid; use the WHO ICD-10 tabular list ranges (A00-A79, A80-B99, C00-D48, D50-D89, E00-E90, F00-F99, G00-G99, H00-H59, H60-H95, I00-I99, J00-J99, K00-K93, L00-L99, M00-M99, N00-N99, O00-O99, P00-P96, Q00-Q99, R00-R99, S00-T98, V01-Y98, Z00-Z99).
    2. From each 3-char code, generate 4-char subcodes (e.g., A00.0, A00.1).
    3. Return as `List[str]`. This is the master list for `--full` mode.

    **`run(fetched_en: Dict[str, ParsedNode], fetched_vi: Dict[str, ParsedNode]) -> int`:**
    1. Iterate over all unique codes from `fetched_en` and `fetched_vi`.
    2. For each code present in both: build an `ICD10Record` with `label_en` from EN node, `label_vi` from VI node.
    3. For each code present in only one language: log an `ICD10ErrorRecord` with `error_type="missing_language"` and proceed (do not block; write the available label with the missing one as empty string).
    4. Write records incrementally to JSONL (append mode, every 100 records).
    5. After all records written, write the error CSV.
    6. Return total record count.

    **CSV columns:** `code,level,label_en,label_vi,chapter_code,chapter_label_en,chapter_label_vi,parent_code,source,source_url,fetched_at`

    **JSONL format:** One `ICD10Record.model_dump()` per line (JSON lines).

    **The join key is `code` field only.** Do not join by label text under any circumstances.

    Use `os.makedirs(output_dir, exist_ok=True)` before writing.
  </action>
  <verify>
    python -c "
from src.icd10_ingestion.joiner import ICD10Joiner
j = ICD10Joiner(output_dir='/tmp/icd10_test')
codes = j.build_code_list()
print(f'Generated {len(codes)} codes')
print(f'Sample 3-char: {[c for c in codes if len(c)==3][:5]}')
print(f'Sample 4-char: {[c for c in codes if len(c)==4][:5]}')
print('ICD10Joiner OK')
"
  </verify>
  <done>
    ICD10Joiner generates the complete code list, joins EN/VI records by code field, writes JSONL and CSV incrementally, and logs missing-language errors.
  </done>
</task>

<task type="auto">
  <name>Task 5: Implement report generator</name>
  <files>src/icd10_ingestion/reporter.py</files>
  <read_first>src/icd10_ingestion/schemas.py</read_first>
  <action>
    Create `src/icd10_ingestion/reporter.py` implementing `ICD10Reporter`.

    **Class `ICD10Reporter`:**

    ```python
    class ICD10Reporter:
        def __init__(self, output_dir: str = "reports"):
            self.output_dir = output_dir
            self.report_path = os.path.join(output_dir, "icd10_ingestion_report.md")
        ```

    **`generate(record_count: int, error_count: int, errors: List[ICD10ErrorRecord], chapter_stats: Dict[str, int], level_stats: Dict[str, int]) -> str`:**
    Write `reports/icd10_ingestion_report.md` with:
    1. Title: `# ICD-10 Dual-Language Ingestion Report`
    2. Ingestion metadata: `fetched_at`, source URL, total records, error count, error rate percentage.
    3. Chapter coverage table: chapter code, chapter label (EN), record count. Sorted by chapter code.
    4. Level distribution: counts for chapter/section/type/disease.
    5. Error summary table: error_type, count, example error messages (top 5 by frequency).
    6. Data quality notes: join success rate, language coverage notes.
    7. Downstream usage: notes on which phases depend on this data.

    Call this method at the end of the CLI run.

    Use `from datetime import datetime, timezone`.
  </action>
  <verify>
    python -c "
from src/icd10_ingestion/reporter import ICD10Reporter
r = ICD10Reporter(output_dir='/tmp/icd10_test_reports')
print(f'Report path: {r.report_path}')
print('ICD10Reporter OK')
"
  </verify>
  <done>
    ICD10Reporter generates a markdown report with statistics, chapter coverage, error summary, and data quality notes.
  </done>
</task>

<task type="auto">
  <name>Task 6: Implement CLI with --mock, --full, --resume, --dry-run flags</name>
  <files>src/icd10_ingestion/cli.py</files>
  <read_first>src/cli.py, src/icd10_ingestion/fetcher.py, src/icd10_ingestion/parser.py, src/icd10_ingestion/joiner.py, src/icd10_ingestion/reporter.py</read_first>
  <action>
    Create `src/icd10_ingestion/cli.py` implementing the Click CLI.

    **CLI structure:**

    ```python
    import click
    import time
    from datetime import datetime, timezone
    from src.shared.logging import setup_logger
    from src.icd10_ingestion.fetcher import ICD10Fetcher
    from src.icd10_ingestion.parser import ICD10Parser
    from src.icd10_ingestion.joiner import ICD10Joiner
    from src.icd10_ingestion.reporter import ICD10Reporter
    from src.icd10_ingestion.schemas import ICD10Record, ICD10ErrorRecord

    logger = setup_logger("icd10_ingestion")

    @click.command()
    @click.option("--mock", is_flag=True, help="Smoke test: fetch only 5 known codes (I10, E11, J18, K29, N39)")
    @click.option("--full", is_flag=True, help="Full ingestion: all ~14,400 ICD-10 codes")
    @click.option("--resume", is_flag=True, help="Resume from last failure (reads progress file)")
    @click.option("--dry-run", is_flag=True, help="Print code list without making API calls")
    @click.option("--output", default="data/icd10", help="Output directory")
    @click.option("--code-list", type=click.Path(exists=True), default=None, help="Custom code list file (one code per line)")
    def run(mock, full, resume, dry_run, output, code_list):
        ...
    ```

    **--mock mode:**
    1. Use hardcoded list: `["I10", "E11", "J18", "K29", "N39"]`.
    2. Create mock output dir `data/icd10/mock/`.
    3. For each code, call fetcher for EN and VI.
    4. Print 5 records to stdout.
    5. Write `data/icd10/mock/icd10_sample.jsonl` and `icd10_sample.csv`.
    6. Print: "Mock ingestion complete: {n} records written to {output}"

    **--full mode:**
    1. Get code list from `ICD10Joiner.build_code_list()`.
    2. Iterate over all codes, fetch EN and VI for each.
    3. Parse responses, join, write incrementally.
    4. Write error log and report.
    5. Print progress every 100 codes: `f"Progress: {i}/{total} ({pct:.1f}%) — errors: {error_count}"`
    6. Print: "Full ingestion complete: {record_count} records, {error_count} errors ({error_rate:.1f}%)"

    **--resume mode:**
    1. Read `data/icd10/.progress.json` (stores last processed code index).
    2. Skip already-processed codes.
    3. Continue from where it left off.
    4. If no progress file exists, behave as --full.

    **--dry-run mode:**
    1. Load code list (from file or built-in).
    2. Print total count and first 10 codes.
    3. Do NOT make any HTTP requests.

    **--code-list option:**
    1. If provided, read codes from the file (one code per line, strip whitespace).
    2. Override the built-in code list.

    **Common flow:**
    1. Initialize `ICD10Fetcher`, `ICD10Parser`, `ICD10Joiner(output_dir)`, `ICD10Reporter(output_dir="reports")`.
    2. After ingestion, call `ICD10Reporter.generate(...)` with stats.
    3. Close fetcher client.
    4. Log final statistics.

    **Entry point (if __name__ == "__main__"):** call `run()`.

    Follow the `--mock` pattern from `src/llm/classifier.py` (line 67-71) and `src/asr/transcriber.py` (line 77-98) for flag-based smoke testing.
  </action>
  <verify>
    python -c "
from src.icd10_ingestion.cli import run
import click
print('CLI module loaded OK')
# Verify all imports work
from src.icd10_ingestion import ICD10Fetcher, ICD10Parser, ICD10Joiner, ICD10Reporter
print('All imports OK')
"
  </verify>
  <done>
    CLI accepts --mock, --full, --resume, --dry-run, --output, --code-list flags and produces correct output artifacts.
  </done>
</task>

<task type="auto">
  <name>Task 7: Create gitkeep files and run smoke test</name>
  <files>data/icd10/.gitkeep, reports/.gitkeep</files>
  <action>
    Create `data/icd10/.gitkeep` and `reports/.gitkeep` to ensure directories are tracked in git.

    Run the mock smoke test:
    ```bash
    python -m src.icd10_ingestion.cli --mock --output data/icd10/mock/
    ```

    Verify the output:
    1. `data/icd10/mock/icd10_sample.jsonl` exists and has ≥5 records.
    2. `data/icd10/mock/icd10_sample.csv` exists and has ≥5 rows (plus header).
    3. Each record has all required fields: `code`, `level`, `label_en`, `label_vi`, `chapter_code`, `source_url`, `fetched_at`.
    4. `label_en` and `label_vi` are both non-empty strings for all mock records.
    5. Join was done by `code`, not by label text.

    Also verify by checking a record:
    ```bash
    head -1 data/icd10/mock/icd10_sample.jsonl | python -m json.tool
    ```
  </action>
  <verify>
    python -m src.icd10_ingestion.cli --mock --output data/icd10/mock/ && \
    python -c "
import json
with open('data/icd10/mock/icd10_sample.jsonl') as f:
    records = [json.loads(line) for line in f]
print(f'Record count: {len(records)}')
for r in records:
    assert r.get('code'), 'Missing code'
    assert r.get('label_en'), 'Missing label_en'
    assert r.get('label_vi'), 'Missing label_vi'
    assert r.get('chapter_code'), 'Missing chapter_code'
    assert r.get('source_url'), 'Missing source_url'
    assert r.get('fetched_at'), 'Missing fetched_at'
    assert 'ccs.whiteneuron.com' in r.get('source_url',''), 'Wrong source_url'
print('All assertions passed — schema valid')
"
  </verify>
  <done>
    Mock smoke test passes: ≥5 records written, all required fields present, source_url points to ccs.whiteneuron.com.
  </done>
</task>

</tasks>

<verification>
```bash
# 1. Schema validation
python -c "from src.icd10_ingestion import ICD10Record; print('Schema OK')"

# 2. Module imports
python -c "from src.icd10_ingestion import ICD10Fetcher, ICD10Parser, ICD10Joiner, ICD10Reporter; print('All modules import OK')"

# 3. Mock smoke test
python -m src.icd10_ingestion.cli --mock --output data/icd10/mock/
python -c "
import json
with open('data/icd10/mock/icd10_sample.jsonl') as f:
    records = [json.loads(line) for line in f]
assert len(records) >= 5, f'Expected ≥5 records, got {len(records)}'
for r in records:
    for field in ['code','level','label_en','label_vi','chapter_code','source_url','fetched_at']:
        assert r.get(field), f'Missing field: {field}'
print('Mock smoke test PASSED')
"

# 4. CLI help
python -m src.icd10_ingestion.cli --help | grep -E "mock|full|resume|dry-run"
```

Expected: all checks pass with no errors.
</verification>

<success_criteria>
1. `src/icd10_ingestion/schemas.py` defines `ICD10Record` with all 11 required fields.
2. `src/icd10_ingestion/fetcher.py` fetches from `https://ccs.whiteneuron.com/api/ICD10/search/{code}?lang={en|vi}&vol1=1&vol3=0&html=true` with 200ms rate limiting and tenacity retry.
3. `src/icd10_ingestion/parser.py` parses HTML `<li class="chapter|section|type|disease">` trees into `ParsedNode` lists.
4. `src/icd10_ingestion/joiner.py` joins EN and VI records by `code` field only (never by label text), writes JSONL and CSV incrementally, and logs errors.
5. `src/icd10_ingestion/reporter.py` generates `reports/icd10_ingestion_report.md` with statistics, chapter coverage, and error summary.
6. `src/icd10_ingestion/cli.py` exposes `--mock`, `--full`, `--resume`, `--dry-run`, `--output`, `--code-list` flags.
7. Mock smoke test produces ≥5 valid records with all required fields in `data/icd10/mock/icd10_sample.jsonl` and `.csv`.
8. Every record has `source_url` pointing to the actual API endpoint used.
9. Error log `data/icd10/icd10_ingestion_errors.csv` captures failed fetches with code, language, error_type, error_message, attempt, timestamp.
10. The `--full` run is resumable via `--resume` flag and progress tracking.
</success_criteria>

<output>
Create `.planning/phases/06A-icd-10-dual-language-ingestion/06A-01-ICD10-INGEST-SUMMARY.md` when done using the summary template at `@$HOME/.cursor/get-shit-done/templates/summary.md`.
</output>
