---
phase: "06B"
plan: "03"
type: execute
wave: 2
depends_on: ["06B-01"]
files_modified:
  - "src/term_inventory/loaders/nlm_lab_loader.py"
  - "src/term_inventory/loaders/openfda_device_loader.py"
  - "src/term_inventory/loaders/abbreviation_loader.py"
  - "src/term_inventory/loaders/vimedcss_seed_loader.py"
autonomous: true
requirements:
  - "FR2-02"
  - "FR2-05"
---

<objective>
Build the supplementary lexicon loaders for lab tests, medical devices, abbreviations, and ViMedCSS seed terms. Each loader follows the `BaseLoader` interface and produces a DataFrame with standard columns. All non-authoritative source terms are flagged `llm_generated_candidate=False` with `review_status=needs_review` (authoritative sources like openFDA get `verified`).

Purpose: These loaders populate the supplementary entity types (lab_test, device, abbreviation, anatomy, symptom, hormone, biomarker, pathogen, unit, dosage) that ICD-10 and RxNorm alone cannot cover.
Output: Four new loader modules, each producing DataFrames consumable by the InventoryBuilder.
</objective>

<execution_context>
@$HOME/.cursor/get-shit-done/workflows/execute-plan.md
</execution_context>

<context>
@src/term_inventory/schemas.py
@src/term_inventory/loaders/icd10_backbone.py
@src/term_inventory/loaders/rxnorm_loader.py
@.planning/phases/06B-medical-term-inventory-extended/06B-01-PLAN.md
@.planning/phases/06B-medical-term-inventory-extended/06B-RESEARCH.md

## Loader Architecture

All loaders inherit from `BaseLoader` (defined in Plan 01). Each returns a DataFrame with columns:
- `term_original`, `term_normalized`, `entity_type`, `source_name`, `source_url`, `review_status`, `llm_generated_candidate`

Plus optional extra columns (e.g., `rxnorm_rxcui` for drugs, `openfda_device_number` for devices).

## Source Authority Order (for deduplication conflicts)

Per Plan 02: icd10 > rxnorm > openfda > nlm_lab > abbreviation_list > vimedcss_seed > llm_generated

## openFDA API

openFDA is free, no API key needed.
Base URL: https://api.fda.gov/device/510k.json
Query param: `search=device_name:"{term}"` or `search=product_code:"{code}"`
Rate limit: 1000 requests/day, 125/minute. Use 500ms delay.

## NLM ICD-10-CM Clinical Table Search API

Free, no key required.
URL: https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search?sf=code,name&terms={query}&limit=10

## Abbreviation List Strategy

The abbreviation list comes from configs/term_inventory.yaml (`abbreviation_list`).
Each abbreviation maps to: entity_type=abbreviation, source_name=abbreviation_list, review_status=needs_review.
Store both the abbreviation AND its expansion (e.g., ECG → electrocardiogram) as separate rows.
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create NLM lab test and procedure loader</name>
  <files>src/term_inventory/loaders/nlm_lab_loader.py</files>
  <action>
Create `src/term_inventory/loaders/nlm_lab_loader.py`:

```python
from src.term_inventory.loaders import BaseLoader
from src.term_inventory.schemas import InventoryConfig, EntityType, ReviewStatus, TermSource
from src.shared.logging import setup_logger

logger = setup_logger("nlm_lab_loader")

class NlmLabLoader(BaseLoader):
    """Ingest lab test and procedure terms from NLM ICD-10-CM Clinical Table Search API.
    
    API is free, no license required. Used for lab_test and procedure entity types.
    Base URL: https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search
    """
    BASE_URL = "https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search"
```

Implement `__init__` and `load()`:
- Accept `InventoryConfig` in `__init__`
- In `load()`:
  - Define seed search terms for lab tests: ["complete blood count", "glucose", "cholesterol", "hemoglobin", "creatinine", "thyroid", "liver function", "kidney function", "HbA1c", "bilirubin", "albumin", "protein", "electrolyte", "uric acid", "triglyceride", "HDL", "LDL"]
  - Define seed search terms for procedures: ["x-ray", "ultrasound", "MRI scan", "CT scan", "endoscopy", "biopsy", "surgery", "dialysis", "chemotherapy", "radiotherapy", "angiography", "echocardiography", "colonoscopy"]
  - For each term, call `_search_icd10cm(query)`:
    - `GET {BASE_URL}?sf=code,name&terms={query}&limit=10`
    - Parse response: `data[0]` = match count, `data[3]` = list of [code, name] pairs
    - Yield rows for each match
  - Map results: if term contains keywords ["test", "level", "count", "panel"], entity_type=lab_test; otherwise entity_type=procedure
  - Set `source_name = nlm_lab`, `source_url = NLM API URL`, `review_status = needs_review`, `llm_generated_candidate = False`
  - Sleep 200ms between requests
