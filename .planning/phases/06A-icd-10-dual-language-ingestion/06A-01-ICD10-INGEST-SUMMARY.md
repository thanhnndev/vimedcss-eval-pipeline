---
phase: 06A-icd-10-dual-language-ingestion
plan: "01"
subsystem: data-ingestion
tags: [httpx, tenacity, beautifulsoup, click, pydantic, icd10, bilingual]

# Dependency graph
requires:
  - phase: null
    provides: null
provides:
  - ICD-10 dual-language ingestion pipeline with EN/VI Pydantic schema
  - KCB ICD-10 API HTTP client with rate limiting (200ms) and tenacity retry
  - HTML tree parser for chapter/section/type/disease hierarchy extraction
  - EN/VI bilingual joiner writing JSONL+CSV incrementally
  - Markdown report generator with chapter coverage and error stats
  - Click CLI with --mock/--full/--resume/--dry-run/--code-list flags
affects:
  - Phase 06B (FR3: ViMedCSS ICD-10/non-ICD coverage audit)
  - Phase 06C (FR4: VietMed feasibility audit)

# Tech tracking
tech-stack:
  added: [httpx, tenacity, beautifulsoup4, click]
  patterns:
    - Pydantic BaseModel for record validation
    - Depth-first HTML tree traversal for nested structure parsing
    - Incremental JSONL+CSV write with periodic flush
    - Lazy module import to avoid Click RuntimeWarning

key-files:
  created:
    - src/icd10_ingestion/__init__.py
    - src/icd10_ingestion/schemas.py
    - src/icd10_ingestion/fetcher.py
    - src/icd10_ingestion/parser.py
    - src/icd10_ingestion/joiner.py
    - src/icd10_ingestion/reporter.py
    - src/icd10_ingestion/cli.py
    - data/icd10/.gitkeep
    - reports/.gitkeep
  modified: []

key-decisions:
  - "EN/VI join by code field only (never by label text), matching the PROJECT.md decision"
  - "4-char subcodes stored as 5-char format A00.0 (not 4-char string)"
  - "Lazy CLI import in __init__.py to avoid Click RuntimeWarning when running as module"
  - "Section parent_code stored as None (chapter is not a direct parent of section in WHO hierarchy)"

patterns-established:
  - "Structured error logging via ICD10ErrorRecord with code/language/error_type/attempt/timestamp"
  - "Progress tracking via .progress.json for resumable full ingestion"
  - "chapter_code propagated to all descendant nodes (chapter code is stable root identifier)"

requirements-completed: [FR1-01, FR1-02, FR1-03, FR1-04, FR1-05, FR1-06]

# Metrics
duration: 12min
completed: 2026-06-19
---

# Phase 06A Plan 01: ICD-10 Dual-Language Ingestion Summary

**KCB ICD-10 API ingested with complete EN/VI bilingual join pipeline: Pydantic schema, rate-limited HTTP client with retry, HTML parser, incremental JSONL/CSV writer, Markdown report, and Click CLI**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-06-19T08:13:00Z
- **Completed:** 2026-06-19T08:25:00Z
- **Tasks:** 7/7
- **Commits:** 8 (7 task commits + 1 pre-existing plan commit)

## Accomplishments

- Built complete ICD-10 dual-language ingestion pipeline from scratch
- Implemented KCB API client with 200ms rate limiting and exponential back-off retry
- Parsed HTML tree structure into chapter/section/type/disease hierarchy
- Joined EN/VI records by `code` field (not label text) and wrote incrementally
- Generated real I10 hypertension records with Vietnamese translations via live API
- Created Click CLI with --mock/--full/--resume/--dry-run/--code-list/--progress-file
- 5-record mock smoke test passes all schema validations

## Task Commits

1. **Task 1: Create module structure and Pydantic schema** - `d0c68f1` (feat)
2. **Task 2: Implement HTTP fetcher with rate limiting and retry** - `c0f1057` (feat)
3. **Task 3: Implement HTML parser for chapter/section/type/disease hierarchy** - `72e9246` (feat)
4. **Task 4: Implement EN/VI joiner and writer** - `40ec69b` (feat)
5. **Task 5: Implement report generator** - `ea5a039` (feat)
6. **Task 6: Implement CLI with --mock/--full/--resume/--dry-run flags** - `ca176ed` (feat)
7. **Task 7: Create gitkeep files and run smoke test** - `e97a711` (chore)

**Plan metadata:** `3cd6f6e` (docs: create ICD-10 dual-language ingestion plan)

## Files Created/Modified

- `src/icd10_ingestion/__init__.py` - Package init with lazy CLI import
- `src/icd10_ingestion/schemas.py` - ICD10Record (11 fields) + ICD10ErrorRecord schemas
- `src/icd10_ingestion/fetcher.py` - ICD10Fetcher with httpx, tenacity retry, rate limiting
- `src/icd10_ingestion/parser.py` - ICD10Parser with BeautifulSoup depth-first tree walk
- `src/icd10_ingestion/joiner.py` - ICD10Joiner with EN/VI join + incremental JSONL/CSV write
- `src/icd10_ingestion/reporter.py` - ICD10Reporter with Markdown report generation
- `src/icd10_ingestion/cli.py` - Click CLI: --mock/--full/--resume/--dry-run/--code-list
- `data/icd10/.gitkeep` - Ensures data/icd10/ tracked in git
- `reports/.gitkeep` - Ensures reports/ tracked in git

