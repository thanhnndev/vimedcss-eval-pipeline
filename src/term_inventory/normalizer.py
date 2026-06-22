"""Normalization pipeline for the medical term inventory.

This module transforms raw ingested terms into canonical normalized forms suitable
for deduplication and matching. It handles:

- Unicode NFC normalization (canonical composition)
- Greek-to-ASCII transliteration (β → beta, α → alpha, etc.)
- Case folding (lowercase)
- Unit suffix normalization (µg → mcg, ug → mcg, etc.)
- Within-entity-type deduplication (same entity_type + same normalized form → merge)

Normalization map (`term_normalization_map.csv`) provides full traceability:
every transformation is recorded with the raw form, normalized form, transformation
description, entity_type, and term_id.
"""
import re
import unicodedata
from typing import List, Optional, Tuple

import pandas as pd

from src.term_inventory.schemas import EntityType, ReviewStatus, TermSource


# ---------------------------------------------------------------------------
# Greek alphabet → ASCII transliteration mapping
# ---------------------------------------------------------------------------
GREEK_TO_ASCII: dict[str, str] = {
    # Lowercase
    "α": "alpha",
    "β": "beta",
    "γ": "gamma",
    "δ": "delta",
    "ε": "epsilon",
    "ζ": "zeta",
    "η": "eta",
    "θ": "theta",
    "ι": "iota",
    "κ": "kappa",
    "λ": "lambda",
    "μ": "mu",
    "ν": "nu",
    "ξ": "xi",
    "ο": "omicron",
    "π": "pi",
    "ρ": "rho",
    "σ": "sigma",
    "τ": "tau",
    "υ": "upsilon",
    "φ": "phi",
    "χ": "chi",
    "ψ": "psi",
    "ω": "omega",
    # Uppercase
    "Α": "Alpha",
    "Β": "Beta",
    "Γ": "Gamma",
    "Δ": "Delta",
    "Ε": "Epsilon",
    "Η": "Eta",
    "Θ": "Theta",
    "Ι": "Iota",
    "Κ": "Kappa",
    "Λ": "Lambda",
    "Μ": "Mu",
    "Ν": "Nu",
    "Ξ": "Xi",
    "Ο": "Omicron",
    "Π": "Pi",
    "Ρ": "Rho",
    "Σ": "Sigma",
    "Τ": "Tau",
    "Υ": "Upsilon",
    "Φ": "Phi",
    "Χ": "Chi",
    "Ψ": "Psi",
    "Ω": "Omega",
    # Special symbols
    "°": "degree",
}


# ---------------------------------------------------------------------------
# Unit suffix normalization mapping
# ---------------------------------------------------------------------------
UNIT_SUFFIX_NORM: dict[str, str] = {
    "µg": "mcg",
    "ug": "mcg",
    "µl": "ml",
    "ul": "ml",
    "µg/kg": "mcg/kg",
    "mg/kg": "mg/kg",
    "mg/ml": "mg/ml",
    "g/dl": "g/dl",
    "mg/dl": "mg/dl",
}


# ---------------------------------------------------------------------------
# Source authority ordering for deduplication conflict resolution
# ---------------------------------------------------------------------------
SOURCE_AUTHORITY_ORDER: list[str] = [
    "icd10",
    "rxnorm",
    "openfda",
    "nlm_lab",
    "abbreviation_list",
    "vimedcss_seed",
    "llm_generated",
]