- Use `@retry` with `stop_after_attempt(3)`, `wait_fixed(1)` on HTTP errors
- Log count of lab_test and procedure terms loaded

If seed list is empty, return empty DataFrame with REQUIRED_COLS.
</action>
  <verify>
python -c "from src.term_inventory.loaders import NlmLabLoader; from src.term_inventory.schemas import InventoryConfig; config = InventoryConfig(); loader = NlmLabLoader(config); print('NlmLabLoader instantiated OK')"
</verify>
  <done>NlmLabLoader fetches lab test and procedure terms from NLM ICD-10-CM API. Returns DataFrame with lab_test and procedure entity types.</done>
</task>

<task type="auto">
  <name>Task 2: Create openFDA medical device loader</name>
  <files>src/term_inventory/loaders/openfda_device_loader.py</files>
  <action>
Create `src/term_inventory/loaders/openfda_device_loader.py`:

```python
from src.term_inventory.loaders import BaseLoader
from src.term_inventory.schemas import InventoryConfig, EntityType, ReviewStatus
from src.shared.logging import setup_logger

logger = setup_logger("openfda_device_loader")

class OpenFdaDeviceLoader(BaseLoader):
    """Ingest medical device terms from openFDA 510(k) device database.
    
    API is free, no API key required.
    Base URL: https://api.fda.gov/device/510k.json
    Rate limit: 1000 req/day, 125/min. Use 500ms delay.
    """
    BASE_URL = "https://api.fda.gov/device/510k.json"
```

Implement `load()`:
- Use seed device categories from `config.openfda_device_categories` (e.g., ["cardiac device", "diagnostic imaging device", "medical device"])
- For each category, call `_search_devices(query)`:
  - `GET {BASE_URL}?search=device_name:"{query}"&limit=20`
  - Parse response JSON: `results` array contains 510(k) records
  - Extract: `device_name` from each record
  - Deduplicate by `device_name` (case-insensitive)
- Map: entity_type = device, source_name = openfda
- `review_status = verified` (openFDA is authoritative government database)
- `llm_generated_candidate = False`
- Set `source_url = https://api.fda.gov/device/510k.json?search=device_name:"{query}"`
- Sleep 500ms between requests
- Use `@retry` with `stop_after_attempt(3)`, `wait_fixed(2)` on HTTP errors

Log count of unique device terms loaded. If results empty, return empty DataFrame with REQUIRED_COLS.
</action>
  <verify>
python -c "from src.term_inventory.loaders import OpenFdaDeviceLoader; from src.term_inventory.schemas import InventoryConfig; config = InventoryConfig(); loader = OpenFdaDeviceLoader(config); print('OpenFdaDeviceLoader instantiated OK')"
</verify>
  <done>OpenFdaDeviceLoader fetches medical device terms from openFDA API. Sets review_status=verified. Returns DataFrame with device entity type.</done>
</task>

<task type="auto">
  <name>Task 3: Create abbreviation and ViMedCSS seed loaders</name>
  <files>
    src/term_inventory/loaders/abbreviation_loader.py
    src/term_inventory/loaders/vimedcss_seed_loader.py
  </files>
  <action>
Create `src/term_inventory/loaders/abbreviation_loader.py`:

