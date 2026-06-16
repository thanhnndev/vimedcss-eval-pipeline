import os
import json
import time
import pandas as pd
from typing import Dict, Any, List
from openai import OpenAI
from src.shared.logging import setup_logger
from src.llm.schemas import (
    TermClassificationBatchResponse,
    TermClassificationItem,
    EntityCategory,
    MedicalDomain,
    MedicalSpecialty
)

logger = setup_logger("classifier")

class TermClassifier:
    """Classifies unique code-switching medical terms using the OpenAI Structured Outputs API."""
    
    def __init__(self, dataset_config: Dict[str, Any], taxonomy_config: Dict[str, Any], llm_config: Dict[str, Any]):
        self.dataset_config = dataset_config
        self.taxonomy_config = taxonomy_config
        self.llm_config = llm_config
        self.output_dir = "outputs/term_coverage"
        self.inventory_path = os.path.join(self.output_dir, "cs_terms_inventory.csv")
        self.audit_log_path = os.path.join(self.output_dir, "llm_classification_audit.jsonl")
        
    def classify(self, mock: bool = False, limit: int = None) -> Dict[str, Any]:
        """Loads terms, batch classifies them, logs audit records, and updates inventory files."""
        if not os.path.exists(self.inventory_path):
            raise FileNotFoundError(f"CS terms inventory file not found: {self.inventory_path}. Run extraction first.")
            
        df = pd.read_csv(self.inventory_path)
        if df.empty:
            logger.info("The inventory is empty. Nothing to classify.")
            return {"total_classified": 0}
            
        logger.info(f"Loaded {len(df)} unique terms for taxonomy classification.")
        
        # Prepare inputs for LLM
        term_payloads = []
        for _, row in df.iterrows():
            # Parse splits, topics, and example texts
            splits = str(row["splits_present"]).split(";") if pd.notna(row["splits_present"]) else []
            topics = str(row["topics_present"]).split(";") if pd.notna(row["topics_present"]) else []
            examples = str(row["example_texts"]).split(";") if pd.notna(row["example_texts"]) else []
            raw_forms = str(row["raw_forms"]).split(";") if pd.notna(row["raw_forms"]) else []
            
            term_payloads.append({
                "normalized_term": str(row["normalized_term"]),
                "raw_forms": raw_forms,
                "occurrence_count": int(row["occurrence_count"]),
                "splits_present": splits,
                "topics_present": topics,
                "example_texts": examples[:5],  # limit to top 5 context sentences to save tokens
                "known_source_matches": []
            })
            
        if limit is not None:
            logger.info(f"Limiting classification to the first {limit} terms.")
            term_payloads = term_payloads[:limit]
            
        # Run classification
        classifications: Dict[str, TermClassificationItem] = {}
        
        if mock:
            logger.info("Mock mode enabled. Generating synthetic classifications...")
            mock_items = self._generate_mock_classifications(term_payloads)
            for item in mock_items:
                classifications[item.normalized_term] = item
        else:
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable is required for live classification.")
                
            client = OpenAI(api_key=api_key)
            batch_size = self.llm_config.get("batch_size", 50)
            
            for i in range(0, len(term_payloads), batch_size):
                batch = term_payloads[i : i + batch_size]
                logger.info(f"Classifying batch {i // batch_size + 1} of {(len(term_payloads) + batch_size - 1) // batch_size}...")
                
                batch_response = self._classify_batch_with_retry(client, batch)
                for item in batch_response.items:
                    classifications[item.normalized_term] = item
                    
        # Update the main inventory DataFrame
        confidence_threshold = self.taxonomy_config.get("confidence_threshold_review", 0.80)
        
        updated_rows = []
        for _, row in df.iterrows():
            term = str(row["normalized_term"])
            cls_item = classifications.get(term)
            
            row_dict = row.to_dict()
            if cls_item:
                row_dict["entity_category"] = cls_item.primary_entity_category.value
                row_dict["medical_domain"] = cls_item.primary_medical_domain.value
                row_dict["specialty"] = cls_item.specialty.value
                row_dict["classification_source"] = "mock" if mock else "openai"
                row_dict["classification_confidence"] = float(cls_item.confidence)
                
                # Check confidence threshold or uncertainty flag
                needs_review = cls_item.needs_human_review or (cls_item.confidence < confidence_threshold)
                row_dict["needs_human_review"] = bool(needs_review)
                
                # Notes combine the evidence and any uncertainty details
                notes_parts = []
                if cls_item.evidence_from_context:
                    notes_parts.append(f"Evidence: {cls_item.evidence_from_context}")
                if cls_item.uncertainty_reason:
                    notes_parts.append(f"Uncertainty: {cls_item.uncertainty_reason}")
                row_dict["notes"] = " | ".join(notes_parts)
                
                # Additional fields from schema: canonical, vietnamese equivalent, etc.
                row_dict["canonical_term"] = cls_item.canonical_term
                row_dict["vietnamese_equivalent"] = cls_item.vietnamese_equivalent
            else:
                # If term was not classified in this run, check if it was previously classified.
                # If so, keep it; otherwise keep placeholder values.
                source = row_dict.get("classification_source", "none")
                if pd.notna(source) and source not in ("none", "failed"):
                    pass
                else:
                    row_dict["classification_source"] = source if pd.notna(source) else "none"
                    row_dict["needs_human_review"] = bool(row_dict.get("needs_human_review", False))
                    row_dict["notes"] = row_dict.get("notes", "")
                    if "canonical_term" not in row_dict or pd.isna(row_dict["canonical_term"]):
                        row_dict["canonical_term"] = term
                    if "vietnamese_equivalent" not in row_dict or pd.isna(row_dict["vietnamese_equivalent"]):
                        row_dict["vietnamese_equivalent"] = "unknown"
                
            updated_rows.append(row_dict)
            
        updated_df = pd.DataFrame(updated_rows)
        
        # Ensure outputs directory exists
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Save updated inventory CSV
        updated_df.to_csv(self.inventory_path, index=False)
        logger.info(f"Updated CS terms inventory saved to {self.inventory_path}")
        
        # Regenerate/update filtered inventory subsets
        self._write_filtered_files(updated_df)
        
        # Generate cs_terms_by_entity_category.csv
        category_df = updated_df[["normalized_term", "occurrence_count", "entity_category", "classification_confidence", "needs_human_review"]].copy()
        category_df = category_df.sort_values(by=["entity_category", "occurrence_count", "normalized_term"], ascending=[True, False, True])
        category_csv = os.path.join(self.output_dir, "cs_terms_by_entity_category.csv")
        category_df.to_csv(category_csv, index=False)
        
        # Generate cs_terms_by_domain.csv
        domain_df = updated_df[["normalized_term", "occurrence_count", "medical_domain", "specialty", "classification_confidence", "needs_human_review"]].copy()
        domain_df = domain_df.sort_values(by=["medical_domain", "specialty", "occurrence_count", "normalized_term"], ascending=[True, True, False, True])
        domain_csv = os.path.join(self.output_dir, "cs_terms_by_domain.csv")
        domain_df.to_csv(domain_csv, index=False)
        
        # Generate term_taxonomy_summary.md
        self._write_taxonomy_summary_md(updated_df)
        
        total_review = int(updated_df["needs_human_review"].sum())
        logger.info("Taxonomy classification completed successfully!")
        
        return {
            "total_classified": len(updated_df),
            "needs_human_review_count": total_review
        }
        
    def _classify_batch_with_retry(self, client: OpenAI, batch: List[Dict[str, Any]]) -> TermClassificationBatchResponse:
        max_retries = self.llm_config.get("max_retries", 3)
        configured_model = self.llm_config.get("model", "gpt-5-mini")
        
        system_prompt = (
            "Bạn là bộ phân loại thuật ngữ y tế chuyên nghiệp cho dự án nghiên cứu ViMedCSS.\n"
            "Nhiệm vụ của bạn là phân loại các thuật ngữ code-switching Anh-Việt được cung cấp dựa trên ngữ cảnh ví dụ.\n"
            "Quy tắc quan trọng:\n"
            "1. Phân loại entity category theo danh sách: drug_or_active_ingredient, disease_or_condition, "
            "lab_test_or_biomarker, procedure_or_intervention, anatomy_or_body_part, hormone_enzyme_protein, "
            "pathogen_or_microbiology, nutrition_or_supplement, chemical_or_biochemical, device_or_technology, "
            "general_medical_english, abbreviation_or_acronym, unknown.\n"
            "2. Phân loại medical domain (Lớp 1) theo: Medical Sciences, Pathology & Pathogens, Treatments, Nutrition, Diagnostics, unknown.\n"
            "3. Phân loại specialty (Lớp 2) theo: endocrinology, cardiology, respiratory, infectious_disease, gastroenterology, "
            "neurology, oncology, obstetrics_gynecology, nephrology, hepatology, immunology, hematology, nutrition, "
            "pharmacology, laboratory_medicine, radiology, surgery, general_medicine, unknown.\n"
            "4. Không được bịa đặt nguồn, không được tự ý thêm bớt hay thay đổi normalized_term.\n"
            "5. Đánh giá độ tin cậy (confidence) từ 0.0 đến 1.0. Nếu có sự mơ hồ lớn hoặc không chắc chắn, đặt needs_human_review = true.\n"
            "6. Cung cấp tương đương tiếng Việt (vietnamese_equivalent) và dạng chuẩn hóa chính xác (canonical_term)."
        )
        
        user_prompt = json.dumps({
            "task": "classify_vimedcss_medical_cs_terms",
            "taxonomy_version": "v1",
            "terms": batch
        }, ensure_ascii=False)
        
        last_error = None
        for attempt in range(max_retries):
            # Attempt structured output using configured model, fallback to gpt-4o-mini if failing
            model = configured_model if attempt == 0 else "gpt-4o-mini"
            try:
                logger.info(f"API Call attempt {attempt + 1} with model {model}...")
                
                # Reasoning models (gpt-5, o1, o3 series) do not support temperature.
                # Per OpenAI docs, use reasoning_effort instead.
                is_reasoning = model.startswith(("o1", "o3", "gpt-5"))
                
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
                
                api_kwargs = {
                    "model": model,
                    "messages": messages,
                    "response_format": TermClassificationBatchResponse
                }
                if is_reasoning:
                    api_kwargs["reasoning_effort"] = "medium"
                else:
                    api_kwargs["temperature"] = 0.0
                
                # Track request payload for audit log
                request_payload = {
                    "model": model,
                    "messages": messages,
                    "response_format": "TermClassificationBatchResponse"
                }
                if is_reasoning:
                    request_payload["reasoning_effort"] = "medium"
                else:
                    request_payload["temperature"] = 0.0
                
                start_time = time.time()
                completion = client.beta.chat.completions.parse(**api_kwargs)
                duration = time.time() - start_time
                
                # Verify parse result
                parsed_response = completion.choices[0].message.parsed
                if not parsed_response:
                    raise ValueError("Failed to parse response into Pydantic model.")
                    
                # Track response payload for audit log
                response_payload = {
                    "id": completion.id,
                    "model": completion.model,
                    "choices": [{
                        "message": {
                            "role": "assistant",
                            "content": completion.choices[0].message.content
                        },
                        "finish_reason": completion.choices[0].finish_reason
                    }],
                    "usage": completion.usage.model_dump() if completion.usage else {},
                    "duration_seconds": duration
                }
                
                # Write to audit log
                self._log_audit(request_payload, response_payload)
                return parsed_response
                
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed with error: {e}")
                last_error = e
                # Backoff
                time.sleep(2 ** attempt)
                
        # If we reach here, all retries failed
        logger.error(f"All API classification attempts failed. Last error: {last_error}")
        raise last_error if last_error else RuntimeError("LLM classification failed.")
        
    def _log_audit(self, request: Dict[str, Any], response: Dict[str, Any]):
        os.makedirs(os.path.dirname(self.audit_log_path), exist_ok=True)
        with open(self.audit_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"request": request, "response": response}, ensure_ascii=False) + "\n")
            
    def _generate_mock_classifications(self, terms: List[Dict[str, Any]]) -> List[TermClassificationItem]:
        items = []
        for t in terms:
            norm = t["normalized_term"]
            
            # Simple keyword-based rules for mock classification
            category = EntityCategory.UNKNOWN
            specialty = MedicalSpecialty.UNKNOWN
            domain = MedicalDomain.UNKNOWN
            canonical = norm
            viet_eq = norm
            evidence = "Mock classification based on keyword matching."
            
            # Entity Categories
            if any(k in norm for k in ["metformin", "insulin", "stent", "drug", "aspirin", "paracetamol"]):
                if "stent" in norm:
                    category = EntityCategory.DEVICE_OR_TECHNOLOGY
                else:
                    category = EntityCategory.DRUG_OR_ACTIVE_INGREDIENT
            elif any(k in norm for k in ["diabetes", "asthma", "pathology", "hepatitis", "cancer", "disease", "hypertension"]):
                category = EntityCategory.DISEASE_OR_CONDITION
            elif any(k in norm for k in ["hba1c", "crp", "egfr", "ast", "alt", "test", "cholesterol", "biomarker"]):
                if "cholesterol" in norm:
                    category = EntityCategory.CHEMICAL_OR_BIOCHEMICAL
                else:
                    category = EntityCategory.LAB_TEST_OR_BIOMARKER
            elif any(k in norm for k in ["ct", "mri", "endoscopy", "scan", "ultrasound", "surgery"]):
                if "ultrasound" in norm:
                    category = EntityCategory.DEVICE_OR_TECHNOLOGY
                else:
                    category = EntityCategory.PROCEDURE_OR_INTERVENTION
            elif any(k in norm for k in ["thyroid", "liver", "kidney", "heart", "lung", "brain"]):
                category = EntityCategory.ANATOMY_OR_BODY_PART
            elif any(k in norm for k in ["estrogen", "renin", "thyroxine", "protein", "enzyme"]):
                category = EntityCategory.HORMONE_ENZYME_PROTEIN
            elif any(k in norm for k in ["virus", "bacteria", "helicobacter", "e. coli", "covid"]):
                category = EntityCategory.PATHOGEN_OR_MICROBIOLOGY
            elif any(k in norm for k in ["vitamin", "supplement", "calcium"]):
                category = EntityCategory.NUTRITION_OR_SUPPLEMENT
            elif any(k in norm for k in ["icu", "ecg", "eeg", "er"]):
                category = EntityCategory.ABBREVIATION_OR_ACRONYM
            elif any(k in norm for k in ["clinical", "symptom", "patient", "medical"]):
                category = EntityCategory.GENERAL_MEDICAL_ENGLISH
                
            # Medical Domain (Lớp 1)
            # Match splits/topics
            topics_present = t.get("topics_present", [])
            if "Medical Sciences" in topics_present:
                domain = MedicalDomain.MEDICAL_SCIENCES
            elif "Pathology & Pathogens" in topics_present:
                domain = MedicalDomain.PATHOLOGY_PATHOGENS
            elif "Treatments" in topics_present:
                domain = MedicalDomain.TREATMENTS
            elif "Nutrition" in topics_present:
                domain = MedicalDomain.NUTRITION
            elif "Diagnostics" in topics_present:
                domain = MedicalDomain.DIAGNOSTICS
            else:
                domain = MedicalDomain.MEDICAL_SCIENCES  # default mock domain
                
            # Specialty (Lớp 2)
            if any(k in norm for k in ["diabetes", "hba1c", "insulin", "thyroid", "renin", "metformin"]):
                specialty = MedicalSpecialty.ENDOCRINOLOGY
            elif any(k in norm for k in ["heart", "cardio", "stent", "ecg", "hypertension"]):
                specialty = MedicalSpecialty.CARDIOLOGY
            elif any(k in norm for k in ["asthma", "lung", "respiratory", "bronchitis"]):
                specialty = MedicalSpecialty.RESPIRATORY
            elif any(k in norm for k in ["virus", "bacteria", "covid", "hepatitis", "infection"]):
                specialty = MedicalSpecialty.INFECTIOUS_DISEASE
            elif any(k in norm for k in ["liver", "hepatology", "alt", "ast"]):
                specialty = MedicalSpecialty.HEPATOLOGY
            elif any(k in norm for k in ["kidney", "nephrology", "egfr"]):
                specialty = MedicalSpecialty.NEPHROLOGY
            elif any(k in norm for k in ["cancer", "oncology", "tumor"]):
                specialty = MedicalSpecialty.ONCOLOGY
            elif any(k in norm for k in ["mri", "ct", "radiology", "ultrasound"]):
                specialty = MedicalSpecialty.RADIOLOGY
            elif any(k in norm for k in ["test", "crp", "cbc", "laboratory"]):
                specialty = MedicalSpecialty.LABORATORY_MEDICINE
            elif any(k in norm for k in ["surgery", "appendix", "procedure"]):
                specialty = MedicalSpecialty.SURGERY
            elif any(k in norm for k in ["vitamin", "nutrition", "supplement"]):
                specialty = MedicalSpecialty.NUTRITION
                
            # Translations
            if norm == "metformin":
                viet_eq = "metformin"
            elif norm == "diabetes":
                viet_eq = "bệnh tiểu đường"
            elif norm == "hba1c":
                viet_eq = "chỉ số hba1c"
            elif norm == "stent":
                viet_eq = "ống đỡ động mạch (stent)"
            else:
                viet_eq = norm
                
            is_abbrev = len(norm) <= 4 and norm.isupper()
            confidence = 0.95 if category != EntityCategory.UNKNOWN else 0.50
            needs_review = confidence < 0.80
            
            items.append(TermClassificationItem(
                normalized_term=norm,
                canonical_term=canonical.capitalize(),
                vietnamese_equivalent=viet_eq,
                primary_entity_category=category,
                secondary_entity_categories=[],
                primary_medical_domain=domain,
                specialty=specialty,
                candidate_domains=[],
                is_abbreviation=is_abbrev,
                is_common_medical_term=True,
                confidence=confidence,
                evidence_from_context=evidence,
                needs_human_review=needs_review,
                uncertainty_reason="Low confidence mock mapping" if needs_review else None
            ))
            
        # Log a mock audit trace
        mock_request = {"task": "mock_classification", "count": len(terms)}
        mock_response = {"status": "success", "items": [item.model_dump() for item in items]}
        self._log_audit(mock_request, mock_response)
        
        return items

    def _write_filtered_files(self, df: pd.DataFrame):
        """Regenerates the filtered inventory CSV files based on the updated main inventory DataFrame."""
        # rare_terms.csv
        rare_df = df[df["frequency_bucket"].isin(["rare", "singleton"])]
        rare_df.to_csv(os.path.join(self.output_dir, "rare_terms.csv"), index=False)
        
        # common_terms.csv
        common_df = df[df["frequency_bucket"] == "common"]
        common_df.to_csv(os.path.join(self.output_dir, "common_terms.csv"), index=False)
        
        # Split overlap lists
        train_terms = set(df[df["splits_present"].fillna("").str.contains("train")]["normalized_term"])
        validation_terms = set(df[df["splits_present"].fillna("").str.contains("validation")]["normalized_term"])
        test_terms = set(df[df["splits_present"].fillna("").str.contains("test")]["normalized_term"])
        hard_terms = set(df[df["splits_present"].fillna("").str.contains("hard")]["normalized_term"])
        
        # hard_only_terms.csv
        hard_only = hard_terms - (train_terms | validation_terms | test_terms)
        hard_only_df = df[df["normalized_term"].isin(hard_only)]
        hard_only_df.to_csv(os.path.join(self.output_dir, "hard_only_terms.csv"), index=False)
        
        # train_seen_hard_terms.csv
        train_seen_hard = hard_terms & train_terms
        train_seen_hard_df = df[df["normalized_term"].isin(train_seen_hard)]
        train_seen_hard_df.to_csv(os.path.join(self.output_dir, "train_seen_hard_terms.csv"), index=False)
        
        # unseen_in_train_terms.csv
        eval_terms = validation_terms | test_terms | hard_terms
        unseen_in_train = eval_terms - train_terms
        unseen_in_train_df = df[df["normalized_term"].isin(unseen_in_train)]
        unseen_in_train_df.to_csv(os.path.join(self.output_dir, "unseen_in_train_terms.csv"), index=False)
        
    def _write_taxonomy_summary_md(self, df: pd.DataFrame):
        """Generates a clean term_taxonomy_summary.md overview of classification results."""
        summary_path = os.path.join(self.output_dir, "term_taxonomy_summary.md")
        
        total_terms = len(df)
        review_count = int(df["needs_human_review"].sum())
        review_pct = (review_count / total_terms * 100) if total_terms > 0 else 0.0
        
        # Entity Category Distribution
        cat_counts = df["entity_category"].value_counts()
        cat_table = []
        for cat, cnt in cat_counts.items():
            pct = (cnt / total_terms * 100)
            cat_table.append(f"| `{cat}` | {cnt} | {pct:.1f}% |")
            
        # Specialty Distribution
        spec_counts = df["specialty"].value_counts()
        spec_table = []
        for spec, cnt in spec_counts.items():
            pct = (cnt / total_terms * 100)
            spec_table.append(f"| `{spec}` | {cnt} | {pct:.1f}% |")
            
        # Domain Distribution
        dom_counts = df["medical_domain"].value_counts()
        dom_table = []
        for dom, cnt in dom_counts.items():
            pct = (cnt / total_terms * 100)
            dom_table.append(f"| `{dom}` | {cnt} | {pct:.1f}% |")
            
        # Terms requiring human review
        review_terms = df[df["needs_human_review"] == True][["normalized_term", "entity_category", "specialty", "classification_confidence", "notes"]].head(20)
        review_table = []
        for _, r in review_terms.iterrows():
            review_table.append(f"| {r['normalized_term']} | `{r['entity_category']}` | `{r['specialty']}` | {r['classification_confidence']:.2f} | {r['notes']} |")
            
        content = f"""# Term Taxonomy Summary

**Tổng số thuật ngữ độc nhất đã phân loại:** {total_terms}
**Cần rà soát thủ công (needs_human_review):** {review_count} ({review_pct:.1f}%)

## 1. Phân phối theo Entity Category

| Entity Category | Số lượng thuật ngữ | Tỷ lệ (%) |
|---|---|---|
{"\n".join(cat_table)}

## 2. Phân phối theo Lớp 1 (Medical Domain)

| Medical Domain | Số lượng thuật ngữ | Tỷ lệ (%) |
|---|---|---|
{"\n".join(dom_table)}

## 3. Phân phối theo Lớp 2 (Specialty)

| Specialty | Số lượng thuật ngữ | Tỷ lệ (%) |
|---|---|---|
{"\n".join(spec_table)}

## 4. Danh sách các thuật ngữ cần rà soát tiêu biểu (tối đa 20 thuật ngữ đầu tiên)

| Thuật ngữ | Entity Category | Specialty | Confidence | Lý do / Ngữ cảnh |
|---|---|---|---|---|
{"\n".join(review_table)}
"""
        with open(summary_path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"Summary markdown saved to {summary_path}")