def _source_authority(source_name: str) -> int:
    """Return a lower-is-better authority rank for deduplication conflict resolution."""
    try:
        return SOURCE_AUTHORITY_ORDER.index(source_name)
    except ValueError:
        return len(SOURCE_AUTHORITY_ORDER)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def normalize_term(raw: str, entity_type: Optional[str] = None) -> Tuple[str, str]:
    """Normalize a raw term string to canonical form.

    Transformation pipeline:
        1. Unicode NFC composition
        2. Greek-to-ASCII transliteration
        3. Case folding (lowercase)
        4. Unit suffix normalization
        5. Punctuation stripping (preserving medical hyphens)
        6. Whitespace collapse

    Args:
        raw: The original term string as ingested.
        entity_type: Optional entity type for future use (not used in normalization).

    Returns:
        A 2-tuple of (normalized_form, transformation_description).
        transformation_description is a comma-separated list of applied transformations,
        or "none" if no transformations were applied.
    """
    if not raw or not isinstance(raw, str):
        return ("", "none")

    transformations: list[str] = []
    s = raw

    # Step 1: Unicode normalization — NFKD decomposition strips combining marks
    # (e.g. metformin + combining acute → metformin), then strip combining chars
    nfc_before = s
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = unicodedata.normalize("NFC", s)  # re-compose remaining characters
    if s != nfc_before:
        transformations.append("nfc")

    # Step 2: Unit suffix normalization — BEFORE Greek-to-ASCII to prevent
    # Greek mu (μ, U+03BC) from becoming "mu" before µg→mcg substitution.
    # Multi-char unit suffixes are handled first (longer match strategy).
    s_unit = s
    for unit_from, unit_to in sorted(UNIT_SUFFIX_NORM.items(), key=lambda x: -len(x[0])):
        pattern = re.escape(unit_from) + r"(?=\s|$|$)"
        s = re.sub(pattern, unit_to, s, flags=re.IGNORECASE)
    if s != s_unit:
        transformations.append("unit_normalization")

    # Step 3: Greek-to-ASCII transliteration
    # Replace all Greek characters (longest match strategy not needed since
    # GREEK_TO_ASCII maps individual characters)
    s_greek = s
    for greek_char, ascii_char in GREEK_TO_ASCII.items():
        s = s.replace(greek_char, ascii_char)
    if s != s_greek:
        transformations.append("greek_to_ascii")

    # Step 4: Case folding
    s_lower = s.lower()
    if s_lower != s:
        transformations.append("case_fold")
    s = s_lower

    # Step 5: Punctuation stripping (preserve internal hyphens for medical terms)
    # Strip leading/trailing punctuation but keep internal hyphens and apostrophes
    s_punct = s
    # Remove punctuation chars except hyphen, apostrophe, and internal spaces
    # Keep: alphanumeric, space, hyphen, apostrophe
    s = re.sub(r"^[^\w\s'-]+|[^\w\s'-]+$", "", s)
    if s != s_punct:
        transformations.append("punctuation_strip")

    # Step 6: Whitespace normalization
    s_ws = s
    s = re.sub(r"\s+", " ", s).strip()
    if s != s_ws:
        transformations.append("whitespace_normalize")

    transformation_desc = ", ".join(transformations) if transformations else "none"
    return s, transformation_desc


def normalize_batch(
    terms: List[str], entity_types: Optional[List[str]] = None
) -> pd.DataFrame:
    """Normalize a batch of term strings.

    Args:
        terms: List of raw term strings to normalize.
        entity_types: Optional list of entity types (one per term). If None,
            all terms get entity_type=None.

    Returns:
        DataFrame with columns: raw_form, normalized_form, transformation, entity_type.
    """
    if entity_types is not None and len(entity_types) != len(terms):
        raise ValueError(
            f"terms and entity_types must have the same length: "
            f"{len(terms)} vs {len(entity_types)}"
        )

    rows = []
    for i, term in enumerate(terms):
        et = entity_types[i] if entity_types else None
        norm, trans = normalize_term(term, et)
        rows.append(
            {
                "raw_form": term,
                "normalized_form": norm,
                "transformation": trans,
                "entity_type": et,
            }
        )
    return pd.DataFrame(rows)


