# ViMedCSS Term Coverage & ASR Code-Switching Evaluation Pipeline

## What This Is

ViMedCSS Term Coverage & ASR Code-Switching Evaluation Pipeline is a research tool designed to analyze medical term coverage and evaluate ASR baseline performance on English/Vietnamese code-switching dataset `tensorxt/ViMedCSS`. It is used by researchers to identify ASR failures on code-switching terms and plan the dataset design for the subsequent VietMedVoice project.

## Core Value

Accurate, traceable medical term coverage analysis and ASR error taxonomy for English/Vietnamese code-switching data to guide future dataset construction.

## Requirements

### Validated

- ✓ Hugging Face metadata acquisition (download CSVs and record file manifest) — existing
- ✓ Metadata schema mapping and local data quality auditing (duplicate IDs, missing field detection, split/topic stats) — existing

### Active

- [ ] CS term extraction and normalization (parse lists, keep raw vs normalized forms)
- [ ] Term taxonomy and LLM classification (classify terms into entity categories and medical domains)
- [ ] External research inventory & coverage comparison (ICD-10, ATC, Meddict references)
- [ ] Audio download/verification and ASR manifest preparation
- [ ] ASR baseline evaluation on test/hard splits (WER, CER, CS term metrics)
- [ ] Vietnamese report generation (summarizing term coverage, ASR weaknesses, dataset gaps)

### Out of Scope

- [ASR model fine-tuning] — Out of scope for v1; focus is on baseline evaluation
- [GUI / Browser Interface] — Command-line interface with persistent file outputs is sufficient
- [Full Medical Lexicon Redistribution] — Only include pilot reference metadata and source registry due to license/access constraints

## Context

- **Dataset**: `tensorxt/ViMedCSS` Hugging Face dataset (15,818 rows, ~32.64 hours).
- **Current State**: Codebase already has download and schema auditing modules implemented in Python with a CLI wrapper and pytest suite.
- **Data Quality**: 4 duplicate segment_ids detected chao-split; test set contains `Topic` instead of `topic`.

## Constraints

- **Data Integrity**: No fabricated data; separate paper-reported, hf-reported, local-verified, and LLM-inferred metrics.
- **LLM Safety**: Do not treat LLM classification as absolute ground truth; include confidence and review flags.
- **Language**: Final report must be in Vietnamese.
- **Testing**: Every pipeline must support a subset/smoke test mode.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Case-insensitive column mapping | Handles case differences like `Topic` vs `topic` across splits | ✓ Good |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-06-16 after initialization*
