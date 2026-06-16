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

if __name__ == "__main__":
    main()