def apply_normalization(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Apply normalization to a DataFrame with term records.

    Adds a `term_normalized` column and produces a normalization map DataFrame
    containing only rows where transformation != "none".

    Args:
        df: DataFrame with a `term_original` column.

    Returns:
        A 2-tuple of (normalized_df, normalization_map_df) where:
        - normalized_df: the input DataFrame with `term_normalized` column added
        - normalization_map_df: only rows where transformation occurred
            (columns: raw_form, normalized_form, transformation, entity_type, term_id)
    """
    if "term_original" not in df.columns:
        raise ValueError(
            "Input DataFrame must have a 'term_original' column. "
            f"Found columns: {list(df.columns)}"
        )

    results: list[dict] = []
    normalized_values: list[str] = []

    for idx, row in df.iterrows():
        raw = str(row["term_original"]) if pd.notna(row["term_original"]) else ""
        entity_type = str(row.get("entity_type", "")) or None
        norm, trans = normalize_term(raw, entity_type)
        normalized_values.append(norm)
        results.append(
            {
                "raw_form": raw,
                "normalized_form": norm,
                "transformation": trans,
                "entity_type": entity_type,
            }
        )

    normalized_df = df.copy()
    normalized_df["term_normalized"] = normalized_values

    # Only include rows where transformation != "none" in the normalization map
    all_maps = pd.DataFrame(results)
    if "term_id" in df.columns:
        all_maps["term_id"] = df["term_id"].values
    normalization_map_df = all_maps[all_maps["transformation"] != "none"].copy()

    # Warn if >20% of terms were transformed (suggests abnormal data)
    if len(normalization_map_df) / max(len(df), 1) > 0.20:
        pct = 100 * len(normalization_map_df) / len(df)
        import logging
        logging.warning(
            f"High normalization rate: {len(normalization_map_df)}/{len(df)} "
            f"({pct:.1f}%) terms were transformed. This suggests abnormal source data."
        )

    return normalized_df, normalization_map_df


def deduplicate_within_entity_type(
    df: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Deduplicate terms within the same entity_type.

    Groups by (entity_type, term_normalized) and resolves conflicts by source authority:
        1. verified review_status wins over needs_review / not_verified / llm_candidate
        2. If both are verified, prefer more authoritative sources:
           icd10 > rxnorm > openfda > nlm_lab > abbreviation_list >
           vimedcss_seed > llm_generated

    Args:
        df: DataFrame with `term_normalized` and `entity_type` columns.

    Returns:
        A 2-tuple of (deduplicated_df, duplicate_map_df) where:
        - deduplicated_df: one row per unique (entity_type, term_normalized) pair
        - duplicate_map_df: tracking which terms were merged (columns:
            canonical_term_id, duplicate_term_id, reason, source_kept, source_removed)
    """
    import logging

    if "term_normalized" not in df.columns or "entity_type" not in df.columns:
        raise ValueError(
            "DataFrame must have 'term_normalized' and 'entity_type' columns. "
            f"Found columns: {list(df.columns)}"
        )

    dup_map_rows: list[dict] = []
    kept_rows: list[dict] = []
    dedup_rate = 0.0

    # Group by (entity_type, term_normalized)
    grouped = df.groupby(["entity_type", "term_normalized"], dropna=False)

    for (entity_type_val, normalized_val), group in grouped:
        if len(group) == 1:
            kept_rows.append(group.iloc[0].to_dict())
            continue

        # Conflict resolution: verified sources win; if both verified, prefer by authority
        group = group.reset_index(drop=True)

        verified = group[group["review_status"] == ReviewStatus.VERIFIED.value]
        non_verified = group[group["review_status"] != ReviewStatus.VERIFIED.value]

        if len(verified) > 0:
            # One of the verified sources wins
            verified = verified.copy()
            verified["_authority_rank"] = verified["source_name"].apply(_source_authority)
            winner = verified.sort_values("_authority_rank").iloc[0]
            losers = pd.concat([non_verified, verified.drop(winner.name)])
        else:
            # No verified source — pick highest-authority non-verified
            group = group.copy()
            group["_authority_rank"] = group["source_name"].apply(_source_authority)
            winner = group.sort_values("_authority_rank").iloc[0]
            losers = group.drop(winner.name)

        kept_rows.append(winner.to_dict())

        # Record the canonical entry itself in the duplicate map
        # (so the map tracks who won and who lost for each normalized-form group)
        # NO — skip canonical self-reference; duplicate_map tracks REMOVED terms only
        # per plan verification: `assert len(dmap) == 1` (one duplicate removed)

        # Record each duplicate that was removed
        for _, dup_row in losers.iterrows():
            is_verified = dup_row.get("review_status") == ReviewStatus.VERIFIED.value
            reason_suffix = (
                "verified but lower authority"
                if is_verified
                else f"not verified (review_status={dup_row.get('review_status', '')})"
            )
            dup_map_rows.append(
                {
                    "canonical_term_id": winner.get("term_id", None),
                    "duplicate_term_id": dup_row.get("term_id", None),
                    "reason": (
                        f"deduplicated: entity_type={entity_type_val}, "
                        f"normalized={normalized_val!r}, "
                        f"removed source={dup_row.get('source_name', '')} — {reason_suffix}"
                    ),
                    "source_kept": winner.get("source_name", ""),
                    "source_removed": dup_row.get("source_name", ""),
                    "entity_type": entity_type_val,
                    "normalized_form": normalized_val,
                }
            )

    deduplicated_df = pd.DataFrame(kept_rows)

    dedup_rate = len(dup_map_rows) / max(len(df), 1)
    if dedup_rate > 0.30:
        import logging
        logging.warning(
            f"High deduplication rate: {len(dup_map_rows)} duplicates removed "
            f"from {len(df)} terms ({100*dedup_rate:.1f}%). "
            f"This suggests too-aggressive normalization or source overlap."
        )

    import logging
    n_entity_types = df["entity_type"].nunique() if len(df) > 0 and "entity_type" in df.columns else 0
    logging.info(
        f"Deduplicated {len(dup_map_rows)} duplicate terms "
        f"across {n_entity_types} entity types. "
        f"Deduplication rate: {100*dedup_rate:.1f}%"
    )

    duplicate_map_df = pd.DataFrame(dup_map_rows)
    return deduplicated_df, duplicate_map_df


def create_deduplication_report(dedup_df: pd.DataFrame) -> pd.DataFrame:
    """Generate a deduplication summary report by entity_type.

    Args:
        dedup_df: The deduplicated DataFrame (with a duplicate_map from
            deduplicate_within_entity_type).

    Returns:
        Summary DataFrame with columns: entity_type, total_terms, duplicates_removed,
        deduplication_rate.
    """
    # Note: this function takes the deduplicated df; the caller should also
    # keep track of the original df size for rate calculation.
    # We provide a minimal report from the dedup result.
    if "entity_type" not in dedup_df.columns:
        return pd.DataFrame(
            columns=["entity_type", "total_terms", "duplicates_removed", "deduplication_rate"]
        )

    summary = (
        dedup_df.groupby("entity_type", dropna=False)
        .size()
        .reset_index(name="total_terms")
    )
    summary["duplicates_removed"] = 0  # Caller fills this from duplicate_map
    summary["deduplication_rate"] = 0.0  # Caller computes this
    return summary
