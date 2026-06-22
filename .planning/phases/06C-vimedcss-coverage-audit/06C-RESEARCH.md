# Phase 6C: ViMedCSS Coverage Audit — Research

**Researched:** 2026-06-22
**Domain:** Medical term coverage measurement and gap analysis
**Confidence:** HIGH

---

## Summary

Phase 6C measures how much of ViMedCSS's code-switching (CS) term coverage is explained by the medical term inventory built in Phase 6B. The phase matches ~841 unique CS terms from `cs_terms_inventory.csv` against the ~27-term inventory from `medical_term_inventory.csv` (Phase 6B output), computes coverage rates grouped by entity type, medical domain, split, and topic, exports missing/hard term lists, and produces a Vietnamese coverage report with metric provenance tiers.

The phase is essentially a **re-implementation of Phase 3's `ExternalReferenceMatcher`** with two critical differences: (1) the reference inventory is now the real Phase 6B multi-source inventory (not a mock), and (2) the match output and report must include confidence tier provenance (local_verified / hf_reported / paper_reported). The existing `src/terms/external.py` pattern provides the canonical architecture to follow; the new `src/coverage_audit/` module extends it.

**Primary recommendation:** Build a `src/coverage_audit/` module mirroring Phase 3's `ExternalReferenceMatcher` but reading from Phase 6B's inventory schema (`term_normalized`, `entity_type`, `source_name`, `review_status`). Reuse the Phase 3 matching logic (case-insensitive exact match) and extend the report generator with provenance tier tracking and Vietnamese narrative.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Term matching (exact) | API / Backend | — | Pure string set lookup; no model needed |
| Coverage rate computation | API / Backend | — | Pandas groupby aggregations |
| Missing/hard term export | API / Backend | — | CSV write; extends Phase 3 pattern |
| Vietnamese report generation | API / Backend | — | Template-based markdown; extends Phase 3 `src/terms/external.py` |
| Provenance tier tracking | API / Backend | — | Column in output CSVs; no external service |
| Split/topic grouping | API / Backend | — | Pandas groupby on existing `cs_terms_inventory.csv` columns |

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `pandas` | ≥3.0 | CSV loading, groupby aggregation, filtering | Existing project dependency; Phase 3 already uses it |
| `src/terms/external.py` | (existing) | `ExternalReferenceMatcher` pattern to extend | Canonical Phase 3 coverage code; well-tested |
| `src/term_inventory/schemas.py` | (existing) | `EntityType`, `ReviewStatus`, `TermSource` enums | Phase 6B schema; matches FR3 requirement labels |
| `src/shared/logging.py` | (existing) | `setup_logger` | Consistent with all existing modules |

### Supporting (existing project dependencies)
| Library | Purpose | When to Use |
|---------|---------|-------------|
| `src/llm/schemas.py` | `EntityCategory` enum for Phase 2 → FR2-04 mapping | Map Phase 2 `entity_category` labels to Phase 6B `entity_type` |
| `src/shared/config.py` | `AppConfig` YAML loading | Config-driven audit parameters |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Case-insensitive exact match | Fuzzy matching (e.g., `rapidfuzz`, `difflib`) | Exact match is already the project standard (Phase 3 decision); fuzzy adds complexity and false positives for medical abbreviations |
| Pandas groupby | SQL with DuckDB | Overkill for 841 × 27 row join; pandas is already in use |
| Custom report generator | ReportLab / WeasyPrint for PDF | FR3-05 specifies markdown output; HTML/PDF not required |

**Installation:**
```bash
# No new packages needed — all existing project dependencies
pip install pandas  # already installed
```

---

## Architecture Patterns

### System Architecture Diagram