```python
from src.term_inventory.loaders import BaseLoader
from src.term_inventory.schemas import InventoryConfig, EntityType, ReviewStatus, TermSource
from src.shared.logging import setup_logger

logger = setup_logger("abbreviation_loader")

# Medical abbreviation → expansion mapping
# Sourced from configs/term_inventory.yaml abbreviation_list + manual additions
ABBREVIATION_EXPANSION_MAP = {
    "ECG": "electrocardiogram",
    "EEG": "electroencephalogram",
    "MRI": "magnetic resonance imaging",
    "CT": "computed tomography",
    "CBC": "complete blood count",
    "ICU": "intensive care unit",
    "ER": "emergency room",
    "IV": "intravenous",
    "IM": "intramuscular",
    "BP": "blood pressure",
    "HR": "heart rate",
    "WBC": "white blood cell",
    "RBC": "red blood cell",
    "CRP": "c-reactive protein",
    "HbA1c": "hemoglobin A1c",
    "eGFR": "estimated glomerular filtration rate",
    "PSA": "prostate specific antigen",
    "HDL": "high density lipoprotein",
    "LDL": "low density lipoprotein",
    "COPD": "chronic obstructive pulmonary disease",
    "UTI": "urinary tract infection",
    "GERD": "gastroesophageal reflux disease",
    "HIV": "human immunodeficiency virus",
    "AIDS": "acquired immunodeficiency syndrome",
    "CPR": "cardiopulmonary resuscitation",
    "CABG": "coronary artery bypass grafting",
    "PCI": "percutaneous coronary intervention",
    "TPN": "total parenteral nutrition",
    "NG": "nasogastric",
    "PO": "per os (by mouth)",
    "QD": "once daily",
    "BID": "twice daily",
    "TID": "three times daily",
    "QID": "four times daily",
    "PRN": "as needed",
    "STAT": "immediately",
    "NPO": "nothing by mouth",
    "O2": "oxygen",
    "O2sat": "oxygen saturation",
    "BT": "body temperature",
    "RR": "respiratory rate",
    "TLC": "total lung capacity",
    "FVC": "forced vital capacity",
    "FEV1": "forced expiratory volume in 1 second",
    "MCH": "mean corpuscular hemoglobin",
    "MCHC": "mean corpuscular hemoglobin concentration",
    "MCV": "mean corpuscular volume",
    "MPV": "mean platelet volume",
    "PT": "prothrombin time",
    "PTT": "partial thromboplastin time",
    "INR": "international normalized ratio",
    "BNP": "brain natriuretic peptide",
    "NT-proBNP": "n-terminal pro brain natriuretic peptide",
    "TSH": "thyroid stimulating hormone",
    "T3": "triiodothyronine",
    "T4": "thyroxine",
    "ALT": "alanine aminotransferase",
    "AST": "aspartate aminotransferase",
    "ALP": "alkaline phosphatase",
    "GGT": "gamma glutamyl transferase",
    "BUN": "blood urea nitrogen",
    "Na": "sodium",
    "K": "potassium",
    "Cl": "chloride",
    "Ca": "calcium",
    "Mg": "magnesium",
    "Ph": "phosphate",
    "Hb": "hemoglobin",
    "Hct": "hematocrit",
    "PLT": "platelet",
    "ESR": "erythrocyte sedimentation rate",
    "LDH": "lactate dehydrogenase",
    "CPK": "creatine phosphokinase",
    "GFR": "glomerular filtration rate",
    "HBA1C": "hemoglobin A1c",
    "SIRS": "systemic inflammatory response syndrome",
    "MODS": "multiple organ dysfunction syndrome",
    "ARDS": "acute respiratory distress syndrome",
    "DVT": "deep vein thrombosis",
    "PE": "pulmonary embolism",
    "MI": "myocardial infarction",
    "CVA": "cerebrovascular accident",
    "TIA": "transient ischemic attack",
    "CHF": "congestive heart failure",
    "SOB": "shortness of breath",
    "HA": "headache",
    "LOC": "loss of consciousness",
    "RX": "prescription",
    "TX": "treatment",
    "DX": "diagnosis",
    "SX": "symptoms",
    "FX": "fracture",
    "HX": "history",
    "Sx": "surgery",
    "D/c": "discharge",
    "Adeno": "adenocarcinoma",
    "CXR": "chest x-ray",
    "KUB": "kidney ureter bladder x-ray",
    "ABG": "arterial blood gas",
    "LP": "lumbar puncture",
    "CSF": "cerebrospinal fluid",
    "GU": "genitourinary",
    "GI": "gastrointestinal",
    "CV": "cardiovascular",
    "MSK": "musculoskeletal",
    "Derm": "dermatology",
    "ENT": "ear nose throat",
    "OB": "obstetrics",
    "GYN": "gynecology",
    "Peds": "pediatrics",
    "Geris": "geriatrics",
    "Psych": "psychiatry",
    "ID": "infectious disease",
    "Onc": "oncology",
    "Neph": "nephrology",
    "Pulm": "pulmonology",
    "Rheum": "rheumatology",
    "Endo": "endocrinology",
    "Neuro": "neurology",
}
```

