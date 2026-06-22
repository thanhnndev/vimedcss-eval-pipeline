"""Phase 6b InventoryBuilder — orchestrates the full term inventory pipeline.

Pipeline order:
  1. Load all sources via their loaders
  2. Concatenate into unified DataFrame
  3. Assign term_id to each row
  4. Apply normalization (term_normalized + normalization_map)
  5. Deduplicate within entity_type
  6. LLM classify non-authoritative terms
  7. Export 4 CSV files + report

Each loader produces a DataFrame with MedicalTermRecord columns already mapped
(term_id through fetched_at). The builder adds term_id after concat so all
loaders can produce their own local term_ids without collision, then the builder
reassigns globally unique term_ids in concat order.
"""
import os
import time
from datetime import datetime, timezone

import pandas as pd

from src.term_inventory.schemas import InventoryConfig
from src.term_inventory.loaders import (
    Icd10BackboneLoader,
    RxNormLoader,
    NlmLabLoader,
    OpenFdaDeviceLoader,
    AbbreviationLoader,
    VimedcssSeedLoader,
)
from src.term_inventory.normalizer import apply_normalization, deduplicate_within_entity_type
from src.term_inventory.classifier import MedicalTermClassifier
from src.term_inventory.reporter import generate_term_inventory_report
from src.shared.logging import setup_logger

logger = setup_logger("term_inventory.builder")

# Authoritative sources — already carry entity_type; skip LLM classification
AUTHORITATIVE_SOURCES = {"icd10", "rxnorm", "openfda"}