```
[ViMedCSS CS Terms]
cs_terms_inventory.csv (Phase 1)
(normalized_term, entity_category, medical_domain,
 splits_present, topics_present, occurrence_count)
        │
        ▼
[CoverageAuditor]
  ├── load_vimedcss_terms()      → DataFrame[841 rows]
  ├── load_inventory()            → DataFrame[27 rows]
  ├── match_terms()               → inner join by normalized_term (case-insensitive)
  ├── compute_coverage_by_entity()  → groupby entity_type
  ├── compute_coverage_by_domain()   → groupby medical_domain
  ├── compute_coverage_by_split()   → groupby splits_present
  ├── compute_coverage_by_topic()    → groupby topics_present
  ├── identify_missing_terms()       → left-outer: in ViMedCSS, not in inventory
  ├── identify_hard_terms()          → in inventory but low-frequency or not_verified
  └── generate_vietnamese_report()   → markdown with provenance tiers
        │
        ├──▶ outputs/coverage/vimedcss_missing_terms.csv
        ├──▶ outputs/coverage/vimedcss_hard_terms.csv
        ├──▶ outputs/coverage/vimedcss_coverage_by_entity.csv
        ├──▶ outputs/coverage/vimedcss_coverage_by_domain.csv
        ├──▶ outputs/coverage/vimedcss_coverage_by_split.csv
        ├──▶ outputs/coverage/vimedcss_coverage_by_topic.csv
        └──▶ reports/vimedcss_coverage_report_vi.md
```

### Recommended Project Structure

```
src/
├── coverage_audit/           # [NEW] Phase 6C
│   ├── __init__.py
│   ├── cli.py               # CLI subcommand: audit-coverage
│   ├── auditor.py           # CoverageAuditor orchestrator
│   ├── matcher.py           # Term matching (exact case-insensitive)
│   ├── statistics.py        # Coverage rate computation per group
│   ├── hard_term_identifier.py  # Hard term classification logic
│   ├── provenance.py        # Confidence tier assignment (local_verified / hf_reported / paper_reported)
│   ├── schemas.py           # Pydantic models for audit outputs
│   └── reporter.py          # Vietnamese coverage report generator

outputs/
├── coverage/                 # [NEW] Phase 6C coverage outputs
│   ├── vimedcss_missing_terms.csv
│   ├── vimedcss_hard_terms.csv
│   ├── vimedcss_coverage_by_entity.csv
│   ├── vimedcss_coverage_by_domain.csv
│   ├── vimedcss_coverage_by_split.csv
│   └── vimedcss_coverage_by_topic.csv

reports/
├── vimedcss_coverage_report_vi.md   # [NEW] Vietnamese coverage report (FR3-05)
```

### Pattern 1: Coverage Computation via Pandas GroupBy

This pattern extends Phase 3's `_compute_coverage` method with multi-dimensional grouping.

```python
# Source: Extended from src/terms/external.py _compute_coverage + Phase 6B builder.py
def compute_coverage_by_group(
    vimedcss_df: pd.DataFrame,
    covered_mask: pd.Series,
    group_col: str,
) -> pd.DataFrame:
    """Compute coverage rate for each value of group_col."""
    rows = []
    for group_name, group_df in vimedcss_df.groupby(group_col, dropna=False):
        total = len(group_df)
        covered = int(covered_mask[group_df.index].sum())
        missing = total - covered
        ratio = covered / total if total > 0 else 0.0
        rows.append({
            "group_key": str(group_name) if pd.notna(group_name) else "unknown",
            "total_terms": total,
            "covered_count": covered,
            "missing_count": missing,
            "coverage_ratio": round(ratio, 4),
        })
    return pd.DataFrame(rows)
```

### Pattern 2: Confidence Tier Assignment

FR3-06 requires every metric to be traceable to a verified local file. The tier system maps data sources to confidence levels.

```python
# Source: Derived from existing Phase 3 metric provenance system + FR3-06 requirement
class ProvenanceTier(str, Enum):
    """Confidence tier for metric provenance (FR3-06).

    Every metric must have a tier annotation for traceability.
    """
    LOCAL_VERIFIED = "local_verified"   # Computed from local CSV files only
    HF_REPORTED = "hf_reported"         # Reported by Hugging Face dataset card
    PAPER_REPORTED = "paper_reported"   # Reported in a published paper

def assign_provenance_tier(
    metric_name: str,
    source_file: str,
) -> ProvenanceTier:
    """Assign provenance tier based on where the metric originates."""
    local_verified_sources = {
        "cs_terms_inventory.csv",
        "medical_term_inventory.csv",
        "term_normalization_map.csv",
        "term_sources.csv",
    }
    if source_file in local_verified_sources:
        return ProvenanceTier.LOCAL_VERIFIED
    elif source_file.startswith("hf://"):
        return ProvenanceTier.HF_REPORTED
    else:
        return ProvenanceTier.PAPER_REPORTED
```

