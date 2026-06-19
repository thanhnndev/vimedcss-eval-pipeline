# ViMedCSS Term Coverage & ASR Code-Switching Evaluation Pipeline

## What This Is

ViMedCSS Term Coverage & ASR Code-Switching Evaluation Pipeline is a research tool designed to analyze medical term coverage and evaluate ASR baseline performance on English/Vietnamese code-switching dataset `tensorxt/ViMedCSS`. It is used by researchers to identify ASR failures on code-switching terms and plan the dataset design for the subsequent VietMedVoice project.

## Core Value

Accurate, traceable medical term coverage analysis and ASR error taxonomy for English/Vietnamese code-switching data to guide future dataset construction.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

- ✓ Hugging Face metadata acquisition (download CSVs and record file manifest) — v1.0 Phase 1
- ✓ Metadata schema mapping and local data quality auditing (duplicate IDs, missing field detection, split/topic stats) — v1.0 Phase 1

### Active

<!-- v1.1 milestone scope -->

- [ ] FR1: ICD-10 dual-language ingestion (EN/VI, chapter/section/type/disease hierarchy)
- [ ] FR2: Medical term taxonomy and extended inventory (disease, drug, lab test, procedure, abbreviation, hormone, biomarker, device, unit, dosage)
- [ ] FR3: ViMedCSS ICD-10/non-ICD coverage audit
- [ ] FR4: VietMed feasibility audit (license, access, overlap analysis)
- [ ] FR5: LLM doctor-patient conversation generation (JSONL, ICD/domain/term-controlled, safety flags)
- [ ] FR6: LLM model cost analysis (cost per conversation, JSON validity rate)
- [ ] FR7: TTS model research (Vietnamese + English term readability, local/API comparison)
- [ ] FR8: Voice pool research and metadata (gender/age/region, license-tracked)
- [ ] FR9: Synthetic TTS generation pilot with round-trip ASR check
- [ ] FR10: ASR evaluation by domain/entity (WER/CER/CS-WER/Term Recall)
- [ ] FR11: TV3 ASR & diarization harness (PhoWhisper zero-shot + fine-tune, pyannote 3.1 + WhisperX, DER/JER)

### Out of Scope

<!-- Explicit boundaries. Includes reasoning to prevent re-adding. -->

- [ASR model fine-tuning in v1.0] — v1.0 focused on baseline evaluation; v1.1 Phase 3 (TV3) includes fine-tune experiments
- [GUI / Browser Interface] — Command-line interface with persistent file outputs is sufficient
- [Full Medical Lexicon Redistribution] — Only include pilot reference metadata and source registry due to license/access constraints
- [Real medical diagnosis or advice] — Phase 2 does not provide medical advice to end users
- [Voice cloning from real people] — Requires consent and policy not covered in this phase
- [Public raw audio from YouTube/TikTok/VietMed/viVoice] — Only if license explicitly permits

## Context

- **Dataset**: `tensorxt/ViMedCSS` Hugging Face dataset (15,818 rows, ~32.64 hours).
- **Previous milestone**: v1.0 shipped CS term extraction, LLM classification, external reference matching, ASR baseline evaluation, and Vietnamese report generation — all via `--mock` smoke test mode. Real audio evaluation blocked on audio access and `OPENAI_API_KEY`.
- **PRD reference**: `docs/prd/PRD_VietMedVoice_Phase2_Enhancement_v1.1.md` — Phase 2 scope covers 11 functional requirements (FR1–FR11) across 8 weeks.
- **Key scope note**: ICD-10 is disease backbone only; must supplement with drug/lab/procedure lexicon lists for non-disease terms.

## Constraints

- **Data Integrity**: No fabricated data; separate paper-reported, hf-reported, local-verified, and LLM-inferred metrics.
- **LLM Safety**: Do not treat LLM classification as absolute ground truth; include confidence and review flags.
- **Language**: Final report must be in Vietnamese.
- **Testing**: Every pipeline must support a subset/smoke test mode.
- **Synthetic Data Policy**: Synthetic speech only for train/augmentation; final ASR test must be real-only.
- **Metadata Honesty**: No guessing gender/age/region; use `unknown` or `estimated_*` with confidence when not provided.

## Key Decisions

|| Decision | Rationale | Outcome |
||----------|-----------|---------|
|| Case-insensitive column mapping | Handles case differences like `Topic` vs `topic` across splits | ✓ Good |
|| ICD-10 as disease backbone only | ICD-10 does not cover drugs, lab tests, procedures, units, dosages — supplement required | ✓ Good |
|| ICD-10 EN/VI join by code, not label | Labels differ across languages; code is the stable join key | ✓ Good |
|| Synthetic data only for train/augmentation | Prevents overfitting to synthetic style on real test evaluation | ✓ Good |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state (users, feedback, metrics)

---
*Last updated: 2026-06-19 after v1.1 milestone initialization*
