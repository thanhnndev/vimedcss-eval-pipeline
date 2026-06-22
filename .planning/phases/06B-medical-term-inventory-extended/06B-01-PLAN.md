---
phase: "06B"
plan: "01"
type: execute
wave: 1
depends_on: []
files_modified:
  - "src/term_inventory/__init__.py"
  - "src/term_inventory/schemas.py"
  - "src/term_inventory/cli.py"
  - "src/term_inventory/loaders/__init__.py"
  - "src/term_inventory/loaders/icd10_backbone.py"
  - "src/term_inventory/loaders/rxnorm_loader.py"
  - "configs/term_inventory.yaml"
autonomous: true
requirements:
  - "FR2-01"
  - "FR2-02"
  - "FR2-04"
  - "FR2-05"
---

<objective>
Create the Phase 6b foundation: the `EntityType` enum (matching FR2-04's 13 types exactly), `MedicalTermRecord` Pydantic schema with all provenance columns, the `BaseLoader` interface, the ICD-10 backbone loader, the RxNorm drug loader, and the CLI entry point with `--mock` and `--full` flags. This plan establishes the data contracts all downstream plans depend on.

Purpose: Without this foundation, no other plan can run — loader outputs, normalization, deduplication, and LLM classification all require these types.
Output: `src/term_inventory/` module with schemas, loaders, and CLI.
</objective>

<execution_context>
@$HOME/.cursor/get-shit-done/workflows/execute-plan.md
</execution_context>

<context>
@data/icd10/mock/icd10_dual_language.csv
@src/llm/schemas.py
@src/llm/classifier.py
@src/terms/external.py
@src/shared/logging.py
@.planning/phases/06B-medical-term-inventory-extended/06B-RESEARCH.md
@.planning/phases/06A-icd-10-dual-language-ingestion/CONTEXT.md

## Phase 6a Output Format (FR2-01 backbone)

The `data/icd10/mock/icd10_dual_language.csv` has these columns:
```
code,level,label_en,label_vi,chapter_code,chapter_label_en,chapter_label_vi,parent_code,source,source_url,fetched_at
```

## Existing Phase 2 EntityCategory Enum (from src/llm/schemas.py)

```python
class EntityCategory(str, Enum):
    UNKNOWN = "unknown"
    DRUG_OR_ACTIVE_INGREDIENT = "drug_or_active_ingredient"
    DISEASE_OR_CONDITION = "disease_or_condition"
    LAB_TEST_OR_BIOMARKER = "lab_test_or_biomarker"
    PROCEDURE_OR_INTERVENTION = "procedure_or_intervention"
    ANATOMY_OR_BODY_PART = "anatomy_or_body_part"
    HORMONE_ENZYME_PROTEIN = "hormone_enzyme_protein"
    PATHOGEN_OR_MICROBIOLOGY = "pathogen_or_microbiology"
    NUTRITION_OR_SUPPLEMENT = "nutrition_or_supplement"
    CHEMICAL_OR_BIOCHEMICAL = "chemical_or_biochemical"
    DEVICE_OR_TECHNOLOGY = "device_or_technology"
    GENERAL_MEDICAL_ENGLISH = "general_medical_english"
    ABBREVIATION_OR_ACRONYM = "abbreviation_or_acronym"
```

## Phase 2 ReviewStatus Enum (extended)

```python
class ReviewStatus(str, Enum):
    VERIFIED = "verified"
    NEEDS_REVIEW = "needs_review"
    NOT_VERIFIED = "not_verified"
```

## Key Interfaces

From `src/terms/external.py` — `REQUIRED_INVENTORY_COLS` pattern:
```python
REQUIRED_INVENTORY_COLS = [
    "term_id", "canonical_term", "language", "entity_category",
    "medical_domain", "specialty", "source_name", "commonness_level",
    "commonness_source", "include_in_pilot", "notes"
]
```

From `src/llm/classifier.py` — LLM client initialization pattern:
```python
from openai import OpenAI
client = OpenAI(api_key=api_key)
batch_size = self.llm_config.get("batch_size", 50)
```

From `src/shared/logging.py` — logger pattern:
```python
from src.shared.logging import setup_logger
logger = setup_logger("module-name")
```

## FR2-04 EntityType Enum (13 types — exact match required)

The Phase 6b `EntityType` enum in `schemas.py` must match these 13 values:
- disease, drug, lab_test, procedure, anatomy, symptom, abbreviation, hormone, biomarker, pathogen, device, unit, dosage, unknown

Note: This is DIFFERENT from Phase 2's `EntityCategory` enum. The mapping table converts Phase 2 outputs to FR2-04 types in Plan 01, but the new enum uses FR2-04 names for the inventory output.
</context>

<tasks>

<task type="auto">
  <name>Task 1: Define EntityType, ReviewStatus, MedicalTermRecord schemas</name>
  <files>src/term_inventory/schemas.py</files>
  <read_first>src/llm/schemas.py</read_first>
  <action>
Create `src/term_inventory/schemas.py` with:

1. `EntityType(str, Enum)` — 14 values: disease, drug, lab_test, procedure, anatomy, symptom, abbreviation, hormone, biomarker, pathogen, device, unit, dosage, unknown

2. `ReviewStatus(str, Enum)` — 4 values: verified, llm_candidate, not_verified, needs_review

3. `TermSource(str, Enum)` — named sources: icd10, rxnorm, openfda, vimedcss_seed, nlm_lab, abbreviation_list, llm_generated, unknown

4. `MedicalTermRecord(BaseModel)` with fields:
   - `term_id: str` — e.g. "term_000001"
   - `term_original: str` — form as ingested from source
   - `term_normalized: str` — post-normalization form
   - `entity_type: EntityType`
   - `medical_domain: Optional[str]` — e.g. "cardiology", "endocrinology"
   - `source_name: TermSource`
   - `source_url: Optional[str]`
   - `source_license: Optional[str]`
   - `icd10_code: Optional[str]`
   - `rxnorm_rxcui: Optional[str]` — RxNorm concept unique identifier
   - `is_code_switch_candidate: bool` — default True
   - `review_status: ReviewStatus`
   - `llm_generated_candidate: bool` — default False
   - `fetched_at: str` — ISO timestamp

5. `Phase2ToFr2EntityTypeMap` dict — maps Phase 2 EntityCategory values to FR2-04 EntityType values:
   - DISEASE_OR_CONDITION → disease
   - DRUG_OR_ACTIVE_INGREDIENT → drug
   - LAB_TEST_OR_BIOMARKER → lab_test
   - PROCEDURE_OR_INTERVENTION → procedure
   - ANATOMY_OR_BODY_PART → anatomy
   - HORMONE_ENZYME_PROTEIN → hormone
   - PATHOGEN_OR_MICROBIOLOGY → pathogen
   - DEVICE_OR_TECHNOLOGY → device
   - ABBREVIATION_OR_ACRONYM → abbreviation
   - GENERAL_MEDICAL_ENGLISH → unknown (no direct FR2-04 match)
   - NUTRITION_OR_SUPPLEMENT → biomarker
   - CHEMICAL_OR_BIOCHEMICAL → drug
   - UNKNOWN → unknown

6. `InventoryConfig(BaseModel)` — for configs/term_inventory.yaml
   - `icd10_backbone_path: str` — default "data/icd10/icd10_dual_language.csv"
   - `output_dir: str` — default "data/terms"
   - `log_dir: str` — default "logs"
   - `rxnorm_drug_list: list[str]` — seed drug names for RxNorm API
   - `abbreviation_list: list[str]` — manual abbreviation list
   - `openfda_device_categories: list[str]` — openFDA device categories
   - `confidence_threshold: float` — default 0.80

Follow Pydantic v2 style (pydantic=2.13). Use Field() for descriptions.
</action>
  <verify>
grep -c "^class EntityType" src/term_inventory/schemas.py && grep -c "^class ReviewStatus" src/term_inventory/schemas.py && grep -c "^class MedicalTermRecord" src/term_inventory/schemas.py && python -c "from src.term_inventory.schemas import EntityType, ReviewStatus, TermSource, MedicalTermRecord, InventoryConfig; print('schemas import OK')"
</verify>
  <done>All Pydantic models defined, importable, and match FR2-04 entity_type values exactly. Phase2ToFr2EntityTypeMap defined.</done>
</task>

<task type="auto">
  <name>Task 2: Create BaseLoader interface and ICD-10 backbone loader</name>
  <files>
    src/term_inventory/loaders/__init__.py
    src/term_inventory/loaders/icd10_backbone.py
  </files>
  <read_first>src/term_inventory/schemas.py</read_first>
  <action>
Create `src/term_inventory/loaders/__init__.py`:
- Import and re-export `BaseLoader`, `Icd10BackboneLoader`
- Add module docstring

Create `src/term_inventory/loaders/icd10_backbone.py`:

```python
from abc import ABC, abstractmethod
import pandas as pd

class BaseLoader(ABC):
    """Abstract base for all term lexicon loaders. All loaders return a DataFrame
    conforming to the MedicalTermRecord schema (flattened to columns)."""
    
    REQUIRED_COLS = [
        "term_original", "term_normalized", "entity_type",
        "source_name", "source_url", "review_status"
    ]
    
    @abstractmethod
    def load(self) -> pd.DataFrame:
        """Load terms from this source. Return DataFrame with REQUIRED_COLS plus optional extra columns."""
        pass
    
    def _validate(self, df: pd.DataFrame) -> None:
        """Validate required columns are present."""
        missing = [c for c in self.REQUIRED_COLS if c not in df.columns]
        if missing:
            raise ValueError(f"{self.__class__.__name__} missing required columns: {missing}")
```

Create `Icd10BackboneLoader(BaseLoader)`:
- `__init__(self, config: InventoryConfig)` — store config
- `load() -> pd.DataFrame`:
  - Read `config.icd10_backbone_path` (default `data/icd10/icd10_dual_language.csv`)
  - Filter rows where `level == "type"` (disease codes, not section/chapter)
  - Map each row: `term_original = label_en`, `term_normalized = label_en.lower().strip()` (normalization happens later in pipeline), `entity_type = disease`, `source_name = icd10`, `source_url = source_url`, `icd10_code = code`, `review_status = verified`, `llm_generated_candidate = False`
  - Add columns: `label_vi = row["label_vi"]`, `chapter_label_en = row["chapter_label_en"]`
  - Log count of loaded disease terms
- If file not found, raise `FileNotFoundError` with helpful message referencing Phase 6a

The ICD-10 loader is the ONLY loader that sets `review_status = verified` (authoritative source). All other loaders default to `needs_review`.
</action>
  <verify>
python -c "from src.term_inventory.loaders import BaseLoader, Icd10BackboneLoader; print('loader imports OK')" && python -c "
from src.term_inventory.loaders import Icd10BackboneLoader
from src.term_inventory.schemas import InventoryConfig
config = InventoryConfig()
loader = Icd10BackboneLoader(config)
# Won't have real file in mock mode, but import+instantiate must work
print('Icd10BackboneLoader instantiated OK')
"
</verify>
  <done>BaseLoader interface defined, Icd10BackboneLoader loads disease backbone with verified status. FileNotFoundError if Phase 6a output missing.</done>
</task>

<task type="auto">
  <name>Task 3: Create RxNorm drug loader</name>
  <files>src/term_inventory/loaders/rxnorm_loader.py</files>
  <action>
Create `src/term_inventory/loaders/rxnorm_loader.py`:

```python
from typing import Optional
import httpx
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_fixed
from src.term_inventory.loaders import BaseLoader
from src.term_inventory.schemas import InventoryConfig, TermSource, ReviewStatus
from src.shared.logging import setup_logger

logger = setup_logger("rxnorm_loader")

class RxNormLoader(BaseLoader):
    """Ingest drug terms from NLM RxNorm REST API.
    
    API is free, no license required. Rate limit: 200ms between requests.
    Base URL: https://rxnav.nlm.nih.gov/REST
    """
    BASE_URL = "https://rxnav.nlm.nih.gov/REST"
    
    def __init__(self, config: InventoryConfig):
        self.config = config
        self.drug_list = config.rxnorm_drug_list  # list of seed drug names from config
        self.delay_ms = 200  # NLM rate limit
```

Implement `load() -> pd.DataFrame`:
- Iterate over `self.drug_list` (e.g., ["metformin", "insulin", "aspirin", "amoxicillin", "ibuprofen", "paracetamol", "atorvastatin", "losartan", "amlodipine", "omeprazole"])
- For each drug name, call `_fetch_drug_concepts(drug_name)`:
  - `GET https://rxnav.nlm.nih.gov/REST/drugs.json?name={drug_name}` with timeout=10
  - Parse `data["drugGroup"]` → `conceptGroup` → `conceptProperties`
  - Yield rows: `term_original = c["name"]`, `rxnorm_rxcui = c.get("rxcui")`, `tty = c.get("tty")`
  - Filter to TTY values that are clinically useful: "SCD" (Semantic Clinical Drug), "IN" (Ingredient), "BN" (Brand Name)
  - Sleep `self.delay_ms / 1000` between requests
- For each valid concept: `entity_type = drug`, `source_name = rxnorm`, `source_url = https://rxnav.nlm.nih.gov/REST/drugs.json?name={drug_name}`, `review_status = verified` (RxNorm is authoritative), `llm_generated_candidate = False`
- Log count of drugs fetched
- Return DataFrame

Use `@retry` decorator: `stop_after_attempt(3)`, `wait_fixed(1)` on HTTP errors. On final failure, log warning and skip that drug (do not crash).

If `self.drug_list` is empty, return empty DataFrame with REQUIRED_COLS.
</action>
  <verify>
python -c "from src.term_inventory.loaders import RxNormLoader; print('RxNormLoader imported OK')" && python -c "
from src.term_inventory.loaders import RxNormLoader
from src.term_inventory.schemas import InventoryConfig
# Test instantiation with empty drug list (no network call)
config = InventoryConfig(rxnorm_drug_list=[])
loader = RxNormLoader(config)
print('RxNormLoader instantiated OK')
"
</verify>
  <done>RxNormLoader fetches drug concepts from NLM API with retry logic. Returns DataFrame with verified drug terms.</done>
</task>

<task type="auto">
  <name>Task 4: Create CLI entry point for term inventory build</name>
  <files>src/term_inventory/cli.py</files>
  <read_first>src/cli.py</read_first>
  <action>
Create `src/term_inventory/cli.py`:

1. `build_arg_parser()` — add subparser "build-inventory" to the argument parser:
   - `--mock` flag: use mock/small seed lists, print "Mock mode: processing 5 seed terms per source"
   - `--full` flag: use full seed lists from config (default)
   - `--output-dir` override: default from config
   - `--limit N`: limit number of terms per source (for smoke tests)

2. `run_build_inventory(args)` — entry point:
   - Load `configs/term_inventory.yaml` via `InventoryConfig`
   - Override with CLI args if provided
   - Create `Icd10BackboneLoader(config)` and `RxNormLoader(config)`
   - Call each loader's `load()` method
   - Concatenate results into a single DataFrame
   - Save to `data/terms/medical_term_inventory.csv`
   - Print summary: "Loaded {N} terms from {M} sources"

3. Add `--mock` seed lists to `InventoryConfig` for smoke tests:
   - `rxnorm_drug_list_mock: ["metformin", "insulin", "aspirin"]`
   - When `--mock` flag is set, use `rxnorm_drug_list_mock` instead of `rxnorm_drug_list`

4. Follow the existing CLI pattern from `src/cli.py` — use `argparse` with subcommands.

Add the subcommand to `src/cli.py` by importing and registering the `build-inventory` subparser.
</action>
  <verify>
python -c "from src.term_inventory.cli import build_arg_parser; p = build_arg_parser(); args = p.parse_args(['build-inventory', '--mock']); print('CLI parsed OK:', args)" && python -c "from src.term_inventory.cli import run_build_inventory; print('run_build_inventory imported OK')"
</verify>
  <done>CLI accepts build-inventory with --mock/--full/--output-dir/--limit flags. --mock mode uses small seed lists.</done>
</task>

<task type="auto">
  <name>Task 5: Create configs/term_inventory.yaml and module __init__</name>
  <files>
    configs/term_inventory.yaml
    src/term_inventory/__init__.py
  </files>
  <action>
Create `configs/term_inventory.yaml`:

```yaml
# Phase 6b: Medical Term Inventory Extended
# FR2 requirements — multi-source term inventory

icd10_backbone_path: "data/icd10/icd10_dual_language.csv"

output_dir: "data/terms"
log_dir: "logs"

# RxNorm drug seed list (used by RxNormLoader)
rxnorm_drug_list:
  - metformin
  - insulin
  - aspirin
  - amoxicillin
  - ibuprofen
  - paracetamol
  - atorvastatin
  - losartan
  - amlodipine
  - omeprazole
  - lisinopril
  - simvastatin
  - warfarin
  - clopidogrel
  - levothyroxine
  - prednisone
  - metformin
  - hba1c
  - cholesterol
  - triglyceride

# Mock mode drug list (small subset for smoke tests)
rxnorm_drug_list_mock:
  - metformin
  - insulin
  - aspirin

# Manual abbreviation list (high-frequency CS medical abbreviations)
abbreviation_list:
  - ECG
  - MRI
  - CT
  - CBC
  - EEG
  - ICU
  - CPR
  - IV
  - IM
  - BP
  - HR
  - WBC
  - RBC
  - CRP
  - HbA1c
  - eGFR
  - PSA
  - HDL
  - LDL
  - COPD
  - UTI
  - GERD
  - HIV
  - AIDS

# openFDA device categories to query
openfda_device_categories:
  - "medical device"
  - "diagnostic imaging device"
  - "cardiac device"

# LLM classification confidence threshold
confidence_threshold: 0.80
```

Create `src/term_inventory/__init__.py`:
```python
"""Phase 6b: Medical Term Inventory Extended.

Builds a comprehensive multi-source medical term inventory from ICD-10 disease
backbone plus supplementary lexicons (drug, lab test, procedure, abbreviation,
hormone, biomarker, device, unit, dosage).
"""
from src.term_inventory.schemas import (
    EntityType,
    ReviewStatus,
    TermSource,
    MedicalTermRecord,
    InventoryConfig,
    Phase2ToFr2EntityTypeMap,
)
from src.term_inventory.loaders import BaseLoader

__all__ = [
    "EntityType",
    "ReviewStatus", 
    "TermSource",
    "MedicalTermRecord",
    "InventoryConfig",
    "Phase2ToFr2EntityTypeMap",
    "BaseLoader",
]
```
</action>
  <verify>
python -c "from src.term_inventory.schemas import InventoryConfig; c = InventoryConfig(); print('Config loaded OK'); import yaml; cfg = yaml.safe_load(open('configs/term_inventory.yaml')); print('YAML parsed OK, keys:', list(cfg.keys()))"
</verify>
  <done>configs/term_inventory.yaml created with all seed lists and paths. Module __init__.py exports all public types.</done>
</task>

</tasks>

<verification>
python -c "
from src.term_inventory.schemas import EntityType, ReviewStatus, TermSource, MedicalTermRecord, InventoryConfig, Phase2ToFr2EntityTypeMap
from src.term_inventory.loaders import BaseLoader, Icd10BackboneLoader, RxNormLoader
print('All imports OK')
# Verify EntityType has all 13 FR2-04 values
fr2_types = {'disease', 'drug', 'lab_test', 'procedure', 'anatomy', 'symptom', 'abbreviation', 'hormone', 'biomarker', 'pathogen', 'device', 'unit', 'dosage', 'unknown'}
actual = {e.value for e in EntityType}
assert actual == fr2_types, f'Mismatch: {actual.symmetric_difference(fr2_types)}'
print('EntityType enum matches FR2-04 exactly')
"
</verification>

<success_criteria>
- `src/term_inventory/schemas.py` defines `EntityType` with all 13 FR2-04 values plus `unknown`
- `src/term_inventory/schemas.py` defines `ReviewStatus` and `TermSource` enums
- `src/term_inventory/schemas.py` defines `MedicalTermRecord` Pydantic model with all provenance columns
- `src/term_inventory/schemas.py` defines `Phase2ToFr2EntityTypeMap` mapping from Phase 2 EntityCategory to FR2-04 EntityType
- `src/term_inventory/loaders/__init__.py` exports `BaseLoader`, `Icd10BackboneLoader`, `RxNormLoader`
- `src/term_inventory/loaders/icd10_backbone.py` loads ICD-10 disease backbone with verified status
- `src/term_inventory/loaders/rxnorm_loader.py` fetches drugs from NLM RxNorm API with retry
- `src/term_inventory/cli.py` exposes `build-inventory` subcommand with --mock/--full flags
- `configs/term_inventory.yaml` contains all seed lists
- All Python files import without error
</success_criteria>

<output>
Create `.planning/phases/06B-medical-term-inventory-extended/06B-01-SUMMARY.md` when done
</output>