### Pattern 3: Missing vs Hard Term Classification

```python
# Source: Analysis of Phase 3 pilot + FR3-04 requirement
def classify_term_match(
    term: str,
    in_inventory: bool,
    in_verified_inventory: bool,
    occurrence_count: int,
    frequency_threshold: int = 5,
) -> str:
    """Classify a term as missing, hard, or covered.

    - missing: Not in any inventory (not even unverified)
    - hard: In inventory but low-frequency OR unverified source
    - covered: In verified inventory AND sufficiently frequent
    """
    if not in_inventory:
        return "missing"
    elif not in_verified_inventory:
        return "hard"  # LLM-generated candidate without verification
    elif occurrence_count < frequency_threshold:
        return "hard"  # Low-frequency, even if verified
    else:
        return "covered"
```

### Pattern 4: Vietnamese Coverage Report Structure

```python
# Source: Extended from src/terms/external.py _write_summary pattern + FR3-05 requirement
def generate_vietnamese_coverage_report(
    coverage_stats: dict,
    missing_df: pd.DataFrame,
    hard_df: pd.DataFrame,
    coverage_by_entity: pd.DataFrame,
    coverage_by_domain: pd.DataFrame,
    coverage_by_split: pd.DataFrame,
    coverage_by_topic: pd.DataFrame,
    provenance_manifest: list[dict],
    output_path: str,
) -> None:
    """Generate vimedcss_coverage_report_vi.md per FR3-05."""
    lines = []
    lines.append("# Báo cáo Phủ sóng Thuật ngữ ViMedCSS — Giai đoạn 6C")
    lines.append("")
    lines.append("**Nguồn dữ liệu:** ViMedCSS (HuggingFace) + Kho thuật ngữ y tế Phase 6B")
    lines.append("**Ngày tạo:** " + datetime.now().strftime("%Y-%m-%d"))
    lines.append("")

    # Section 1: Executive Summary
    lines.append("## 1. Tóm tắt Tổng quan")
    lines.append(f"- **Tổng số thuật ngữ CS trong ViMedCSS:** {total_vimedcss}")
    lines.append(f"- **Số thuật ngữ trong kho Phase 6B:** {total_inventory}")
    lines.append(f"- **Thuật ngữ được phủ sóng:** {covered_count} ({coverage_ratio:.1%})")
    lines.append(f"- **Thuật ngữ bị thiếu:** {missing_count}")
    lines.append(f"- **Thuật ngữ khó (hard):** {hard_count}")
    lines.append("")

    # Section 2: Coverage by Entity Type
    lines.append("## 2. Tỷ lệ Phủ sóng theo Entity Type")
    lines.append("| Entity Type | Tổng | Được phủ | Thiếu | Hard | Tỷ lệ |")
    lines.append("|---|---|---|---|---|---|")
    for _, row in coverage_by_entity.iterrows():
        lines.append(
            f"| {row['group_key']} | {row['total_terms']} | "
            f"{row['covered_count']} | {row['missing_count']} | "
            f"{row.get('hard_count', 0)} | {row['coverage_ratio']:.1%} |"
        )
    lines.append("")

    # Section 3: Metric Provenance Table
    lines.append("## 3. Nguồn gốc và Độ tin cậy của Số liệu")
    lines.append("")
    lines.append("| Chỉ số | Nguồn | Tầng độ tin cậy | Ghi chú |")
    lines.append("|---|---|---|---|")
    for prov in provenance_manifest:
        tier_label = {
            "local_verified": "✓ Xác minh cục bộ",
            "hf_reported": "⚠ Báo cáo từ HuggingFace",
            "paper_reported": "⚠ Trích từ bài báo",
        }[prov["tier"]]
        lines.append(
            f"| {prov['metric_name']} | {prov['source_file']} | "
            f"{tier_label} | {prov.get('notes', '')} |"
        )
    lines.append("")

    # Section 4: Missing Terms (top 20)
    lines.append("## 4. Các thuật ngữ Bị Thiếu (Top 20)")
    # ... table of missing terms with examples
    lines.append("")

    # Section 5: Hard Terms
    lines.append("## 5. Các thuật ngữ Khó (Hard Terms)")
    # ... table of hard terms with reason
    lines.append("")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
```

