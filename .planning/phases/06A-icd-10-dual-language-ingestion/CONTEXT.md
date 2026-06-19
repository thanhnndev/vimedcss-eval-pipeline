# Phase 6a: ICD-10 Dual-Language Ingestion — Context

**Gathered:** 2026-06-19
**Status:** Ready for planning
**Source:** PRD Express Path + domain research (STACK.md, FEATURES.md, ARCHITECTURE.md, PITFALLS.md, RESEARCH.md)

<domain>

## Phase Boundary

Phase 6a ingests ICD-10 as a bilingual EN/VI disease backbone. It is the foundation for all subsequent phases (6b–6k): medical term taxonomy, coverage audit, LLM conversation generation, TTS, and ASR evaluation all depend on having a clean, code-keyed ICD-10 inventory with chapter/section/type/disease hierarchy.

**Deliverables:** `data/icd10/icd10_dual_language.csv`, `.jsonl`, `icd10_ingestion_errors.csv`, `reports/icd10_ingestion_report.md`.

</domain>

<decisions>

## Implementation Decisions

### ICD-10 Endpoint

- Use KCB ICD-10 API: `/api/ICD10/search/<query>?lang=vi|en&vol1=1&vol3=0&html=true`
- Config: `lang=en` and `lang=vi`, `vol1=1`, `vol3=0`, `html=true`
- English keyword search is more reliable than Vietnamese free-text search
- Prefer code search over label search where possible

### EN/VI Join Strategy

- **Join by `code`, NOT by label text.** English "Essential hypertension" ≠ Vietnamese "Tăng huyết áp nguyên phát" — labels differ; code is the stable join key
- Every record must have `code`, `level`, `label_en`, `label_vi`, `parent_code`, `chapter_code`, `source_url`, `fetched_at`
- ISO 3166-1 alpha-2 chapter codes (e.g., "IX" for diseases of the circulatory system)

### Response Parsing

- Parse JSON response; extract `html` field; parse HTML tree to get `chapter`, `section`, `type`, `disease`
- Log parent-child relationship between chapter/section/type/disease
- Handle failures gracefully: log to `icd10_ingestion_errors.csv`, continue with remaining codes

### Rate Limiting & Resilience

- Minimum 200ms delay between requests (KCB endpoint is reverse-engineered, no official SLA)
- Retry with exponential backoff on transient failures
- Cache raw responses with version/timestamp
- Log every failure with code, reason, timestamp, attempt count

### Scope

- Ingest ICD-10 3-character codes (chapter level, ~26 chapters) and 4-character codes (category/type level, ~14,400 categories) for both languages
- Do NOT attempt to ingest ICD-10 5+ character sub-codes in this phase — that is a future enhancement
- Do NOT attempt to ingest ICD-10 2026 revision (ICD-11) in this phase

### CLI Interface

- Follow existing `--mock` smoke test pattern from v1.0 (e.g., `src/llm/classifier.py`, `src/asr/transcriber.py`)
- `--mock` mode: fetch 5 codes only, write sample output, verify schema
- `--full` mode: fetch all codes, write complete inventory
- Support `--resume` to continue from last failure

### Output Schema

Each record in `icd10_dual_language.jsonl` must contain:
```json
{
  "code": "I10",
  "level": "type",
  "label_en": "Essential hypertension",
  "label_vi": "Tăng huyết áp nguyên phát",
  "chapter_code": "IX",
  "chapter_label_en": "Diseases of the circulatory system",
  "chapter_label_vi": "Bệnh của hệ tuần hoàn",
  "parent_code": "I00-I99",
  "source": "kcb_icd10_tt06",
  "source_url": "https://.../api/ICD10/search/I10?lang=en&vol1=1&vol3=0&html=true",
  "fetched_at": "2026-06-19T00:00:00+07:00"
}
```

</decisions>

<canonical_refs>

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Context

- `.planning/STATE.md` — Project decisions and history
- `.planning/PROJECT.md` — Core value, requirements, constraints, key decisions
- `.planning/REQUIREMENTS.md` — FR1 requirements (FR1-01 through FR1-06)
- `.planning/ROADMAP.md` — Phase 6a goal, success criteria, dependencies
- `docs/prd/PRD_VietMedVoice_Phase2_Enhancement_v1.1.md` — Full PRD (FR1 section, Section 5.2 ICD-10 endpoint requirement, Section 8.1 data schema)
- `docs/icd10-api-kcb.md` — KCB ICD-10 API specification (verified accurate)

### Research

- `.planning/research/RESEARCH.md` — Consolidated research synthesis
- `.planning/research/STACK.md` — Technology stack: httpx, BeautifulSoup4, lxml, tenacity for ICD-10 ingestion
- `.planning/research/FEATURES.md` — FR1 feature spec details
- `.planning/research/ARCHITECTURE.md` — System architecture and data flow
- `.planning/research/PITFALLS.md` — 12 critical pitfalls (FR1-related: ICD-10 EN/VI join by label, endpoint fragility)

### Existing Patterns

- `.planning/codebase/CONVENTIONS.md` — Project conventions
- `.planning/codebase/STRUCTURE.md` — Project structure
- `.planning/codebase/STACK.md` — v1.0 tech stack
- `.planning/codebase/ARCHITECTURE.md` — v1.0 architecture
- `.planning/codebase/INTEGRATIONS.md` — Integration patterns
- `.planning/codebase/TESTING.md` — Testing conventions

### No external specs — requirements fully captured in decisions above

</canonical_refs>

<specifics>

## Specific Ideas

- KCB endpoint base URL: reverse-engineered, needs verification. Start with known ICD-10 codes for common diseases (I10, E11, J18, K29, N39, etc.) as pilot set
- Parse ISO 3166-1 alpha-2 codes for chapters: I → "IX", II → "X", etc. or use string position
- HTML parsing: look for `<span class="chuhoa">` or similar structural elements in the HTML response
- ICD-10 chapters: 26 chapters, codes A00–Z99, with chapter labels in EN and VI
- ICS-10 4-char codes: range ~14,400 codes (A00–Z99.xx), should be feasible in a single session with rate limiting
- Use `httpx` with async client for concurrent EN/VI queries (but rate-limit to 200ms per request)

</specifics>

<deferred>

## Deferred Ideas

- Ingest ICD-10 5+ character sub-codes (detailed clinical modifications) — deferred to future phase
- Ingest ICD-11 in parallel — deferred, ICD-10 is the backbone for v1.1
- Attempt Vietnamese keyword search as fallback when code search fails — deferred, code search is preferred
- Automatic retry of failed codes in a second pass after initial pass completes — could be added post-6a

</deferred>

---

*Phase: 6a-icd-10-dual-language-ingestion*
*Context gathered: 2026-06-19 via PRD Express Path + domain research synthesis*