class InventoryBuilder:
    """Orchestrates the complete medical term inventory pipeline.

    Usage:
        config = InventoryConfig()
        builder = InventoryBuilder(config)
        stats = builder.build(mock=True, limit=5)
    """

    def __init__(self, config: InventoryConfig) -> None:
        """Initialize all loaders, the normalizer, and the classifier.

        Args:
            config: InventoryConfig controlling paths, seed lists, thresholds.
        """
        self.config = config

        # Instantiate all 6 loaders
        self.icd10_loader = Icd10BackboneLoader(config)
        self.rxnorm_loader = RxNormLoader(config)
        self.nlm_lab_loader = NlmLabLoader(config)
        self.openfda_loader = OpenFdaDeviceLoader(config)
        self.abbreviation_loader = AbbreviationLoader(config)
        self.vimedcss_seed_loader = VimedcssSeedLoader(config)

        # Classifier is created lazily in build() — mock flag is needed there
        self._classifier: MedicalTermClassifier | None = None

        logger.info(
            "InventoryBuilder initialized with 6 loaders: "
            "icd10, rxnorm, nlm_lab, openfda, abbreviation, vimedcss_seed"
        )

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def build(self, mock: bool = False, limit: int | None = None) -> dict:
        """Run the complete inventory build pipeline.

        Args:
            mock: If True, use keyword-based mock classification instead of OpenAI.
            limit: If set, truncate each source DataFrame to this many rows.

        Returns:
            Stats dict with total_terms, authoritative_count, llm_candidate_count,
            review_queue_count, normalization_map_count, deduplication_count,
            elapsed_seconds.
        """
        t0 = time.time()

        # Ensure output directories exist
        os.makedirs(self.config.output_dir, exist_ok=True)
        os.makedirs(self.config.log_dir, exist_ok=True)

        # ---- Step 1: Load all sources ----
        logger.info("=" * 60)
        logger.info("Step 1: Loading all sources")
        logger.info("=" * 60)

        loader_results = self._load_all_sources(limit=limit)

        if not loader_results:
            raise RuntimeError(
                "No data loaded from any source. Check that data files exist "
                "(Phase 1 output, ICD-10 backbone) or use --mock mode."
            )

        for name, count in loader_results.items():
            logger.info(f"  {name}: {count} terms")

        # ---- Step 2: Concatenate ----
        logger.info("=" * 60)
        logger.info("Step 2: Concatenating all sources")
        logger.info("=" * 60)

        combined_df = pd.concat(loader_results.values(), ignore_index=True)
        logger.info(f"Combined DataFrame: {len(combined_df)} rows")

        # ---- Step 3: Assign global term_id ----
        logger.info("=" * 60)
        logger.info("Step 3: Assigning global term_id")
        logger.info("=" * 60)

        combined_df = combined_df.copy()
        combined_df["term_id"] = [
            f"term_{i:06d}" for i in range(1, len(combined_df) + 1)
        ]

        # Ensure review_status column is string (not mixed types from concat)
        if "review_status" in combined_df.columns:
            combined_df["review_status"] = combined_df["review_status"].astype(str)
        if "entity_type" in combined_df.columns:
            combined_df["entity_type"] = combined_df["entity_type"].astype(str)
        if "llm_generated_candidate" in combined_df.columns:
            combined_df["llm_generated_candidate"] = combined_df["llm_generated_candidate"].astype(str)

        logger.info(f"term_id assigned: {combined_df['term_id'].iloc[0]} … {combined_df['term_id'].iloc[-1]}")

        # ---- Step 4: Normalization ----
        logger.info("=" * 60)
        logger.info("Step 4: Applying normalization")
        logger.info("=" * 60)

        normalized_df, norm_map_df = apply_normalization(combined_df)

        # Attach term_id to normalization map rows
        norm_map_df = norm_map_df.copy()
        norm_map_df["term_id"] = normalized_df.loc[norm_map_df.index, "term_id"]

        norm_transformed = len(norm_map_df)
        norm_rate = 100 * norm_transformed / max(len(normalized_df), 1)
        logger.info(
            f"Normalization: {norm_transformed}/{len(normalized_df)} "
            f"({norm_rate:.1f}%) terms transformed"
        )

        # ---- Step 5: Deduplication ----
        logger.info("=" * 60)
        logger.info("Step 5: Deduplicating within entity_type")
        logger.info("=" * 60)

        dedup_df, dedup_map_df = deduplicate_within_entity_type(normalized_df)

        n_deduped = len(combined_df) - len(dedup_df)
        dedup_rate = 100 * n_deduped / max(len(combined_df), 1)
        logger.info(
            f"Deduplication: {n_deduped} duplicates removed "
            f"({dedup_rate:.1f}%) — {len(dedup_df)} unique terms remain"
        )

        # ---- Step 6: LLM Classification ----
        logger.info("=" * 60)
        logger.info("Step 6: LLM classification of non-authoritative terms")
        logger.info("=" * 60)

        if not mock:
            classifier = MedicalTermClassifier(self.config, mock=False)
            classified_df = classifier.classify(dedup_df)
        else:
            classified_df = self._mock_classify(dedup_df)

        n_auth = int(
            classified_df["source_name"].isin(AUTHORITATIVE_SOURCES).sum()
        )
        n_llm = int(
            (~classified_df["source_name"].isin(AUTHORITATIVE_SOURCES)).sum()
        )
        logger.info(f"Classification: {n_auth} authoritative + {n_llm} LLM-classified")

        # ---- Step 7: Export CSVs ----
        logger.info("=" * 60)
        logger.info("Step 7: Exporting CSV files")
        logger.info("=" * 60)

        self._export_csvs(classified_df, norm_map_df, dedup_map_df)

        # ---- Step 8: Generate report ----
        logger.info("=" * 60)
        logger.info("Step 8: Generating term inventory report")
        logger.info("=" * 60)

        stats = generate_term_inventory_report(classified_df, norm_map_df)

        elapsed = time.time() - t0
        stats["elapsed_seconds"] = round(elapsed, 2)

        # Compute counts for final summary
        auth_count = int(
            classified_df["source_name"].isin(AUTHORITATIVE_SOURCES).sum()
        )
        llm_count = int(
            (~classified_df["source_name"].isin(AUTHORITATIVE_SOURCES)).sum()
        )
        review_status_col = (
            classified_df["review_status"]
            .astype(str)
            .str.strip()
            .str.lower()
        )
        review_queue = int(
            (
                review_status_col.isin(["needs_review", "not_verified"])
                | (classified_df["llm_generated_candidate"].astype(str).str.lower() == "true")
            ).sum()
        )

        stats["authoritative_count"] = auth_count
        stats["llm_candidate_count"] = llm_count
        stats["review_queue_count"] = review_queue
        stats["total_terms"] = len(classified_df)
        stats["normalization_map_count"] = len(norm_map_df)
        stats["deduplication_count"] = n_deduped

        logger.info(
            f"\n{'=' * 60}\n"
            f"Pipeline complete in {elapsed:.2f}s\n"
            f"Total terms: {stats['total_terms']} | "
            f"Auth: {auth_count} | "
            f"LLM: {llm_count} | "
            f"Review queue: {review_queue}\n"
            f"{'=' * 60}"
        )

        return stats

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _load_all_sources(self, limit: int | None) -> dict[str, pd.DataFrame]:
        """Load terms from all 6 sources, returning {source_name: DataFrame}.

        Each loader is called in sequence. Empty DataFrames from a loader are
        silently skipped. FileNotFoundError and network errors are caught per
        source so one failing loader does not block the whole pipeline.

        Args:
            limit: If set, truncate each source DataFrame to this many rows.

        Returns:
            Dict mapping source names to non-empty DataFrames.
        """
        results: dict[str, pd.DataFrame] = {}

        loaders = [
            ("icd10", self.icd10_loader),
            ("rxnorm", self.rxnorm_loader),
            ("nlm_lab", self.nlm_lab_loader),
            ("openfda", self.openfda_loader),
            ("abbreviation", self.abbreviation_loader),
            ("vimedcss_seed", self.vimedcss_seed_loader),
        ]

        for name, loader in loaders:
            try:
                df = loader.load()
                if df.empty:
                    logger.warning(f"[{name}] loader returned 0 rows — skipped")
                    continue

                # Strip per-loader local term_id; builder assigns global IDs after concat
                if "term_id" in df.columns:
                    df = df.drop(columns=["term_id"])

                if limit:
                    df = df.head(limit)

                results[name] = df
                logger.info(f"[{name}] loaded {len(df)} terms")

            except FileNotFoundError as e:
                logger.warning(f"[{name}] file not found — skipped: {e}")
            except Exception as e:
                logger.error(f"[{name}] loader failed — skipped: {e}")

        return results

    def _mock_classify(self, df: pd.DataFrame) -> pd.DataFrame:
        """Keyword-based mock classification for smoke tests.

        For authoritative sources (icd10, rxnorm, openfda), entity_type is
        preserved as-is. For all non-authoritative terms, medical_domain is set
        to "unknown" and needs_human_review is set to True.

        Args:
            df: DataFrame after deduplication.

        Returns:
            DataFrame with llm_generated_candidate=True and review_status set
            for non-authoritative rows.
        """
        df = df.copy()

        # Ensure boolean column exists
        if "llm_generated_candidate" not in df.columns:
            df["llm_generated_candidate"] = False

        # Non-authoritative: mark as LLM candidate
        non_auth_mask = ~df["source_name"].isin(AUTHORITATIVE_SOURCES)

        df.loc[non_auth_mask, "llm_generated_candidate"] = True
        df.loc[non_auth_mask, "medical_domain"] = "unknown"

        # Set review_status to NOT_VERIFIED for non-authoritative
        df.loc[non_auth_mask, "review_status"] = "not_verified"

        n_mock = int(non_auth_mask.sum())
        logger.info(f"[mock] classified {n_mock} non-authoritative terms as 'unknown' domain")

        return df

    def _export_csvs(
        self,
        classified_df: pd.DataFrame,
        norm_map_df: pd.DataFrame,
        dedup_map_df: pd.DataFrame,
    ) -> None:
        """Write the 4 required CSV output files to config.output_dir.

        Args:
            classified_df: Final classified DataFrame (full inventory).
            norm_map_df: Normalization map with term_id.
            dedup_map_df: Deduplication map (not written — for audit only).
        """
        out = self.config.output_dir
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # ---- File 1: medical_term_inventory.csv ----
        inv_cols = [
            "term_id",
            "term_original",
            "term_normalized",
            "entity_type",
            "medical_domain",
            "source_name",
            "source_url",
            "source_license",
            "icd10_code",
            "rxnorm_rxcui",
            "is_code_switch_candidate",
            "review_status",
            "llm_generated_candidate",
            "fetched_at",
        ]
        inv_df = classified_df[[c for c in inv_cols if c in classified_df.columns]].copy()
        inv_path = os.path.join(out, "medical_term_inventory.csv")
        inv_df.to_csv(inv_path, index=False)
        logger.info(f"Written: {inv_path} ({len(inv_df)} rows)")

        # ---- File 2: term_normalization_map.csv ----
        norm_cols = [
            "raw_form",
            "normalized_form",
            "transformation",
            "entity_type",
            "term_id",
        ]
        norm_df = norm_map_df[[c for c in norm_cols if c in norm_map_df.columns]].copy()
        norm_path = os.path.join(out, "term_normalization_map.csv")
        norm_df.to_csv(norm_path, index=False)
        logger.info(f"Written: {norm_path} ({len(norm_df)} rows)")

        # ---- File 3: human_review_terms.csv ----
        review_status_str = (
            classified_df["review_status"].astype(str).str.strip().str.lower()
        )
        llm_candidate_str = (
            classified_df["llm_generated_candidate"].astype(str).str.strip().str.lower()
        )
        is_review = (
            review_status_str.isin(["not_verified", "needs_review"])
            | (llm_candidate_str == "true")
        )
        human_review_df = classified_df[is_review].copy()
        hr_cols = [
            "term_id",
            "term_original",
            "term_normalized",
            "entity_type",
            "medical_domain",
            "source_name",
            "review_status",
            "llm_generated_candidate",
            "needs_human_review_reason",
        ]
        hr_df = human_review_df[[c for c in hr_cols if c in human_review_df.columns]].copy()
        hr_path = os.path.join(out, "human_review_terms.csv")
        hr_df.to_csv(hr_path, index=False)
        logger.info(f"Written: {hr_path} ({len(hr_df)} rows)")

        # ---- File 4: term_sources.csv ----
        if "entity_type" in classified_df.columns:
            source_grp = classified_df.groupby("source_name", dropna=False)
            auth_mask_per_src = (
                classified_df.groupby("source_name")["source_name"]
                .transform(lambda x: x.isin(pd.Series(list(AUTHORITATIVE_SOURCES), dtype=str)))
            )

            source_stats = []
            for source_name, group in source_grp:
                entity_types_list = (
                    group["entity_type"].dropna().unique().tolist()
                )
                source_stats.append({
                    "source_name": source_name if pd.notna(source_name) else "unknown",
                    "source_url": group["source_url"].iloc[0]
                    if "source_url" in group.columns
                    else None,
                    "source_license": group["source_license"].iloc[0]
                    if "source_license" in group.columns
                    else None,
                    "entity_types_provided": ", ".join(sorted(set(entity_types_list))),
                    "term_count": len(group),
                    "authoritative": source_name in AUTHORITATIVE_SOURCES,
                })

            sources_df = pd.DataFrame(source_stats)
        else:
            # Fallback: aggregate by term_count only
            source_counts = classified_df["source_name"].value_counts(dropna=False).reset_index()
            source_counts.columns = ["source_name", "term_count"]
            source_counts["entity_types_provided"] = ""
            source_counts["authoritative"] = source_counts["source_name"].isin(AUTHORITATIVE_SOURCES)
            source_counts["source_url"] = None
            source_counts["source_license"] = None
            sources_df = source_counts[[
                "source_name", "source_url", "source_license",
                "entity_types_provided", "term_count", "authoritative"
            ]]

        src_path = os.path.join(out, "term_sources.csv")
        sources_df.to_csv(src_path, index=False)
        logger.info(f"Written: {src_path} ({len(sources_df)} sources)")

        logger.info(f"\nAll 4 CSV files written to: {out}/")