Implement `AbbreviationLoader(BaseLoader)`:
- `__init__(self, config: InventoryConfig)` — load `abbreviation_list` from config
- `load() -> pd.DataFrame`:
  - For each abbreviation in config's `abbreviation_list`, create two rows:
    - Row 1: `term_original = abbrev`, `entity_type = abbreviation`, `source_name = abbreviation_list`, `review_status = needs_review`, `llm_generated_candidate = False`
    - Row 2 (if expansion exists): `term_original = expansion`, `entity_type = abbreviation`, `source_name = abbreviation_list`, `review_status = needs_review`, `llm_generated_candidate = False`
  - If abbreviation not in ABBREVIATION_EXPANSION_MAP, still add the abbreviation row (no expansion row)
  - Set `source_url = "configs/term_inventory.yaml#abbreviation_list"`
  - Log count of abbreviations loaded

---

Create `src/term_inventory/loaders/vimedcss_seed_loader.py`:

```python
from src.term_inventory.loaders import BaseLoader
from src.term_inventory.schemas import InventoryConfig, EntityType, ReviewStatus, TermSource
from src.shared.logging import setup_logger

logger = setup_logger("vimedcss_seed_loader")
```

Implement `VimedcssSeedLoader(BaseLoader)`:
- `__init__(self, config: InventoryConfig)`
- `load() -> pd.DataFrame`:
  - Load Phase 1 output: `outputs/term_coverage/cs_terms_inventory.csv`
  - If file doesn't exist, raise `FileNotFoundError` with message "Phase 1 output not found. Run term extraction first."
  - For each row, map: `term_original = normalized_term` from Phase 1, `entity_type = unknown` (will be classified by LLM in Plan 04), `source_name = vimedcss_seed`, `review_status = needs_review`, `llm_generated_candidate = False`
  - Log count of ViMedCSS seed terms loaded
  - Return DataFrame with all standard columns

The ViMedCSS seed loader provides the bridge between Phase 1 (ViMedCSS CS terms) and the medical term inventory. These terms will get entity_type and medical_domain assigned in Plan 04 via LLM classification.
</action>
  <verify>
python -c "
from src.term_inventory.loaders import AbbreviationLoader, VimedcssSeedLoader
from src.term_inventory.schemas import InventoryConfig
config = InventoryConfig(abbreviation_list=['ECG', 'MRI', 'CT', 'CBC'])
abbr_loader = AbbreviationLoader(config)
vimedcss_loader = VimedcssSeedLoader(config)
print('Loaders instantiated OK')
# Test abbreviation loader produces rows
abbr_df = abbr_loader.load()
assert len(abbr_df) >= 6, f'Expected >=6 rows (3 abbrevs x 2 rows each), got {len(abbr_df)}'
assert 'ECG' in abbr_df['term_original'].values
assert 'electrocardiogram' in abbr_df['term_original'].values
print(f'AbbreviationLoader produced {len(abbr_df)} rows')
"
</verify>
  <done>AbbreviationLoader creates two rows per abbreviation (abbrev + expansion). VimedcssSeedLoader loads Phase 1 CS terms with unknown entity_type.</done>
</task>

</tasks>

<verification>
python -c "
from src.term_inventory.loaders import (
    NlmLabLoader,
    OpenFdaDeviceLoader,
    AbbreviationLoader,
    VimedcssSeedLoader,
)
from src.term_inventory.schemas import InventoryConfig

config = InventoryConfig(
    abbreviation_list=['ECG', 'MRI', 'CT'],
    openfda_device_categories=['cardiac device']
)

loaders = [
    ('NlmLabLoader', NlmLabLoader(config)),
    ('OpenFdaDeviceLoader', OpenFdaDeviceLoader(config)),
    ('AbbreviationLoader', AbbreviationLoader(config)),
    ('VimedcssSeedLoader', VimedcssSeedLoader(config)),
]

for name, loader in loaders:
    cols = loader.REQUIRED_COLS
    assert 'term_original' in cols
    assert 'entity_type' in cols
    assert 'source_name' in cols
    assert 'review_status' in cols
    print(f'{name}: REQUIRED_COLS OK')
print('All supplementary loaders validated')
"
</verification>

<success_criteria>
- `NlmLabLoader` fetches lab_test and procedure terms from NLM ICD-10-CM API
- `OpenFdaDeviceLoader` fetches device terms from openFDA 510(k) API with review_status=verified
- `AbbreviationLoader` creates abbreviation and expansion rows from abbreviation_list config
- `VimedcssSeedLoader` loads Phase 1 CS terms as vimedcss_seed source
- All loaders inherit from BaseLoader and return DataFrames with REQUIRED_COLS
- All loaders handle empty/missing data gracefully (empty DataFrame, no crash)
- All loaders log counts of terms loaded
- Module-level imports work without error
</success_criteria>

<output>
Create `.planning/phases/06B-medical-term-inventory-extended/06B-03-SUMMARY.md` when done
</output>