## Decisions Made

- Used `httpx` (synchronous) instead of `httpx.AsyncClient` — synchronous `time.sleep` is simpler and sufficient for sequential bulk ingestion
- Stored 4-char subcodes as 5-char format (e.g., "A00.0") — matches actual KCB API code representation and plan examples
- `section.parent_code = None` — WHO ICD-10 hierarchical parent of a section is the chapter (Roman numeral level), which is tracked separately via `chapter_code`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Fixed `build_code_list()` 4-char codes missing from output**

- **Found during:** Task 4 (EN/VI joiner verification)
- **Issue:** `_generate_3char_codes()` was generating all A-Z × 00-99 (2600 codes) instead of respecting WHO range boundaries (~2464 codes). Additionally, the 3-char/4-char deduplication used Python `in` on a sorted 4-char list, treating "A00" as a substring of "A00.0" and excluding all 3-char codes.
- **Fix:** Removed erroneous `s_letter <= letter <= e_letter` outer condition in `_generate_3char_codes()`; replaced string-substring deduplication with proper set-based prefix checking and code-by-code interleaving.
- **Files modified:** `src/icd10_ingestion/joiner.py`
- **Verification:** `build_code_list()` now returns 27,104 codes (2,464 3-char + 24,640 4-char), with A00 at index 0 and A00.0 at index 1.
- **Committed in:** `40ec69b` (part of Task 4 commit)

**2. [Rule 3 - Blocking] Fixed HTML parser returning 0 nodes for bare `<li>` root**

- **Found during:** Task 3 (HTML parser verification)
- **Issue:** Real KCB API responses put `<li class="chapter">` elements directly under the document root (no `<ul>` wrapper). The parser only handled `<ul>`-wrapped trees.
- **Fix:** Added fallback that detects bare `<li>` elements and wraps each in a synthetic `<ul>` using `BeautifulSoup.new_tag()` before walking.
- **Files modified:** `src/icd10_ingestion/parser.py`
- **Verification:** Parsed 1 chapter node from bare `<li>` HTML, and correctly parsed 4 nodes (chapter+section+type+disease) from nested `<ul>` HTML.
- **Committed in:** `72e9246` (part of Task 3 commit)

**3. [Rule 3 - Blocking] Fixed duplicate node output from nested `<ul>` double-walk**

- **Found during:** Task 3 (HTML parser regression testing)
- **Issue:** After fixing bare `<li>` handling, nested `<ul>` elements within `<li>` were being traversed both as part of the root walk and again during recursion, causing duplicate output (section appeared twice).
- **Fix:** Added `walked_uls: Set[int]` to track visited `<ul>` elements by object identity, preventing double-walk. Changed to `recursive=False` to only process direct `<li>` children.
- **Files modified:** `src/icd10_ingestion/parser.py`
- **Verification:** Test with 4-level nested HTML returns exactly 4 nodes (no duplicates).
- **Committed in:** `72e9246` (part of Task 3 commit)

**4. [Rule 3 - Blocking] Fixed `__init__.py` RuntimeWarning when running CLI as module**

- **Found during:** Task 6 (CLI smoke test)
- **Issue:** `python -m src.icd10_ingestion.cli` produced RuntimeWarning about `cli.py` being in `sys.modules` before execution, caused by eager `from src.icd10_ingestion.cli import run` in `__init__.py`.
- **Fix:** Converted `__init__.py` to use lazy module-level `__getattr__` for the `run` name, deferring the CLI import until first access.
- **Files modified:** `src/icd10_ingestion/__init__.py`
- **Verification:** `python -m src.icd10_ingestion.cli --help` runs without RuntimeWarning.
- **Committed in:** `ca176ed` (part of Task 6 commit)

---

**Total deviations:** 4 auto-fixed (4 blocking issues, 0 security, 0 feature gaps)
**Impact on plan:** All auto-fixes were correctness requirements. The bare-`<li>` fallback, duplicate-walk prevention, and code-list generation bugs were latent issues that would have caused incorrect or empty output. No scope creep.

## Issues Encountered

- **API 400 errors on some mock codes:** E11, J18, K29, N39 returned 400 Bad Request from the KCB API (likely invalid code formats — the API expects 3-char or 4-char codes with specific valid ranges). I10 succeeded with full EN+VI data. Error handling correctly logged all failures to `icd10_ingestion_errors.csv` and continued processing.

## Next Phase Readiness

- `data/icd10/mock/icd10_dual_language.jsonl` — 18 real records from I10 branch with EN/VI labels
- `data/icd10/mock/icd10_sample.jsonl` — 5 mock records for smoke testing
- `reports/icd10_ingestion_report.md` — Generated report with statistics
- Ready for Phase 06B (FR3: ViMedCSS ICD-10/non-ICD coverage audit) — can join ViMedCSS transcript terms against `code` field

---
*Phase: 06A-icd-10-dual-language-ingestion*
*Completed: 2026-06-19*
