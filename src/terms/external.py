import os
import pandas as pd
from typing import Dict, Any, List
from src.shared.logging import setup_logger

logger = setup_logger("terms.external")


class ExternalReferenceMatcher:
    """Matches ViMedCSS code-switching terms against an external medical reference lexicon.
    
    Phase 3 pilot implementation uses case-insensitive exact matching.
    All coverage numbers are computed from local CSV files only.
    """
    
    REQUIRED_REGISTRY_COLS = [
        "source_name", "source_url", "license_or_access_note",
        "include_in_pilot", "coverage_notes"
    ]
    REQUIRED_INVENTORY_COLS = [
        "term_id", "canonical_term", "language", "entity_category",
        "medical_domain", "specialty", "source_name", "commonness_level",
        "commonness_source", "include_in_pilot", "notes"
    ]
    REQUIRED_COVERAGE_COLS = [
        "group_key", "external_term_count", "vimedcss_covered_count",
        "coverage_ratio", "missing_high_priority_count"
    ]
    
    def __init__(
        self,
        dataset_config: Dict[str, Any],
        taxonomy_config: Dict[str, Any],
        external_config: Dict[str, Any]
    ):
        self.dataset_config = dataset_config
        self.taxonomy_config = taxonomy_config
        self.external_config = external_config
        
        self.output_dir = external_config.get("output_dir", "outputs/term_coverage")
        self.inventory_dir = external_config.get("inventory_dir", "data/raw/external/")
        self.match_mode = external_config.get("match_mode", "exact_case_insensitive")
        self.min_high_priority = external_config.get("min_commonness_for_high_priority", 5)
        
        self.vimedcss_inventory_path = os.path.join(self.output_dir, "cs_terms_inventory.csv")
        self.registry_path = os.path.join(self.output_dir, "external_sources_registry.csv")
        self.external_inventory_path = os.path.join(self.output_dir, "external_medical_term_inventory.csv")
        self.coverage_path = os.path.join(self.output_dir, "vimedcss_vs_external_coverage.csv")
        self.summary_path = os.path.join(self.output_dir, "external_coverage_summary.md")
    
    def run(self) -> Dict[str, Any]:
        """Execute the full external reference matching pipeline.
        
        Returns:
            dict of statistics: external_term_count, vimedcss_covered_count,
            coverage_ratio, missing_high_priority_count
        """
        os.makedirs(self.output_dir, exist_ok=True)
        
        # 1. Build source registry
        self._build_registry()
        
        # 2. Load external inventory
        external_df = self._load_inventory()
        
        # 3. Load ViMedCSS terms
        vimedcss_df = self._load_vimedcss_inventory()
        
        # 4. Match terms
        matched_df = self._match_terms(vimedcss_df, external_df)
        
        # 5. Compute coverage
        coverage_stats = self._compute_coverage(matched_df, external_df)
        
        # 6. Write summary markdown
        self._write_summary(coverage_stats, matched_df, external_df)
        
        logger.info("External reference matching completed successfully!")
        return coverage_stats
    
    # -------------------------------------------------------------------------
    # Registry builder
    # -------------------------------------------------------------------------
    
    def _build_registry(self) -> None:
        """Write external_sources_registry.csv from pilot_sources config."""
        sources = self.external_config.get("pilot_sources", [])
        rows = []
        for src in sources:
            rows.append({
                "source_name": src.get("name", ""),
                "source_url": src.get("source_url", ""),
                "license_or_access_note": src.get("license_or_access_note", ""),
                "include_in_pilot": src.get("include_in_pilot", False),
                "coverage_notes": src.get("coverage_notes", ""),
            })
        
        registry_df = pd.DataFrame(rows, columns=self.REQUIRED_REGISTRY_COLS)
        registry_df.to_csv(self.registry_path, index=False)
        logger.info(f"Registry written to {self.registry_path} with {len(registry_df)} source(s).")
    
    # -------------------------------------------------------------------------
    # Inventory loader
    # -------------------------------------------------------------------------
    
    def _load_inventory(self) -> pd.DataFrame:
        """Load external medical term inventory from inventory_dir.
        
        For Phase 3 pilot (--mock mode), a synthetic fixture is used.
        Raises FileNotFoundError if inventory is missing.
        """
        if not os.path.exists(self.inventory_dir):
            raise FileNotFoundError(
                f"External inventory directory not found: {self.inventory_dir}. "
                "Use --mock for smoke testing or provide an inventory path."
            )
        
        # Look for any CSV in the inventory dir
        csv_files = [f for f in os.listdir(self.inventory_dir) if f.endswith(".csv")]
        if not csv_files:
            # Return empty DataFrame with required columns for empty-inventory handling
            logger.warning("No CSV files found in inventory dir. Returning empty inventory.")
            return pd.DataFrame(columns=self.REQUIRED_INVENTORY_COLS)
        
        # Load the first CSV found
        inv_path = os.path.join(self.inventory_dir, csv_files[0])
        df = pd.read_csv(inv_path)
        
        # Validate required columns
        missing = [c for c in self.REQUIRED_INVENTORY_COLS if c not in df.columns]
        if missing:
            raise ValueError(
                f"External inventory missing required columns: {missing}. "
                f"Found columns: {list(df.columns)}"
            )
        
        # Deduplicate by canonical_term (case-insensitive), first occurrence wins
        initial_count = len(df)
        df["_canonical_lower"] = df["canonical_term"].astype(str).str.lower()
        df = df.drop_duplicates(subset=["_canonical_lower"], keep="first")
        df = df.drop(columns=["_canonical_lower"])
        
        if len(df) < initial_count:
            logger.warning(
                f"Removed {initial_count - len(df)} duplicate canonical_term(s) "
                "(case-insensitive, first occurrence kept)."
            )
        
        # Warn about non-string normalized_term values
        if "canonical_term" in df.columns:
            non_string = df["canonical_term"].apply(lambda x: not isinstance(x, str))
            if non_string.any():
                logger.warning(
                    f"Found {non_string.sum()} non-string canonical_term values. "
                    "Converting to string."
                )
                df["canonical_term"] = df["canonical_term"].astype(str)
        
        logger.info(f"Loaded {len(df)} external inventory terms from {inv_path}.")
        return df
    
    # -------------------------------------------------------------------------
    # ViMedCSS inventory loader
    # -------------------------------------------------------------------------
    
    def _load_vimedcss_inventory(self) -> pd.DataFrame:
        """Load the ViMedCSS terms inventory CSV."""
        if not os.path.exists(self.vimedcss_inventory_path):
            raise FileNotFoundError(
                f"ViMedCSS inventory not found: {self.vimedcss_inventory_path}. "
                "Run term extraction and classification first."
            )
        df = pd.read_csv(self.vimedcss_inventory_path)
        logger.info(f"Loaded {len(df)} ViMedCSS terms.")
        return df
    
    # -------------------------------------------------------------------------
    # Matcher
    # -------------------------------------------------------------------------
    
    def _match_terms(
        self, vimedcss_df: pd.DataFrame, external_df: pd.DataFrame
    ) -> pd.DataFrame:
        """Perform case-insensitive exact match between ViMedCSS and external inventory.
        
        All ViMedCSS terms are preserved; unmatched terms get external_match_status=missing.
        """
        if external_df.empty:
            # Empty external inventory: all terms are missing
            logger.warning("External inventory is empty. All ViMedCSS terms marked as missing.")
            result = vimedcss_df.copy()
            result["external_match_status"] = "missing"
            result["external_canonical_term"] = ""
            result["external_source"] = ""
            return result
        
        # Build a lowercase set of external canonical terms for O(1) lookup
        ext_lower_map: Dict[str, str] = {}
        for _, row in external_df.iterrows():
            key = str(row["canonical_term"]).lower()
            ext_lower_map[key] = str(row["canonical_term"])
        
        ext_source_map: Dict[str, str] = {}
        for _, row in external_df.iterrows():
            key = str(row["canonical_term"]).lower()
            ext_source_map[key] = str(row.get("source_name", ""))
        
        statuses: List[str] = []
        ext_terms: List[str] = []
        ext_sources: List[str] = []
        
        for term in vimedcss_df["normalized_term"]:
            term_lower = str(term).lower()
            if term_lower in ext_lower_map:
                statuses.append("covered")
                ext_terms.append(ext_lower_map[term_lower])
                ext_sources.append(ext_source_map[term_lower])
            else:
                statuses.append("missing")
                ext_terms.append("")
                ext_sources.append("")
        
        result = vimedcss_df.copy()
        result["external_match_status"] = statuses
        result["external_canonical_term"] = ext_terms
        result["external_source"] = ext_sources
        
        covered = sum(1 for s in statuses if s == "covered")
        logger.info(
            f"Matched {covered}/{len(vimedcss_df)} ViMedCSS terms "
            f"({covered / len(vimedcss_df) * 100:.1f}% coverage)."
        )
        
        return result
    
    # -------------------------------------------------------------------------
    # Coverage calculator
    # -------------------------------------------------------------------------
    
    def _compute_coverage(
        self, matched_df: pd.DataFrame, external_df: pd.DataFrame
    ) -> Dict[str, Any]:
        """Compute coverage ratios by entity_category and medical_domain using pandas."""
        coverage_rows: List[Dict[str, Any]] = []
        
        # Group by entity_category
        for group_col in ["entity_category", "medical_domain"]:
            if group_col not in matched_df.columns:
                continue
            
            groups = matched_df.groupby(group_col, dropna=False)
            
            for group_name, group_df in groups:
                group_name_str = str(group_name) if pd.notna(group_name) else "unknown"
                
                vimedcss_count = len(group_df)
                covered_count = (group_df["external_match_status"] == "covered").sum()
                
                # Missing high-priority: missing from external AND common enough
                is_missing = group_df["external_match_status"] == "missing"
                is_common = group_df["occurrence_count"] >= self.min_high_priority
                missing_high_priority = int((is_missing & is_common).sum())
                
                coverage_ratio = (
                    covered_count / vimedcss_count if vimedcss_count > 0 else 0.0
                )
                
                coverage_rows.append({
                    "group_key": group_name_str,
                    "external_term_count": len(external_df),
                    "vimedcss_covered_count": covered_count,
                    "coverage_ratio": round(coverage_ratio, 4),
                    "missing_high_priority_count": missing_high_priority,
                })
        
        coverage_df = pd.DataFrame(coverage_rows, columns=self.REQUIRED_COVERAGE_COLS)
        coverage_df.to_csv(self.coverage_path, index=False)
        logger.info(f"Coverage table saved to {self.coverage_path}.")
        
        # Write external inventory copy
        external_df.to_csv(self.external_inventory_path, index=False)
        logger.info(f"External inventory copy saved to {self.external_inventory_path}.")
        
        # Overall stats
        total_vimedcss = len(matched_df)
        total_covered = (matched_df["external_match_status"] == "covered").sum()
        total_missing_hp = int(
            (
                (matched_df["external_match_status"] == "missing") &
                (matched_df["occurrence_count"] >= self.min_high_priority)
            ).sum()
        )
        overall_ratio = total_covered / total_vimedcss if total_vimedcss > 0 else 0.0
        
        return {
            "external_term_count": len(external_df),
            "vimedcss_covered_count": int(total_covered),
            "coverage_ratio": round(overall_ratio, 4),
            "missing_high_priority_count": total_missing_hp,
        }
    
    # -------------------------------------------------------------------------
    # Summary writer
    # -------------------------------------------------------------------------
    
    def _write_summary(
        self,
        coverage_stats: Dict[str, Any],
        matched_df: pd.DataFrame,
        external_df: pd.DataFrame
    ) -> None:
        """Generate external_coverage_summary.md in Vietnamese with pilot disclaimer."""
        lines: List[str] = []
        lines.append("# Tổng quan Phủ sóng Thuật ngữ Y tế với Nguồn Tham chiếu Bên ngoài")
        lines.append("")
        lines.append("**Giai đoạn thử nghiệm (Pilot) - Phase 3**")
        lines.append("")
        lines.append("> **Tuyên bố giới hạn phạm vi:** Đây là bộ thuật ngữ thử nghiệm (pilot inventory) được ")
        lines.append("> tổng hợp từ các nguồn tham chiếu đã được xác minh. Bộ thuật ngữ này **không** đại diện ")
        lines.append("> cho một bảng phân loại y tế đầy đủ (ICD-10, ATC, MedDRA, v.v.) và chỉ bao gồm các thuật ")
        lines.append("> ngữ thuộc phạm vi nghiên cứu của dự án ViMedCSS.")
        lines.append("")
        lines.append("## 1. Tổng quan Tỷ lệ Phủ sóng")
        lines.append("")
        
        total_ext = coverage_stats["external_term_count"]
        total_covered = coverage_stats["vimedcss_covered_count"]
        total_vimedcss = len(matched_df)
        total_ratio = coverage_stats["coverage_ratio"]
        total_missing_hp = coverage_stats["missing_high_priority_count"]
        
        lines.append(f"| Chỉ số | Giá trị |")
        lines.append(f"|--------|---------|")
        lines.append(f"| Tổng số thuật ngữ trong kho tham chiếu bên ngoài | {total_ext} |")
        lines.append(f"| Tổng số thuật ngữ ViMedCSS được phủ sóng | {total_covered} |")
        lines.append(f"| Tổng số thuật ngữ ViMedCSS | {total_vimedcss} |")
        lines.append(f"| Tỷ lệ phủ sóng tổng thể | {total_ratio:.2%} |")
        lines.append(f"| Số thuật ngữ ưu tiên cao bị thiếu (missing) | {total_missing_hp} |")
        lines.append("")
        
        # Coverage by entity category
        lines.append("## 2. Tỷ lệ Phủ sóng theo Entity Category")
        lines.append("")
        if "entity_category" in matched_df.columns:
            cat_groups = matched_df.groupby("entity_category", dropna=False)
            lines.append("| Entity Category | Tổng | Được phủ sóng | Tỷ lệ | Thiếu ưu tiên cao |")
            lines.append("|---|---|---|---|---|")
            for cat, grp in sorted(cat_groups.groups.keys()):
                grp = cat_groups.get_group(cat)
                total = len(grp)
                covered = (grp["external_match_status"] == "covered").sum()
                ratio = covered / total if total > 0 else 0
                is_missing = grp["external_match_status"] == "missing"
                is_common = grp["occurrence_count"] >= self.min_high_priority
                missing_hp = int((is_missing & is_common).sum())
                cat_str = str(cat) if pd.notna(cat) else "unknown"
                lines.append(
                    f"| {cat_str} | {total} | {covered} | {ratio:.2%} | {missing_hp} |"
                )
        lines.append("")
        
        # Coverage by medical domain
        lines.append("## 3. Tỷ lệ Phủ sóng theo Medical Domain")
        lines.append("")
        if "medical_domain" in matched_df.columns:
            dom_groups = matched_df.groupby("medical_domain", dropna=False)
            lines.append("| Medical Domain | Tổng | Được phủ sóng | Tỷ lệ | Thiếu ưu tiên cao |")
            lines.append("|---|---|---|---|---|")
            for dom, grp in sorted(dom_groups.groups.keys()):
                grp = dom_groups.get_group(dom)
                total = len(grp)
                covered = (grp["external_match_status"] == "covered").sum()
                ratio = covered / total if total > 0 else 0
                is_missing = grp["external_match_status"] == "missing"
                is_common = grp["occurrence_count"] >= self.min_high_priority
                missing_hp = int((is_missing & is_common).sum())
                dom_str = str(dom) if pd.notna(dom) else "unknown"
                lines.append(
                    f"| {dom_str} | {total} | {covered} | {ratio:.2%} | {missing_hp} |"
                )
        lines.append("")
        
        # Missing high-priority terms
        lines.append("## 4. Các thuật ngữ Ưu tiên cao Bị Thiếu (Top 20)")
        lines.append("")
        missing_hp_df = matched_df[
            (matched_df["external_match_status"] == "missing") &
            (matched_df["occurrence_count"] >= self.min_high_priority)
        ].sort_values("occurrence_count", ascending=False).head(20)
        
        if not missing_hp_df.empty:
            lines.append("| Thuật ngữ | Entity Category | Medical Domain | Số lần xuất hiện |")
            lines.append("|---|---|---|---|")
            for _, row in missing_hp_df.iterrows():
                norm_term = row.get("normalized_term", "")
                entity_cat = row.get("entity_category", "unknown")
                med_domain = row.get("medical_domain", "unknown")
                occ = row.get("occurrence_count", 0)
                lines.append(f"| {norm_term} | {entity_cat} | {med_domain} | {occ} |")
        else:
            lines.append("*Không có thuật ngữ ưu tiên cao nào bị thiếu.*")
        lines.append("")
        
        # Registry summary
        lines.append("## 5. Nguồn Tham chiếu Bên ngoài (Đã đăng ký)")
        lines.append("")
        if os.path.exists(self.registry_path):
            reg_df = pd.read_csv(self.registry_path)
            lines.append("| Tên nguồn | URL | License/Ghi chú truy cập | Pilot |")
            lines.append("|---|---|---|---|")
            for _, row in reg_df.iterrows():
                name = row.get("source_name", "")
                url = row.get("source_url", "")
                license_note = row.get("license_or_access_note", "")
                pilot = "Có" if row.get("include_in_pilot", False) else "Không"
                lines.append(f"| {name} | {url} | {license_note} | {pilot} |")
        else:
            lines.append("*Chưa có nguồn tham chiếu nào được đăng ký.*")
        lines.append("")
        
        # Limitations section
        lines.append("## 6. Giới hạn của Phạm vi Pilot")
        lines.append("")
        lines.append("- Đây **không phải** là bảng phân loại y tế đầy đủ (ICD-10, ATC, MedDRA, SNOMED CT, v.v.)")
        lines.append("- Các nguồn tham chiếu có giấy phép hạn chế không được tải lên kho")
        lines.append("- Tỷ lệ phủ sóng được tính **chỉ từ các tệp CSV cục bộ** — không có số liệu bịa đặt")
        lines.append("- So khớp chính xác (exact, không phân biệt hoa thường) cho Phase 3 pilot")
        lines.append("")
        lines.append("*Tệp này được tạo tự động bởi viMedCSS Evaluation Pipeline — Phase 3.*")
        
        content = "\n".join(lines)
        with open(self.summary_path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"Summary markdown saved to {self.summary_path}.")
    
    # -------------------------------------------------------------------------
    # Mock fixture helper (used by CLI --mock flag)
    # -------------------------------------------------------------------------
    
    @staticmethod
    def build_mock_inventory(tmp_dir: str) -> str:
        """Write a synthetic pilot external inventory CSV to tmp_dir.
        
        Returns the path to the created file.
        """
        os.makedirs(tmp_dir, exist_ok=True)
        
        mock_data = [
            {
                "term_id": "ext_001",
                "canonical_term": "metformin",
                "language": "en",
                "entity_category": "drug_or_active_ingredient",
                "medical_domain": "Treatments",
                "specialty": "endocrinology",
                "source_name": "ViMedCSS Internal Pilot Lexicon",
                "commonness_level": "common",
                "commonness_source": "ViMedCSS domain analysis",
                "include_in_pilot": True,
                "notes": "Synthetic pilot term for Phase 3 smoke test",
            },
            {
                "term_id": "ext_002",
                "canonical_term": "diabetes",
                "language": "en",
                "entity_category": "disease_or_condition",
                "medical_domain": "Medical Sciences",
                "specialty": "endocrinology",
                "source_name": "ViMedCSS Internal Pilot Lexicon",
                "commonness_level": "common",
                "commonness_source": "ViMedCSS domain analysis",
                "include_in_pilot": True,
                "notes": "Synthetic pilot term for Phase 3 smoke test",
            },
            {
                "term_id": "ext_003",
                "canonical_term": "hba1c",
                "language": "en",
                "entity_category": "lab_test_or_biomarker",
                "medical_domain": "Diagnostics",
                "specialty": "laboratory_medicine",
                "source_name": "ViMedCSS Internal Pilot Lexicon",
                "commonness_level": "medium",
                "commonness_source": "ViMedCSS domain analysis",
                "include_in_pilot": True,
                "notes": "Synthetic pilot term for Phase 3 smoke test",
            },
            {
                "term_id": "ext_004",
                "canonical_term": "stent",
                "language": "en",
                "entity_category": "device_or_technology",
                "medical_domain": "Treatments",
                "specialty": "cardiology",
                "source_name": "ViMedCSS Internal Pilot Lexicon",
                "commonness_level": "medium",
                "commonness_source": "ViMedCSS domain analysis",
                "include_in_pilot": True,
                "notes": "Synthetic pilot term for Phase 3 smoke test",
            },
            {
                "term_id": "ext_005",
                "canonical_term": "asthma",
                "language": "en",
                "entity_category": "disease_or_condition",
                "medical_domain": "Medical Sciences",
                "specialty": "respiratory",
                "source_name": "ViMedCSS Internal Pilot Lexicon",
                "commonness_level": "common",
                "commonness_source": "ViMedCSS domain analysis",
                "include_in_pilot": True,
                "notes": "Synthetic pilot term for Phase 3 smoke test",
            },
        ]
        
        df = pd.DataFrame(mock_data)
        out_path = os.path.join(tmp_dir, "external_pilot_inventory.csv")
        df.to_csv(out_path, index=False)
        return out_path