### Anti-Patterns to Avoid

- **Computing coverage against unverified-only terms as if they were authoritative:** `medical_term_inventory.csv` has `review_status` column distinguishing `verified` vs `not_verified`. Coverage against `not_verified` terms should be reported separately from verified coverage.
- **Claiming "0% ICD-10 coverage" as a negative result:** The Phase 6B inventory has only ~27 terms (vs. ~841 ViMedCSS terms). Coverage rates will naturally be low because the inventory is small, not because ViMedCSS is poorly covered. The report must contextualize this.
- **Re-implementing matching from scratch:** Phase 3's `ExternalReferenceMatcher._match_terms` already implements case-insensitive exact match correctly. Extend it rather than re-implement.
- **Mixing Phase 2 `entity_category` with Phase 6B `entity_type`:** Phase 2 uses 14 entity categories (e.g., `disease_or_condition`); Phase 6B uses 14 FR2-04 entity types (e.g., `disease`). Use `Phase2ToFr2EntityTypeMap` from `src/term_inventory/schemas.py` for cross-phase mapping.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Term matching | Custom fuzzy matching algorithm | Phase 3 `ExternalReferenceMatcher._match_terms` pattern | Already case-insensitive exact; well-tested; project standard |
| Coverage grouping | SQL queries or external OLAP | Pandas `groupby` | Already in use; 841 rows is trivial for pandas |
| Vietnamese report formatting | HTML-to-MD conversion library | Template-based string concatenation | FR3-05 requires markdown; Phase 3 already does this pattern |
| ICD-10 term lookup | Custom web scraping | Phase 6A output (`icd10_dual_language.csv`) | Already ingested and joined |

**Key insight:** Phase 6C is primarily a **data processing and reporting** task, not a modeling or algorithm task. The complexity is in correct grouping, accurate provenance tracking, and clear Vietnamese narrative — not in novel algorithms.

---

## Common Pitfalls

### Pitfall 1: Confusing "Missing" with "Uncovered"
**What goes wrong:** Terms not in the Phase 6B inventory are labeled "missing" and interpreted as "not covered by any medical standard." But the Phase 6B inventory has only ~27 terms — most ViMedCSS terms will be "missing" simply because the inventory is small.
**Why it happens:** The 27-term inventory from Phase 6B (mock mode) is not a comprehensive medical lexicon. It was built from a limited seed set (3 ICD-10 diseases, 5 RxNorm drugs, 5 openFDA devices, 5 NLM lab tests, 5 abbreviations, 5 vimedcss_seed terms).
**How to avoid:** Report two coverage metrics separately: (1) `coverage_against_verified` — coverage against only `review_status=verified` terms, (2) `coverage_against_all` — coverage against all terms regardless of verification. Always contextualize raw numbers with "the Phase 6B inventory contains N terms from X sources."
**Warning signs:** Coverage ratio < 5% for any group is expected given inventory size.

### Pitfall 2: Entity Type Schema Mismatch Between Phase 2 and Phase 6B
**What goes wrong:** `cs_terms_inventory.csv` (Phase 1) uses Phase 2 entity categories (e.g., `disease_or_condition`, `drug_or_active_ingredient`), while `medical_term_inventory.csv` (Phase 6B) uses FR2-04 entity types (e.g., `disease`, `drug`). Grouping coverage by entity type may fail or produce mismatched group keys.
**Why it happens:** Two different classification schemas evolved over phases.
**How to avoid:** Use `Phase2ToFr2EntityTypeMap` from `src/term_inventory/schemas.py` to normalize Phase 2 entity categories to FR2-04 entity types before grouping. Alternatively, report both Phase 2 and FR2-04 entity breakdowns.
**Warning signs:** `groupby` produces entity labels that don't appear in `medical_term_inventory.csv`.

