# Phase 6b: Medical Term Inventory Extended — Research

**Researched:** 2026-06-22
**Domain:** Medical terminology ingestion, normalization, classification, and multi-source inventory construction
**Confidence:** MEDIUM-HIGH

---

## Summary

Phase 6b builds a comprehensive medical term inventory from the ICD-10 bilingual disease backbone (Phase 6a output) plus supplementary lexicons for drug, lab test, procedure, abbreviation, hormone, biomarker, device, unit, and dosage terms. The critical challenges are: (1) sourcing freely accessible, license-compatible medical lexicons, (2) designing a normalization strategy that handles medical-specific edge cases, (3) classifying terms by entity type and medical domain without hallucination, and (4) tracking provenance so every term is traceable to a verified source.

The recommended approach uses NLM/RxNorm API for drugs, the existing ViMedCSS domain vocabulary as a seed for lab tests and abbreviations, and LLM-assisted classification for entity_type and medical_domain with mandatory human review. No single authoritative source covers all 9 entity types — the inventory is inherently multi-source.

**Primary recommendation:** Build a `src/term_inventory/` module with ingestion adapters per source type, a normalization pipeline using unicode-aware case folding + medical abbreviation expansion, LLM-assisted classification (reusing Phase 2's `TermClassifier` schema), and a strict provenance-tracking CSV schema.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| ICD-10 disease backbone load | API / Backend | — | CSV/JSONL file read; no API call needed |
| Drug lexicon ingestion (RxNorm API) | API / Backend | — | HTTP GET to NLM RxNorm; stateless, rate-limited |
| Lab/procedure/abbreviation ingestion | API / Backend | — | HTTP GET to open APIs; manual CSV curation for abbreviations |
| Term normalization | API / Backend | — | Pure string transformation; no model needed |
| Entity type classification | API / Backend (LLM) | — | OpenAI structured output; existing Phase 2 pattern |
| Medical domain classification | API / Backend (LLM) | — | OpenAI structured output; existing Phase 2 pattern |
| Provenance tracking | API / Backend | — | Column in output CSV |
| Human review queue | Browser / Client | — | Manual review; CSV-based output |

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `pandas` | ≥3.0 | CSV/JSONL tabular operations | Existing project dependency; handles large inventories |
| `httpx` | ≥0.28 | HTTP client for RxNorm API | Existing project dependency; async support for batch ingestion |
| `pydantic` | ≥2.13 | JSON schema validation for inventory records | Existing project dependency; matches Phase 2 schema pattern |
| `openai` | ≥2.31 | Structured output for entity/domain classification | Existing project dependency; reuse `TermClassifier` schema from Phase 2 |
| `tenacity` | ≥8.4 | Retry with exponential backoff for API calls | Consistent with Phase 6a patterns |
| `tqdm` | ≥4.66 | Progress bars for large lexicon ingestion | Consistent with Phase 6a patterns |

### Supporting (existing project dependencies)
| Library | Purpose | When to Use |
|---------|---------|-------------|
| `src/llm/schemas.py` | `EntityCategory`, `MedicalDomain`, `MedicalSpecialty` enums | Reuse existing taxonomy for classification |
| `src/shared/logging.py` | Structured logger | All ingestion/adapter modules |
| `src/shared/config.py` | `AppConfig` YAML loading | Config-driven ingestion |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| RxNorm API for drugs | DrugBank (commercial), ATC classification (limited VI access) | RxNorm is free, no license, NLM-maintained |
| LLM for entity classification | Rule-based keyword matching (fragile for medical terms) | LLM with Pydantic schema is more robust; existing Phase 2 infrastructure |
| Manual abbreviation list | UMLS (steep learning curve, license required) | ViMedCSS seed + NLM abbreviation resources is pragmatic |

**Installation:**
```bash
pip install httpx tenacity
# openai, pandas, pydantic, tqdm already in project dependencies
```

---

## Architecture Patterns

### System Architecture Diagram

```
[ICD-10 Bilingual CSV]
      │
      ▼
[InventoryBuilder] ──── ingests ──── [Disease Backbone Loader]
      │                                    │
      ├─── RxNorm API (drugs)             │
      ├─── NLM/MeSH (lab tests, hormones, biomarkers)
      ├─── Manual curated lists (abbreviations, units, dosage)
      ├─── openFDA Device API (devices)
      └─── ViMedCSS seed terms (procedure, anatomy)
              │
              ▼
      [NormalizationPipeline]
      - Unicode NFC normalization
      - Case folding
      - Punctuation stripping
      - Medical abbreviation expansion
      - Synonym normalization
              │
              ▼
      [DeduplicationEngine]
      - Canonical form grouping
      - Multi-source conflict resolution
              │
              ▼
      [TermClassifier] (LLM, Phase 2 pattern)
      - entity_type assignment
      - medical_domain assignment
      - review_status flagging
              │
              ▼
      [OutputFiles]
      - medical_term_inventory.csv
      - term_sources.csv
      - term_normalization_map.csv
      - human_review_terms.csv
```

### Recommended Project Structure
```
src/
├── term_inventory/          # [NEW] Phase 6b
│   ├── __init__.py
│   ├── cli.py              # CLI subcommand: build-inventory
│   ├── builder.py          # InventoryBuilder orchestrator
│   ├── loaders/
│   │   ├── icd10_backbone.py  # Load Phase 6a output
│   │   ├── rxnorm_loader.py   # RxNorm API drug ingestion
│   │   ├── lab_loader.py      # NLM lab test ingestion
│   │   ├── abbreviation_loader.py  # Manual abbreviation lists
│   │   ├── device_loader.py    # openFDA device ingestion
│   │   └── seed_loader.py      # ViMedCSS seed terms
│   ├── normalizer.py        # Normalization pipeline
│   ├── deduplicator.py      # Cross-source deduplication
│   ├── classifier.py        # LLM classification (reuses Phase 2)
│   ├── schemas.py           # Inventory record Pydantic models
│   └── reporter.py          # Inventory report generator
```

### Pattern 1: Multi-Source Loader Adapter

Each lexicon source gets its own loader class following a common interface. This isolates API-specific logic and makes testing easier.

```python
# Source: Pattern from existing src/terms/external.py + Phase 6a icd10_ingestion/ patterns
from abc import ABC, abstractmethod

class BaseLoader(ABC):
    REQUIRED_COLS = ["term_original", "entity_type", "source_name"]

    @abstractmethod
    def load(self) -> pd.DataFrame:
        """Return DataFrame with standard columns."""
        pass

class RxNormLoader(BaseLoader):
    """Ingest drug terms from NLM RxNorm API."""
    BASE_URL = "https://rxnav.nlm.nih.gov/REST"

    def load(self) -> pd.DataFrame:
        rows = []
        for drug_name in self._get_drug_list():
            resp = httpx.get(f"{self.BASE_URL}/drugs.json", params={"name": drug_name}, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            for group in data.get("drugGroup", []):
                for concept in group.get("conceptGroup", []):
                    for c in concept.get("conceptProperties", []):
                        rows.append({
                            "term_original": c["name"],
                            "term_normalized": c["name"].lower().strip(),
                            "entity_type": "drug",
                            "source_name": "rxnorm",
                            "source_url": f"https://rxnav.nlm.nih.gov/RxNorm/drugs?name={drug_name}",
                            "rxnorm_rxcui": c.get("rxcui", ""),
                        })
        return pd.DataFrame(rows)
```

### Pattern 2: Normalization Map

Track every transformation so downstream matching is explainable.

```python
# Source: Informed by existing src/terms/external.py _load_inventory deduplication
def build_normalization_map(terms_df: pd.DataFrame) -> pd.DataFrame:
    """Build a map from raw → canonical forms."""
    rows = []
    for _, row in terms_df.iterrows():
        original = str(row.get("term_original", ""))
        normalized = normalize_term(original)
        if original != normalized:
            rows.append({
                "raw_form": original,
                "normalized_form": normalized,
                "transformation": "lowercase+strip+punctuation",
            })
    return pd.DataFrame(rows)
```

### Pattern 3: LLM-Assisted Classification with Provenance

Reuse the Phase 2 `TermClassifier` but wrap each loader's output with provenance metadata before classification.

```python
# Source: Existing src/llm/classifier.py pattern extended with provenance
def classify_with_provenance(
    terms_df: pd.DataFrame,
    source_name: str,
    classifier: TermClassifier,
) -> pd.DataFrame:
    """Classify terms and attach source provenance."""
    for _, row in terms_df.iterrows():
        classification = classifier.classify_single(row["term_normalized"])
        row["entity_type"] = classification.primary_entity_category.value
        row["medical_domain"] = classification.primary_medical_domain.value
        row["source_name"] = source_name
        row["review_status"] = "verified" if classification.confidence >= 0.8 else "needs_review"
    return terms_df
```

### Anti-Patterns to Avoid

- **Generating terms from LLM without sourcing:** LLM output is a candidate pool only. Every term without a named external source must be flagged `llm_generated_candidate: true` and `review_status: not_verified`.
- **Deduplicating across entity types:** A term can legitimately appear in multiple entity types (e.g., "insulin" as drug and biomarker). Deduplication should be within entity_type, not global.
- **Merging by normalized string across languages:** "metformin" (EN) and "metformin" (VI transliteration) are the same term. But "hypertension" (EN) and "tăng huyết áp" (VI) are NOT the same — merge only when the normalized string matches, not when translations differ.
- **Skipping source attribution:** Every term row must have `source_name`. Empty source is a data integrity violation.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Drug term normalization | Custom drug name cleaning | RxNorm API canonical names | RxNorm already normalizes "Metformin 500mg" → "Metformin"; custom regex misses edge cases |
| Medical entity classification | Rule-based keyword matching | LLM structured output with Pydantic schema | Medical ambiguity (e.g., "scan" = CT scan procedure vs. diagnostic lab) requires context; Phase 2 infrastructure exists |
| ICD-10 EN/VI dual-language | Custom scraping | Phase 6a output (icd10_dual_language.csv) | Already implemented; join by code is correct |
| HTTP retry logic | Custom retry with sleep | `tenacity.retry` | Exponential backoff, jitter, stop-after-delay already implemented in Phase 6a |

**Key insight:** Medical term inventory is fundamentally a data integration problem, not a machine learning problem. The quality of the output depends on the quality of the source data and the rigor of the provenance tracking.

---

## Common Pitfalls

### Pitfall 1: LLM-Generated Terms Without Source Attribution
**What goes wrong:** A large pool of LLM-suggested terms gets marked as `verified` because they look plausible, but they have no external source.
**Why it happens:** Pressure to increase inventory coverage; LLM output is easy to generate.
**How to avoid:** Every term must have a `source_name` column. LLM-generated candidates get `source_name: llm_generated` and `review_status: not_verified`. The inventory CSV has a filter: `include_in_coverage_audit` = `True` only for `review_status: verified`.
**Warning signs:** `source_name` column is empty for >5% of terms.

### Pitfall 2: Normalization Collisions Across Languages
**What goes wrong:** "metformin" (EN) and "Metformin" (uppercase) deduplicate correctly. But "β-blocker" (Greek beta) and "beta-blocker" (ASCII) are the same concept but normalize to different strings.
**Why it happens:** Basic lowercase + strip normalization misses Unicode normalization and medical symbol equivalence.
**How to avoid:** Apply Unicode NFC normalization (`unicodedata.normalize("NFC", s)`) before any comparison. Add a Greek-to-ASCII mapping for common medical symbols (β→beta, α→alpha, μ→mu). Log collision candidates for human review.
**Warning signs:** Normalization map has <50% of terms as unchanged (suggests over-aggressive or under-aggressive normalization).

### Pitfall 3: Treating ICD-10 as Sufficient for All Entity Types
**What goes wrong:** The inventory is ICD-10-only because other sources are hard to find, leading to an entity_type distribution that is 90% disease.
**Why it happens:** ICD-10 is well-structured and freely available; other lexicons require API keys, licenses, or manual curation.
**How to avoid:** Design the 9 entity types from the start. Allocate at least one loader per entity type. RxNorm for drugs, NLM for lab tests, manual list for abbreviations, openFDA for devices. If a loader returns 0 rows, log a warning and set `entity_type` to `unknown` with `review_status: not_verified`.
**Warning signs:** `entity_type` distribution shows only disease and unknown categories.

### Pitfall 4: LLM Classification Without Review Gate
**What goes wrong:** LLM classifies all terms with high confidence because the prompt is too permissive. `needs_human_review` is always `False`.
**Why it happens:** The LLM is prompted to classify into valid categories even when genuinely uncertain.
**How to avoid:** Set confidence threshold at 0.80 (matching Phase 2 `confidence_threshold_review`). Below this threshold, `needs_human_review` must be `True`. The `human_review_terms.csv` must exist and have rows.
**Warning signs:** `needs_human_review` count is 0 for a batch of >100 terms.

---

## Code Examples

### Multi-Source Provenance Tracking Schema

```python
# Source: Extended from existing src/terms/external.py REQUIRED_INVENTORY_COLS
from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum

class EntityType(str, Enum):
    DISEASE = "disease"
    DRUG = "drug"
    LAB_TEST = "lab_test"
    PROCEDURE = "procedure"
    ANATOMY = "anatomy"
    SYMPTOM = "symptom"
    ABBREVIATION = "abbreviation"
    HORMONE = "hormone"
    BIOMARKER = "biomarker"
    PATHOGEN = "pathogen"
    DEVICE = "device"
    UNIT = "unit"
    DOSAGE = "dosage"
    UNKNOWN = "unknown"

class ReviewStatus(str, Enum):
    VERIFIED = "verified"
    LLM_CANDIDATE = "llm_candidate"
    NOT_VERIFIED = "not_verified"
    NEEDS_REVIEW = "needs_review"

class MedicalTermRecord(BaseModel):
    term_id: str = Field(..., description="Unique term ID, e.g. term_000001")
    term_original: str = Field(..., description="Original form as ingested from source")
    term_normalized: str = Field(..., description="Normalized form for matching")
    entity_type: EntityType = Field(..., description="Primary entity type")
    medical_domain: Optional[str] = Field(None, description="Medical domain, e.g. cardiology")
    source_name: str = Field(..., description="Named source: rxnorm, icd10, vimedcss_seed, llm_generated, etc.")
    source_url: Optional[str] = Field(None, description="URL or reference to source")
    icd10_code: Optional[str] = Field(None, description="ICD-10 code if disease entity")
    is_code_switch_candidate: bool = Field(True, description="Whether this term can appear in EN/VI code-switching")
    review_status: ReviewStatus = Field(..., description="Verification status")
    llm_generated_candidate: bool = Field(False, description="True if sourced from LLM without external verification")
    fetched_at: str = Field(..., description="ISO timestamp of ingestion")
```

### RxNorm Drug Ingestion

```python
# Source: NLM RxNorm API documentation (https://lhncbc.nlm.nih.gov/RxNav/APIs/RxNormAPIs.html)
import httpx
import time

def fetch_rxnorm_drugs(drug_names: list[str], delay_ms: int = 200) -> list[dict]:
    """Fetch drug concepts from RxNorm API by name.
    
    RxNorm API is free, no license required.
    Base URL: https://rxnav.nlm.nih.gov/REST
    """
    results = []
    for name in drug_names:
        url = "https://rxnav.nlm.nih.gov/REST/drugs.json"
        resp = httpx.get(url, params={"name": name}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        for group in data.get("drugGroup", []):
            for concept_group in group.get("conceptGroup", []):
                for concept in concept_group.get("conceptProperties", []):
                    results.append({
                        "term_original": concept["name"],
                        "rxcui": concept.get("rxcui", ""),
                        "tty": concept.get("tty", ""),  # SCD=Semantically grouped drug, IN=Ingredient
                        "source": "rxnorm",
                    })
        time.sleep(delay_ms / 1000)  # Rate limit
    return results
```

### NLM ICD-10-CM Search for Lab/Procedure Terms

```python
# Source: NLM Clinical Table Search Service (https://clinicaltables.nlm.nih.gov/apidoc/icd10cm/v3/doc.html)
def search_icd10cm(query: str, limit: int = 10) -> list[dict]:
    """Search ICD-10-CM codes and descriptions for lab/procedure context.
    
    Base URL: https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search
    """
    url = "https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search"
    resp = httpx.get(url, params={
        "sf": "code,name",
        "terms": query,
        "limit": limit,
    }, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    results = []
    if data[0] > 0:  # data[0] is match count
        for item in data[3]:  # data[3] is the list of [code, name] pairs
            results.append({"code": item[0], "name": item[1]})
    return results
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|-----------------|--------------|--------|
| ICD-10-only term inventory | Multi-source (ICD-10 + RxNorm + NLM + openFDA + manual lists) | Phase 6b | Covers all 9 entity types; coverage audit meaningful |
| LLM output as verified terms | LLM output as `llm_generated_candidate` with `review_status: not_verified` | Phase 6b | Data integrity preserved; no fabricated terms in coverage stats |
| Case-insensitive exact match only | Unicode NFC + medical symbol normalization + synonym mapping | Phase 6b | Matches "β-blocker" to "beta-blocker"; fewer false negatives |
| No entity type classification | EntityType enum (13 categories) with LLM-assisted classification | Phase 2 (Phase 6b extends) | Enables coverage audit by entity type, not just disease |
| Single-source deduplication | Cross-source deduplication with conflict resolution and provenance | Phase 6b | "metformin" appearing in both RxNorm and ViMedCSS counts once |

**Deprecated/outdated:**
- **Phase 3 mock inventory:** The `build_mock_inventory()` fixture from Phase 3 produced 5 synthetic terms. Phase 6b replaces this with real multi-source ingestion. The mock inventory pattern is retained only for `--mock` smoke testing in Phase 6b.
- **Single entity_category labels:** Phase 2 used `entity_category` (singular). Phase 6b uses `entity_type` per FR2-04 schema with a flat enum. The Phase 2 `EntityCategory` enum maps to the Phase 6b `EntityType` enum.

---

## Assumptions Log

> List all claims tagged `[ASSUMED]` in this research. The planner and discuss-phase use this section to identify decisions that need user confirmation before execution.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | RxNorm API at `rxnav.nlm.nih.gov/REST` returns free drug data without API key | Standard Stack | RxNorm requires no license per NLM docs, but the endpoint URL pattern may differ from assumed |
| A2 | NLM ICD-10-CM search API covers lab test and procedure terms sufficiently | Code Examples | ICD-10-CM is primarily disease codes; lab tests and procedures may not be well-covered |
| A3 | The existing `EntityCategory` enum from Phase 2 maps cleanly to FR2-04's `entity_type` enum | Standard Stack | FR2-04 lists 13 entity types; Phase 2 has ~14 categories with different names — planner must reconcile |
| A4 | ViMedCSS `cs_terms_list` provides sufficient seed terms for abbreviations and procedure entity types | Architecture Patterns | ViMedCSS may not cover all needed abbreviation types; fallback manual list may be needed |
| A5 | LLM classification via `TermClassifier` can handle batch sizes of 50–100 terms per API call | Code Examples | Token limits may require smaller batches; cost estimation may be off |

**If this table is empty:** All claims in this research were verified or cited — no user confirmation needed.

---

## Open Questions

1. **FR2-04 entity_type vs Phase 2 EntityCategory enum mismatch**
   - What we know: FR2-04 specifies 13 entity types (disease, drug, lab_test, procedure, anatomy, symptom, abbreviation, hormone, biomarker, pathogen, device, unit, dosage). Phase 2's `EntityCategory` enum has ~14 categories with different naming.
   - What's unclear: Should the planner create a new `EntityType` enum or extend the existing `EntityCategory`? The schema must match FR2-04 exactly.
   - Recommendation: Create a new `EntityType` enum in `src/term_inventory/schemas.py` that matches FR2-04's 13 types exactly. Add a mapping table for Phase 2 backward compatibility.

2. **Drug term scope: RxNorm alone vs RxNorm + ATC**
   - What we know: RxNorm covers US prescription/OTC drugs. ATC (Anatomical Therapeutic Chemical) classification covers international drug categorization with VI translations.
   - What's unclear: Is ATC needed for VI coverage, or is RxNorm + ViMedCSS seed sufficient?
   - Recommendation: Start with RxNorm only. Add ATC only if RxNorm coverage of VI medical CS terms is insufficient (measure after Phase 6c coverage audit).

3. **Abbreviation expansion strategy**
   - What we know: Medical abbreviations (ECG, MRI, HbA1c) are high-frequency CS terms. ViMedCSS already has some.
   - What's unclear: Should abbreviations be expanded (ECG → electrocardiogram) or kept as-is with `is_abbreviation: true`?
   - Recommendation: Keep original form AND store expanded form as `canonical_term`. Both are useful: original for ASR matching, expanded for downstream conversation generation.

4. **LLM classification cost estimation**
   - What we know: Phase 2's `TermClassifier` processes terms in batches of 50. Phase 6b may ingest 10,000+ terms from all sources.
   - What's unclear: How many terms need LLM classification? Only new terms (not from verified sources) or all terms?
   - Recommendation: Only LLM-classify terms where `source_name` is not a verified authoritative source. ICD-10, RxNorm, openFDA terms already have entity metadata from their source. LLM classification is needed for ViMedCSS seed terms and any `llm_generated_candidate` pool.

5. **Vietnamese term ingestion**
   - What we know: ICD-10 has VI labels from Phase 6a. RxNorm is EN-only.
   - What's unclear: Should supplementary lexicons include VI terms? The coverage audit (Phase 6c) matches ViMedCSS EN terms against the inventory — VI labels are for human readability only.
   - Recommendation: Store VI labels where available (ICD-10 backbone). For other sources, VI labels are optional. Focus FR2 on EN term coverage for ASR matching.

---

## Environment Availability

> Step 2.6: SKIPPED (no external dependencies beyond existing project environment)

Phase 6b uses only:
- Existing project dependencies (pandas, httpx, pydantic, openai, tenacity, tqdm)
- Public APIs (RxNorm, NLM, openFDA) — no installation required
- Phase 6a output file (`data/icd10/icd10_dual_language.csv`) — local file

No new package installations, external tools, or runtimes are required.

---

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FR2-01 | Ingest ICD-10 dual-language inventory as disease backbone | Phase 6a output; `icd10_dual_language.csv` load pattern documented |
| FR2-02 | Ingest supplementary lexicons (drug, lab test, procedure, abbreviation lists) from approved sources | RxNorm API (drug), NLM ICD-10-CM search (lab), ViMedCSS seed + manual lists (abbreviation), openFDA (device) |
| FR2-03 | Normalize and deduplicate terms; create `term_normalization_map.csv` | Unicode NFC normalization, case folding, medical symbol mapping, cross-source deduplication |
| FR2-04 | Classify each term by `entity_type` (13 types) and `medical_domain` | LLM structured output reusing Phase 2 `TermClassifier` schema; new `EntityType` enum per FR2-04 |
| FR2-05 | Attach source provenance to every term; flag `llm_generated_candidate` terms as `not_verified` | `source_name`, `review_status`, `llm_generated_candidate` columns in output schema |
| FR2-06 | Export `data/terms/medical_term_inventory.csv`, `term_sources.csv`, `term_normalization_map.csv`, `human_review_terms.csv` | Output schema defined; file naming per PRD Section 10 folder structure |

---

## Security Domain

> Skip this section — Phase 6b is a data ingestion and normalization pipeline with no user input, authentication, or network-facing endpoints.

No ASVS categories apply. No user-controlled input is processed. Only static lexicon files and public API responses are ingested.

---

## Sources

### Primary (HIGH confidence)
- [NLM RxNorm API documentation](https://lhncbc.nlm.nih.gov/RxNav/APIs/RxNormAPIs.html) — Drug API endpoints, no-license requirement
- [NLM Clinical Table Search Service](https://clinicaltables.nlm.nih.gov/apidoc/icd10cm/v3/doc.html) — ICD-10-CM search API
- [openFDA API](https://open.fda.gov/apis/) — Medical device terminology
- Existing Phase 2 codebase (`src/llm/classifier.py`, `src/terms/external.py`) — Established patterns

### Secondary (MEDIUM confidence)
- [LOINC API documentation](https://loinc.org/downloads/) — Laboratory test terminology (BETA API, requires free registration)
- [WHO ICD-11 API](https://icd.who.int/icdapi/docs2/APIDoc-Version2/) — Future ICD expansion reference
- [HORDB peptide hormone database](http://hordb.cpu-bioinfor.org/) — Hormone/biomarker source (open-access)
- Web search synthesis on UMLS, RxNorm, LOINC terminology services

### Tertiary (LOW confidence)
- MedDRA (commercial license, not verified for this project)
- DrugBank (commercial license, not verified)
- Specific API endpoint URL patterns (may differ from assumed patterns)

---

## Metadata

**Confidence breakdown:**
- Standard Stack: MEDIUM-HIGH — verified existing project dependencies; RxNorm/NLM API patterns confirmed by official documentation
- Architecture: HIGH — follows existing Phase 2/3 patterns; multi-source adapter pattern well-established
- Pitfalls: MEDIUM — based on Phase 2 experience and medical NLP literature; specific threshold values need validation

**Research date:** 2026-06-22
**Valid until:** 2026-07-22 (30 days; medical terminology standards are stable; API patterns are unlikely to change)
