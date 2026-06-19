from src.icd10_ingestion.schemas import ICD10Record, ICD10ErrorRecord
from src.icd10_ingestion.fetcher import ICD10Fetcher
from src.icd10_ingestion.parser import ICD10Parser
from src.icd10_ingestion.joiner import ICD10Joiner
from src.icd10_ingestion.reporter import ICD10Reporter

# Lazily import cli to avoid RuntimeWarning when running as __main__
# via: python -m src.icd10_ingestion.cli
run = None  # type: ignore


def __getattr__(name: str):
    if name == "run":
        global run
        if run is None:
            from src.icd10_ingestion import cli as _cli

            run = _cli.run
        return run
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "ICD10Record",
    "ICD10ErrorRecord",
    "ICD10Fetcher",
    "ICD10Parser",
    "ICD10Joiner",
    "ICD10Reporter",
    "run",
]
