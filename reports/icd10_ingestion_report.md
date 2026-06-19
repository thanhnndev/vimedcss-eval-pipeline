# ICD-10 Dual-Language Ingestion Report

## Ingestion Metadata

| Field | Value |
| --- | --- |
| Generated at | 2026-06-19T08:25:19Z |
| Source | KCB ICD-10 API (https://ccs.whiteneuron.com/api/ICD10) |
| Total records written | 5 |
| Total errors | 2 |
| Error rate | 28.57% |

## Chapter Coverage

| Chapter Label (EN) | Record Count |
| --- | --- |

## Level Distribution

| Level | Count |
| --- | --- |
| chapter | 0 |
| section | 0 |
| type | 0 |
| disease | 0 |

## Error Summary

**Total errors:** 2

| Error Type | Count |
| --- | --- |
| `http_error` | 2 |

### Top Error Messages (examples)

| Code | Language | Error Type | Message |
| --- | --- | --- | --- |
| `E11` | en | `http_error` | Client error '400 Bad Request' for url 'https://ccs.whiteneuron.com/api/ICD10/se |
| `K29` | en | `http_error` | Client error '400 Bad Request' for url 'https://ccs.whiteneuron.com/api/ICD10/se |

## Data Quality Notes

- **Join success rate:** 60.0% (EN+VI records joined by `code` field)
- **Language coverage:** All records have both EN and VI labels when join succeeds.
- **Join key:** Code field only — labels are never matched by text similarity.
- **Error handling:** Failed fetches logged to `icd10_ingestion_errors.csv` with code, language, error_type, and attempt count.

## Downstream Usage

This bilingual ICD-10 inventory is consumed by the following phases:

- **FR1 (Phase 06A):** ICD-10 dual-language ingestion (this pipeline).
- **FR3:** ViMedCSS ICD-10/non-ICD coverage audit — cross-reference ViMedCSS
  transcript terms against the `code` field for disease coverage analysis.
- **FR4:** VietMed feasibility audit — use ICD-10 taxonomy to map disease
  categories across datasets.

## Files Produced

- `data/icd10/icd10_dual_language.jsonl` — 5 bilingual records (JSONL)
- `data/icd10/icd10_dual_language.csv` — 5 bilingual records (CSV)
- `data/icd10/icd10_ingestion_errors.csv` — 2 error records