### Pitfall 3: `splits_present` and `topics_present` Are Semicolon-Delimited Lists
**What goes wrong:** `cs_terms_inventory.csv` has `splits_present` and `topics_present` as semicolon-delimited strings (e.g., `"hard;test;train"`). A naive groupby treats each string as a single value, producing groups for each unique combination rather than per-split or per-topic counts.
**Why it happens:** These columns are lists serialized as strings.
**How to avoid:** Use pandas `str.split(";")` + `explode()` to expand lists before groupby, or use a multi-set counting approach.
**Example fix:**
```python
# Expand semicolon-delimited split list into one row per split
split_rows = []
for _, row in vimedcss_df.iterrows():
    splits = str(row.get("splits_present", "")).split(";")
    for split in splits:
        split = split.strip()
        if split:
            split_rows.append({**row.to_dict(), "split": split})
split_df = pd.DataFrame(split_rows)
```

### Pitfall 4: Hard Terms Identified as "Covered" Due to LLM-Generated Candidates
**What goes wrong:** The Phase 6B inventory includes `llm_generated_candidate=True` terms from `vimedcss_seed` and `abbreviation_list` that were never verified against an authoritative source. A ViMedCSS term matching one of these could be marked "covered" when it actually has no real external backing.
**Why it happens:** Phase 6B's non-authoritative loaders (abbreviation, vimedcss_seed) produce terms that look like they came from a lexicon but are actually LLM candidates.
**How to avoid:** Use `review_status` and `llm_generated_candidate` columns to distinguish verified vs. unverified coverage. FR3-04's "hard terms" category specifically targets terms in the inventory but with low confidence.

### Pitfall 5: Phase 6B Inventory Uses `term_normalized` vs Phase 2 Uses `normalized_term`
**What goes wrong:** The two CSV files use different column names for the normalized term field. Phase 2 (Phase 1 output) uses `normalized_term`; Phase 6B uses `term_normalized`.
**Why it happens:** Evolving schema across phases.
**How to avoid:** The matching function should normalize both to lowercase before comparison, and should try both column names. This is already handled by Phase 3's `_match_terms` which uses `str(term).lower()`.
**Warning signs:** `external_lower_map` builds from whatever canonical column exists; if the wrong column is used, coverage will be 0.

---

## Code Examples

### Term Matching (Case-Insensitive Exact Match)

```python
# Source: Extended from src/terms/external.py _match_terms
def match_terms(
    vimedcss_df: pd.DataFrame,
    inventory_df: pd.DataFrame,
    match_col_vimedcss: str = "normalized_term",
    match_col_inventory: str = "term_normalized",
) -> pd.DataFrame:
    """Perform case-insensitive exact match between ViMedCSS and inventory.
    
    Preserves all ViMedCSS rows; adds inventory match columns.
    """
    # Build O(1) lookup from inventory
    inv_lookup: dict[str, dict] = {}
    for _, row in inventory_df.iterrows():
        key = str(row[match_col_inventory]).lower().strip()
        inv_lookup[key] = row.to_dict()
    
    matched = vimedcss_df.copy()
    matched["coverage_status"] = "missing"
    matched["coverage_source"] = ""
    matched["coverage_entity_type"] = ""
    matched["coverage_verified"] = "false"
    
    covered_count = 0
    for idx in matched.index:
        term = str(matched.loc[idx, match_col_vimedcss]).lower().strip()
        if term in inv_lookup:
            inv_row = inv_lookup[term]
            matched.loc[idx, "coverage_status"] = "covered"
            matched.loc[idx, "coverage_source"] = str(inv_row.get("source_name", ""))
            matched.loc[idx, "coverage_entity_type"] = str(inv_row.get("entity_type", ""))
            matched.loc[idx, "coverage_verified"] = str(inv_row.get("review_status", "")) == "verified"
            covered_count += 1
    
    logger.info(f"Matched {covered_count}/{len(matched)} ViMedCSS terms.")
    return matched
```

