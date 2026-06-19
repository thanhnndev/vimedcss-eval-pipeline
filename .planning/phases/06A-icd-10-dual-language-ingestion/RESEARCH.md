# Phase 6a: ICD-10 Dual-Language Ingestion — Research

**Phase:** 6a
**Research date:** 2026-06-19
**Source:** Consolidated from `.planning/research/RESEARCH.md`, `STACK.md`, `FEATURES.md`, `PITFALLS.md`

---

## Executive Summary

Phase 6a ingests ICD-10 as a bilingual disease backbone. The critical technical challenge is reliable EN/VI join by `code` (not label text) and resilient endpoint access. Technology choices are well-established (httpx + BeautifulSoup4 + lxml). The biggest risks are endpoint fragility and Vietnamese keyword search unreliability.

**Confidence:** HIGH
**Risk level:** MEDIUM (endpoint stability)

---

## Technology Stack (FR1-relevant)

| Component | Choice | Version | Rationale |
|-----------|--------|---------|-----------|
| HTTP client | httpx | ≥0.28.0 | Async support for concurrent EN/VI queries |
| HTML parser | BeautifulSoup4 | ≥4.13.0 | Robust HTML tree parsing |
| XML parser | lxml | ≥5.0.0 | Faster HTML parsing backend for BeautifulSoup |
| Retry/backoff | tenacity | ≥8.3.0 | Exponential backoff on transient failures |
| CLI | click | ≥8.2.0 | Consistent with v1.0 pipeline |
| Data validation | pydantic | ≥2.0 | Schema validation for output records |
| Progress | tqdm | ≥4.67.0 | Progress bars for large code batch ingestion |

**No async-first required** — synchronous with rate limiting is safer for this endpoint.

---

## KCB ICD-10 API Details

**Base URL pattern:**
```
/api/ICD10/search/<query>?lang=vi|en&vol1=1&vol3=0&html=true
```

**Known patterns:**
- `query=I10` → returns ICD-10 code I10 record
- `lang=en` → English labels
- `lang=vi` → Vietnamese labels
- `vol1=1` → include volume 1 (clinical)
- `vol3=0` → exclude volume 3 (Alphabetic index)
- `html=true` → return HTML-formatted content in `html` field

**Response structure (observed):**
- JSON outer wrapper
- `html` field contains HTML with chapter/section/type/disease hierarchy
- Look for structural elements like `<span class="chuhoa">` for chapter headers

**Rate limiting:** Minimum 200ms between requests

---

## Key Findings

### 1. Join by Code, Not Label

The most critical pitfall (from PITFALLS.md, Pitfall #1):
- English "Essential hypertension" ≠ Vietnamese "Tăng huyết áp nguyên phát"
- Merging by label text guarantees empty results
- Code is the stable join key: `"code": "I10"` in both EN and VI responses

### 2. Vietnamese Search Is Unreliable

From `docs/icd10-api-kcb.md` (verified accurate):
- Vietnamese free-text search is inconsistent across code ranges
- English keyword search is more reliable
- Prefer code-based queries when possible

### 3. Endpoint Stability

KCB endpoint is reverse-engineered with no official SLA. Required mitigations:
- Cache raw responses with version/timestamp
- Exponential backoff retry (tenacity)
- Log every failure with code, reason, timestamp, attempt count
- `--resume` flag to continue from last failure

### 4. Scope: Chapter + Type Level Only

ICD-10 has ~26 chapters (3-char parent codes) and ~14,400 type-level categories (4-char codes). Sub-category codes (5+ chars) are deferred to a future phase.

---

## Validation Architecture

### Smoke Test (`--mock`)

1. Fetch 5 known codes (e.g., I10, E11, J18, K29, N39)
2. Verify EN and VI responses both contain the code
3. Verify join by code produces correct bilingual records
4. Verify HTML parsing extracts chapter/section/type/disease
5. Verify schema: all required fields present
6. Write to `data/icd10/mock/icd10_sample.csv`

### Full Run (`--full`)

1. Fetch all ~14,400 ICD-10 codes (4-char) in both languages
2. Rate-limit to 200ms per request (~48 minutes for full run)
3. Retry failed codes up to 3 times with exponential backoff
4. Write batch to CSV/JSONL incrementally (every 100 codes)
5. Final validation: count records, verify no duplicate codes, check chapter coverage

### Output Validation

- Every record: `code`, `level`, `label_en`, `label_vi`, `chapter_code`, `chapter_label_en`, `chapter_label_vi`, `parent_code`, `source`, `source_url`, `fetched_at`
- All fields non-null except `parent_code` (null for chapter-level codes)
- No duplicate `code` values
- All chapter codes map to known ICD-10 chapters

---

## Risks and Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| KCB endpoint returns unexpected HTML structure | Medium | Parse conservatively; log parsing failures; fallback to raw text |
| Rate limit causes timeouts | Medium | 200ms delay; tenacity retry with backoff |
| Vietnamese search fails for some codes | High | Prefer code search; fallback to English search; log failures |
| EN/VI join produces empty results for some codes | High | Verify join on known codes first; log and report |
| Large batch takes too long | Low | Show progress bar; support `--resume` |

---

## Open Questions

1. **KCB endpoint base URL:** Needs verification. Start with known codes (I10, E11, J18) as pilot.
2. **HTML structure:** Need to inspect actual HTML from a sample code response to confirm parsing selectors.
3. **Chapter code format:** Are chapter codes "IX" or "9" or something else? Need to verify from sample response.

---

## Existing Patterns to Follow

From v1.0 codebase:

- `--mock` smoke test pattern: `src/llm/classifier.py`, `src/asr/transcriber.py`
- Output to `data/` subdirectory with CSV + JSONL
- Error logging to CSV with timestamp, code, reason
- Report generation to `reports/` directory

---

## Verification Checklist

From PITFALLS.md (FR1-relevant items):

- [ ] EN/VI join uses `code` field, not `label_en` or `label_vi`
- [ ] Retry with exponential backoff on HTTP failures
- [ ] Minimum 200ms rate limit between requests
- [ ] Failed codes logged with reason and timestamp
- [ ] HTML parsing handles missing/null fields gracefully
- [ ] `--mock` smoke test validates schema before full run
- [ ] `chapter_code` is a valid ICD-10 chapter code (A-Z pattern)
- [ ] No fabricated data; every record traced to API response
