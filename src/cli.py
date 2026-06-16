import sys
import argparse
from src.shared.config import AppConfig
from src.shared.logging import setup_logger
from src.hf_client.download import HFDatasetClient
from src.audit.auditor import MetadataAuditor

logger = setup_logger("cli")

def main():
    parser = argparse.ArgumentParser(
        description="ViMedCSS Term Coverage & ASR Evaluation Pipeline Command Line Interface"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Sub-commands")
    
    # Download metadata command
    subparsers.add_parser("download-metadata", help="Download only metadata CSV files from Hugging Face dataset repo")
    
    # Audit metadata command
    subparsers.add_parser("audit-metadata", help="Run metadata schema audit and statistics checks")
    
    # Extract terms command
    subparsers.add_parser("extract-terms", help="Extract and normalize code-switching medical terms from metadata")
    
    # Classify terms command
    classify_parser = subparsers.add_parser("classify-terms", help="Classify unique code-switching medical terms using LLM")
    classify_parser.add_argument("--mock", action="store_true", help="Use mock classification without calling OpenAI API")
    classify_parser.add_argument("--limit", type=int, default=None, help="Limit the number of terms to classify (useful for testing)")

    # Match external command
    match_parser = subparsers.add_parser("match-external", help="Match ViMedCSS terms against external medical reference lexicon")
    match_parser.add_argument("--mock", action="store_true", help="Use built-in synthetic pilot inventory for smoke testing")
    match_parser.add_argument("--limit", type=int, default=None, help="Limit the number of ViMedCSS terms to process (useful for testing)")

    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
        
    try:
        config = AppConfig()
    except Exception as e:
        logger.error(f"Failed to load application configuration: {e}")
        sys.exit(1)
        
    if args.command == "download-metadata":
        logger.info("Starting Hugging Face metadata acquisition...")
        try:
            client = HFDatasetClient(config.get_dataset_config())
            manifest = client.download_metadata_only()
            logger.info("Metadata acquisition completed successfully!")
            print(f"Manifest created at: outputs/audit/hf_file_manifest.json")
            print(f"Revision hash: {manifest['revision']}")
        except Exception as e:
            logger.error(f"Download metadata failed: {e}")
            sys.exit(1)
            
    elif args.command == "audit-metadata":
        logger.info("Starting local metadata audit...")
        try:
            auditor = MetadataAuditor(config.get_dataset_config())
            stats = auditor.run_audit()
            logger.info("Metadata audit completed successfully!")
            print(f"Total rows audited: {stats['total_rows']}")
            print(f"Total duration: {stats['total_duration_hours']} hours ({stats['total_duration_seconds']} seconds)")
            print(f"Schema report generated at: outputs/audit/metadata_schema_report.md")
        except Exception as e:
            logger.error(f"Audit metadata failed: {e}")
            sys.exit(1)

    elif args.command == "extract-terms":
        logger.info("Starting code-switching term extraction and normalization...")
        try:
            from src.terms.extractor import TermExtractor
            extractor = TermExtractor(config.get_dataset_config(), config.get_taxonomy_config())
            stats = extractor.extract_and_analyze()
            logger.info("Term extraction completed successfully!")
            print(f"Total unique terms extracted: {stats['total_unique_normalized_terms']}")
            print(f"Total occurrences: {stats['total_raw_term_occurrences']}")
            print(f"Common terms (>=20): {stats['common_terms_count']}")
            print(f"Rare terms (<5): {stats['rare_terms_count']}")
            print(f"Hard-only terms: {stats['hard_only_terms_count']}")
            print(f"Unseen in train terms: {stats['unseen_in_train_terms_count']}")
            print(f"Inventory saved at: outputs/term_coverage/cs_terms_inventory.csv")
        except Exception as e:
            logger.error(f"Extract terms failed: {e}")
            sys.exit(1)

    elif args.command == "classify-terms":
        logger.info("Starting code-switching term taxonomy classification...")
        try:
            from src.llm.classifier import TermClassifier
            classifier = TermClassifier(
                config.get_dataset_config(),
                config.get_taxonomy_config(),
                config.get_llm_config()
            )
            stats = classifier.classify(mock=args.mock, limit=args.limit)
            logger.info("Term taxonomy classification completed successfully!")
            print(f"Total unique terms classified: {stats['total_classified']}")
            print(f"Terms requiring human review: {stats['needs_human_review_count']}")
            print(f"Audit log: outputs/term_coverage/llm_classification_audit.jsonl")
            print(f"Summary generated at: outputs/term_coverage/term_taxonomy_summary.md")
        except Exception as e:
            logger.error(f"Classify terms failed: {e}")
            sys.exit(1)

    elif args.command == "match-external":
        logger.info("Starting external reference matching...")
        try:
            from src.terms.external import ExternalReferenceMatcher
            ext_config = config.get_external_config()
            matcher = ExternalReferenceMatcher(
                config.get_dataset_config(),
                config.get_taxonomy_config(),
                ext_config
            )
            if args.mock:
                import tempfile
                mock_dir = tempfile.mkdtemp()
                mock_inv_path = ExternalReferenceMatcher.build_mock_inventory(mock_dir)
                matcher.inventory_dir = mock_dir
                logger.info(f"Mock mode: using synthetic inventory at {mock_inv_path}")
            stats = matcher.run()
            logger.info("External reference matching completed successfully!")
            print(f"External term count: {stats['external_term_count']}")
            print(f"ViMedCSS covered count: {stats['vimedcss_covered_count']}")
            print(f"Overall coverage ratio: {stats['coverage_ratio']:.2%}")
            print(f"Missing high-priority terms: {stats['missing_high_priority_count']}")
            print(f"Registry: outputs/term_coverage/external_sources_registry.csv")
            print(f"External inventory: outputs/term_coverage/external_medical_term_inventory.csv")
            print(f"Coverage CSV: outputs/term_coverage/vimedcss_vs_external_coverage.csv")
            print(f"Summary: outputs/term_coverage/external_coverage_summary.md")
        except Exception as e:
            logger.error(f"Match external failed: {e}")
            sys.exit(1)

if __name__ == "__main__":
    main()