### Split-List Expansion for GroupBy

```python
# Source: Pitfall 3 mitigation — semicolon-delimited list expansion
def expand_split_column(df: pd.DataFrame, col: str = "splits_present") -> pd.DataFrame:
    """Expand semicolon-delimited string column into one row per item."""
    rows = []
    for _, row in df.iterrows():
        items = str(row.get(col, "")).split(";")
        for item in items:
            item = item.strip()
            if item:
                rows.append({**row.to_dict(), col.replace("_present", ""): item})
    return pd.DataFrame(rows)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Phase 3 mock inventory (5 synthetic terms) | Phase 6B real multi-source inventory (~27 terms from ICD-10, RxNorm, openFDA, NLM, abbreviations, seed) | Phase 6B (now) | Coverage audit now uses actual external lexicons; results are meaningful |
| Single-dimension grouping (entity only) | Multi-dimension grouping: entity, domain, split, topic | Phase 6C (this phase) | Enables detailed slice analysis per FR3-03 |
| No provenance tracking | Confidence tier tracking (local_verified / hf_reported / paper_reported) | Phase 6C (this phase) | Every metric is traceable per FR3-06 |
| Phase 2 `entity_category` labels | FR2-04 `entity_type` labels | Phase 6B (transition) | Requires mapping for cross-phase grouping |

**Deprecated/outdated:**
- **Phase 3 mock inventory:** The `build_mock_inventory()` fixture is replaced by Phase 6B's real `medical_term_inventory.csv`. The mock pattern is retained only for smoke tests.

---

## Assumptions Log

> List all claims tagged `[ASSUMED]` in this research. The planner and discuss-phase use this section to identify decisions that need user confirmation before execution.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Phase 6B `medical_term_inventory.csv` will have ≥1 matching term for at least some ViMedCSS CS terms | Matching Strategy | Coverage may be 0% if the inventories don't overlap; the report must handle this gracefully |
| A2 | `cs_terms_inventory.csv` column names (`normalized_term`, `entity_category`, `medical_domain`, `splits_present`, `topics_present`) remain stable | Data Schema | Column name changes would break groupby and matching; add schema validation |
| A3 | Phase 6B `medical_term_inventory.csv` uses `term_normalized` as the matching column (not `canonical_term` or `term_original`) | Data Schema | If wrong column is used, coverage will be 0; cross-check against `term_normalization_map.csv` |
| A4 | The ~27 terms in Phase 6B inventory are sufficient for a meaningful coverage audit | Scope | Low coverage rates are expected; the report must contextualize inventory size |
| A5 | FR3-05's "confidence tiers" map directly to the 3-tier system (local_verified / hf_reported / paper_reported) | Report Structure | FR3-05 specifies these 3 tiers; no additional tiers needed |
| A6 | `splits_present` and `topics_present` use semicolon (`;`) as delimiter (not comma or pipe) | Data Schema | If delimiter differs, the split expansion pattern will produce wrong counts; verify from actual data |

**If this table is empty:** All claims in this research were verified or cited — no user confirmation needed.

---

## Open Questions

1. **Phase 2 → FR2-04 entity type mapping fidelity**
   - What we know: Phase 2 uses `entity_category` labels (e.g., `disease_or_condition`); Phase 6B uses `entity_type` labels (e.g., `disease`). `Phase2ToFr2EntityTypeMap` provides a mapping.
   - What's unclear: Does the mapping correctly handle ambiguous Phase 2 categories like `general_medical_english` → `UNKNOWN`? Should these be excluded from entity-grouped coverage or reported separately?
   - Recommendation: Report two entity breakdowns: one using Phase 2 `entity_category` (for consistency with Phase 1/2/3), one using the mapped FR2-04 `entity_type` (for FR3-03 compliance).

2. **Coverage threshold for "hard" terms**
   - What we know: Phase 3 used `min_high_priority = 5` (occurrence_count threshold). FR3-04 defines "hard" as terms in inventory but low coverage.
   - What's unclear: Should "hard" use the same 5-occurrence threshold, or a different one based on Phase 6B inventory size?
   - Recommendation: Use the same threshold (5 occurrences) for consistency. If Phase 6B inventory grows in future phases, the threshold can be revisited.

3. **Whether to include `segment_text` matching for FR3-01**
   - What we know: FR3-01 mentions matching from both `cs_terms_list` (already in `cs_terms_inventory.csv` as `normalized_term`) and `segment_text` (raw utterance text).
   - What's unclear: Does `segment_text` matching mean fuzzy matching within full utterances, or extracting additional terms from utterances not already in `cs_terms_list`?
   - Recommendation: Focus FR3-01 on `cs_terms_list`/`normalized_term` matching (already implemented). `segment_text` matching is a potential extension but adds significant complexity and should be deferred.

4. **Vietnamese report length and depth**
   - What we know: FR3-05 requires "numbers, examples, and confidence tiers." Phase 5 report was 12 sections.
   - What's unclear: How many examples are needed per group? Should the report include all missing/hard terms or just top-N?
   - Recommendation: Report all missing/hard terms in CSV exports (machine-readable); report top 20 in the markdown narrative for human readability. Full lists are in the CSV files.

---

## Environment Availability

> Step 2.6: SKIPPED (no external dependencies identified)

Phase 6C is purely a data processing and reporting task using only:
- Local CSV files from Phase 1 and Phase 6B outputs
- Existing project dependencies (pandas, pydantic)
- No external APIs, databases, or services

No new package installations, external tools, or runtimes are required.

---

## Validation Architecture

> Skip this section — `workflow.nyquist_validation` is explicitly set to `false` in `.planning/config.json`.

No automated test framework setup is required for Phase 6C.

---

## Security Domain

> Skip this section — Phase 6C is a data processing and reporting task with no user input, authentication, network-facing endpoints, or sensitive data processing beyond existing CSV files.

No ASVS categories apply. Only static CSV files are read and written.

---

## Sources

### Primary (HIGH confidence)
- Existing codebase: `src/terms/external.py` — `ExternalReferenceMatcher` (canonical Phase 3 coverage implementation)
- Existing codebase: `src/term_inventory/schemas.py` — `EntityType`, `ReviewStatus`, `Phase2ToFr2EntityTypeMap` (Phase 6B schema)
- Existing codebase: `src/term_inventory/builder.py` — `InventoryBuilder` (Phase 6B pipeline pattern)
- Existing data: `outputs/term_coverage/cs_terms_inventory.csv` — Phase 1 output (841 rows)
- Existing data: `data/terms/medical_term_inventory.csv` — Phase 6B output (27 rows)

### Secondary (MEDIUM confidence)
- Project architecture: `.planning/research/ARCHITECTURE.md` — Phase 2 build order, `coverage_audit/` module specification
- Project requirements: `.planning/REQUIREMENTS.md` — FR3-01 through FR3-06 specification

### Tertiary (LOW confidence)
- Phase 3 coverage results: `outputs/term_coverage/vimedcss_vs_external_coverage.csv` — Phase 3 output showing 0% coverage (mock inventory)
- Specific column delimiter assumptions (`;` for `splits_present`, `topics_present`) — need field verification

---

## Metadata

**Confidence breakdown:**
- Standard Stack: HIGH — all libraries are existing project dependencies; no new packages
- Architecture: HIGH — extends well-tested Phase 3 `ExternalReferenceMatcher` pattern; Phase 2 architecture doc confirms `coverage_audit/` module
- Pitfalls: MEDIUM — specific data quality issues (schema mismatches, delimiter assumptions) need field verification

**Research date:** 2026-06-22
**Valid until:** 2026-07-22 (30 days; coverage audit logic is stable; only input data schema changes would invalidate)
