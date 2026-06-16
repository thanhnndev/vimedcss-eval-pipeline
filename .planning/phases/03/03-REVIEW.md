---
phase: 03-external-ref-match
reviewed: 2026-06-16T08:35:00Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - configs/external.yaml
  - src/terms/external.py
  - src/shared/config.py
  - src/cli.py
  - tests/test_external_reference.py
findings:
  critical: 0
  warning: 1
  info: 2
  total: 3
status: issues_found
---

# Phase 3: Code Review Report

**Reviewed:** 2026-06-16T08:35:00Z
**Depth:** standard
**Files Reviewed:** 5
**Status:** issues_found

## Summary

Phase 3 implements an external reference matcher for the ViMedCSS evaluation pipeline. The implementation follows established patterns (config injection, module-level logger, fail-fast validation) and has 15 passing Nyquist validation tests. Three issues were identified: one **warning** about a potentially unvalidated column access, and two **info** items about edge cases in test coverage and code documentation.

---

## Structural Findings (fallow)

No structural pre-pass findings were provided. This section is omitted.

---

## Narrative Findings (AI reviewer)

## Warnings

### WR-01: Unvalidated column access in coverage computation

**File:** `src/terms/external.py:269`
**Issue:** `_compute_coverage()` accesses `matched_df["occurrence_count"]` without first validating that the column exists. While this column is populated by `cs_terms_inventory.csv` (Phase 1/2 output), there is no defensive check. If a future caller passes a DataFrame without this column, the code will raise a `KeyError` with an opaque message.

**Fix:**
```python
# Add validation at the start of _compute_coverage
if "occurrence_count" not in matched_df.columns:
    logger.warning("occurrence_count column not found in matched_df. "
                   "Setting missing_high_priority_count to 0.")
    matched_df = matched_df.copy()
    matched_df["occurrence_count"] = 0
```

---

## Info

### IN-01: Test does not verify all edge cases for limit=0 behavior

**File:** `tests/test_external_reference.py:512`
**Issue:** `test_cli_mock_mode_writes_expected_files` tests `limit=2` but does not cover `limit=0` or negative limit values. The `run()` method guards `limit > 0` (line 73), so negative/zero limits are effectively no-ops. While this is minor, explicitly testing the boundary would improve robustness.

**Fix:** Consider adding:
```python
# Test limit=0 behaves same as no limit
stats_zero = matcher.run(limit=0)
assert stats_zero["vimedcss_covered_count"] == 5
```

---

### IN-02: Duplicate term in external inventory silently deduplicated by first-occurrence

**File:** `src/terms/external.py:145-149`
**Issue:** When the external inventory contains duplicate `canonical_term` values (case-insensitive), the implementation silently keeps the first occurrence. This is documented via a warning log, but there is no test that specifically verifies which occurrence is retained when duplicates exist with different metadata (e.g., different `source_name`).

**Fix:** No immediate fix required — the current behavior (first wins) is documented and defensible for a pilot. A future enhancement could log the discarded rows' source names for auditability.

---

## Previously Auto-Fixed Issues (Noted from 03-01-SUMMARY.md)

The following bugs were identified and fixed during implementation. They are recorded here for completeness and are NOT re-flagged as new issues:

1. **groupby iteration bug** (`4504f43`) — `for cat, grp in sorted(cat_groups.groups.keys())` was incorrect; fixed to `for cat, grp in cat_groups`
2. **Boolean string coercion** (`4504f43`) — pandas converted YAML booleans to `"True"/"False"` strings in CSV; fixed with `bool()` wrapper
3. **Missing else branch in test** (`4504f43`) — test fixture did not write all required YAML files, causing `AppConfig` to raise `FileNotFoundError`; fixed by adding `else` branch
4. **Missing --limit parameter** (`0fcb79b`) — `--limit` CLI flag was not passed to `run()`; fixed by adding the parameter

---

## Positive Observations

- **Config-driven design**: All paths, thresholds, and source lists live in YAML. No hard-coded URLs or paths in source code.
- **Fail-fast validation**: `_load_inventory()` raises descriptive `FileNotFoundError` and `ValueError` for missing/invalid files.
- **Case-insensitive deduplication**: External inventory deduplication is handled correctly with a warning log.
- **Empty inventory handling**: Empty external inventory is handled gracefully (returns empty DataFrame with required columns, logs warning).
- **Vietnamese summary with disclaimer**: Summary explicitly states the pilot scope, following the plan's requirement for scope honesty.
- **Clean test coverage**: 15 tests cover all acceptance criteria (EXT_REF-01, EXT_REF-02) plus edge cases.
- **Static mock fixture**: `build_mock_inventory()` is a well-structured static helper for CLI smoke testing.

---

_Reviewed: 2026-06-16T08:35:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
