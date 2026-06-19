# Feature Research: VietMedVoice Phase 2 Enhancement

**Domain:** Vietnamese Medical Code-Switching ASR Evaluation Pipeline
**Researched:** 2026-06-19
**Confidence:** MEDIUM-HIGH (verified against official sources, research papers, and existing datasets)

## Feature Landscape

### Table Stakes (Expected for Medical ASR Research Pipeline)

These are non-negotiable features for a research-grade Vietnamese medical code-switching pipeline. Missing these = pipeline feels incomplete or unreliable.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| ICD-10 dual-language disease inventory | Disease backbone for term taxonomy and coverage audit | MEDIUM | VN ICD-10 (QĐ 4469/QĐ-BYT) has 15,026 codes; join EN/VI by code, not label |
| Medical term taxonomy (entity types) | Covers diseases, drugs, labs, procedures, abbreviations, biomarkers | MEDIUM | VN Core FHIR provides SNOMED CT (77K), LOINC (66K), medical devices (956) |
| ViMedCSS coverage audit | Quantifies what ViMedCSS covers vs. missing | LOW | Extract CS terms → match against inventory → compute coverage rates |
| JSONL conversation schema with safety flags | Structured synthetic data with validation traces | LOW | Required for TTS input, must include speaker roles and safety_flags |
| Round-trip ASR pronunciation check | Validates TTS correctly pronounces medical terms | MEDIUM | Medical terms (e.g., "HbA1c", "metformin") need explicit pronunciation validation |
| ASR metrics by domain/entity | Identifies which medical areas ASR fails on | LOW | WER/CER/CS-WER/Term Recall grouped by disease, drug, lab, procedure |
| PhoWhisper zero-shot baseline | Establishes baseline before fine-tuning | LOW | PhoWhisper-small (244M params) fine-tuned on 844h Vietnamese; use as E0 |

### Differentiators (Competitive Advantage)

These features set the pipeline apart from generic TTS/ASR pipelines. Not required but highly valuable for medical code-switching research.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| ICD-10 EN/VI ingestion via FHIR | Official, authoritative, 15K+ disease codes with dual-language labels | MEDIUM | VN Core FHIR CodeSystem `vn-icd10-cs` supports `designation[en]`; use code as stable join key |
| Medical entity classification (9 types) | Distinguishes disease vs. drug vs. lab vs. procedure vs. abbreviation vs. hormone vs. biomarker vs. device vs. unit | MEDIUM | VN Core FHIR provides ontology coverage: ICD-10, SNOMED CT VN subset, LOINC VN subset, VNMedicalDeviceNomenclature |
| LLM conversation generation with ICD grounding | Generates doctor-patient dialogues anchored to specific ICD codes and medical terms | HIGH | Dual-agent (Doctor + Patient) architecture; validate against ontology; requires strict JSON schema + safety flags |
| VieNeu-TTS code-switching support | Local Vietnamese TTS that handles EN medical terms within VI sentences | MEDIUM | VieNeu-TTS v2/v3 Turbo supports code-switching via sea-g2p phonemizer; 10,000+ hours training data |
| Voice pool with dialect metadata | Diverse synthetic voices covering North/Central/South regions for natural prosody | MEDIUM | VieNeu-TTS-500h-Dialects (500h, North/Central/South labels); ViMD (63 provincial dialects); PhoAudiobook (941h, 735 speakers) |
| PhoWhisper fine-tuning with ablation | Validates whether synthetic augmentation actually helps on real medical audio | HIGH | Compare E0 (zero-shot), E1 (synthetic only), E2 (VietMed real only), E3 (synthetic + VietMed); validate on real test set only |
| pyannote 3.1 + WhisperX speaker attribution | Word-level speaker labels for doctor-patient conversation analysis | MEDIUM | Exclusive diarization → assign words to speakers by temporal overlap → RTTM output |
| DER/JER diarization metrics | Measures speaker counting and attribution accuracy | MEDIUM | Requires reference RTTM; if unavailable, report qualitative/proxy only |
| Medical-specific ASR metrics | MWER/MCER focused on terminology accuracy | LOW | Extends WER/CER to medical word/character error rate; extract terms from conversation JSON |
| VietMed feasibility audit | Determines if VietMed (16h labeled, 1000h unlabeled) can augment training | MEDIUM | Must verify license and access; overlap analysis with ViMedCSS and ICD-10 inventory |

### Anti-Features (Commonly Requested, Problematic)

Features that seem good but create problems for this research pipeline.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|----------------|-------------|
| LLM output as ground truth | LLMs classify medical terms accurately | LLM can misclassify; hallucinate rare terms; no accountability | Use LLM as candidate label + human review gate; flag low-confidence items |
| All synthetic data for final test set | Maximizes data volume | ASR overfits to synthetic style; invalidates evaluation | Synthetic only for train/augmentation; real-only for final test |
| Claim full ICD-10 coverage | Makes dataset sound comprehensive | Only 15K ICD-10 disease codes; doesn't cover drugs/labs/procedures | Report verified coverage percentages with evidence |
| Guess speaker gender/age/region | Fills missing metadata | Inference is unreliable; violates data integrity | Use `unknown` or `estimated_*` with confidence level |
| Voice cloning from real doctors/patients | Creates realistic voices | Requires explicit consent; policy not defined in this phase | Use synthetic voices from TTS model; clone only with proper consent |
| Public raw audio from YouTube/TikTok | Expands data cheaply | License unclear; privacy/ethics violations | Only use licensed sources; metadata-only for unauthorized sources |

## Feature Dependencies

```
[ICD-10 Dual-Language Ingestion]
    └──requires──> [Medical Term Taxonomy]
                           └──requires──> [ViMedCSS Coverage Audit]

[Medical Term Taxonomy]
    └──required-for──> [LLM Conversation Generation]
                                   └──required-for──> [Synthetic TTS Generation]

[Voice Pool Research]
    └──required-for──> [Synthetic TTS Generation]

[Synthetic TTS Generation]
    └──required-for──> [Round-trip ASR Check]
                                 └──required-for──> [PhoWhisper Fine-tuning]

[PhoWhisper Fine-tuning]
    └──validates-with──> [ASR Evaluation by Domain/Entity]

[pyannote 3.1 Diarization] ──merges-with──> [WhisperX Word Timestamps]
                                                       └──produces──> [Speaker-Attributed Transcript]
```

### Dependency Notes

- **ICD-10 ingestion requires code-based EN/VI join:** Labels differ across languages; code is the stable join key. Do not attempt label-based matching.
- **Medical term taxonomy requires ontology mapping:** ICD-10 alone doesn't cover drugs/labs/procedures. Supplement with SNOMED CT VN subset (77K codes) and LOINC VN subset (66K codes).
- **LLM conversation generation requires ICD grounding:** Each conversation must trace to ICD code + required terms. This enables controlled term coverage and quality validation.
- **Synthetic TTS requires voice pool:** Diverse voices prevent monotonous synthetic audio. Use VieNeu-TTS-500h-Dialects or ViMD for dialect coverage.
- **Round-trip ASR check is mandatory before fine-tuning:** Medical terms (HbA1c, metformin, corticosteroid) must be validated for correct TTS pronunciation. Mispronunciations propagate to ASR training.
- **Fine-tuning ablation requires real test set:** E0/E1/E2/E3 must be evaluated on the same real test set (VietMed-test or approved real audio). Synthetic-only test invalidates improvement claims.

## MVP Definition

### Launch With (v1.1 Phase 2 Core)

Minimum viable features to validate the pipeline concept and generate actionable insights.

- [ ] **ICD-10 dual-language ingestion** — Generate `icd10_dual_language.csv/jsonl` with code, label_en, label_vi, chapter, section, type. Join EN/VI by code only.
- [ ] **Medical term taxonomy v0** — Classify terms by entity type (disease/drug/lab/procedure/abbreviation). Supplement ICD-10 with non-disease medical terms from VN Core FHIR.
- [ ] **ViMedCSS coverage audit** — Quantify ViMedCSS coverage of ICD-10 and non-ICD medical terms. Report missing terms and hard cases.
- [ ] **LLM conversation generation pilot** — Generate 100-500 doctor-patient conversations in JSONL with ICD grounding, speaker roles, safety flags. Validate JSON schema + medical term inclusion.
- [ ] **TTS model comparison** — Benchmark VieNeu-TTS v2 Turbo for code-switching readability. Test English medical term pronunciation (MRI, CT, HbA1c, metformin).
- [ ] **Voice pool inventory** — Catalog available voices from VieNeu-TTS-500h-Dialects, ViMD, PhoAudiobook. Include dialect labels and metadata confidence.
- [ ] **PhoWhisper zero-shot baseline** — Run PhoWhisper-small on VietMed-test or approved real audio. Compute WER/CER/CS-WER.
- [ ] **ASR metrics by domain** — Group WER/CER/CS-WER by medical domain (cardiology, endocrinology, etc.) and entity type (disease, drug, lab).

### Add After Validation (v1.1 Phase 2 Extension)

Features to add once core pipeline is working and resources are confirmed.

- [ ] **Synthetic TTS pilot with round-trip ASR** — Generate 500-1000 synthetic audio samples. Run round-trip ASR check. Flag failed pronunciations.
- [ ] **VietMed feasibility audit** — If license permits, analyze VietMed overlap with ViMedCSS and ICD-10. Report access constraints.
- [ ] **Voice profile cards** — Create `voice_profile_cards.jsonl` with gender/age/region status (provided/estimated/unknown), license, and allowed_use.
- [ ] **PhoWhisper fine-tuning ablation (E0/E1/E2/E3)** — Fine-tune PhoWhisper-small with synthetic only (E1), VietMed real only (E2), and synthetic + VietMed (E3). Compare on same real test set.
- [ ] **pyannote 3.1 diarization baseline** — Run diarization on doctor-patient audio. Output RTTM and speaker turn statistics.

### Future Consideration (v2+)

Features to defer until Phase 2 validates and funding/resources are secured.

- [ ] **Full LLM conversation dataset (10K+)** — Scale conversation generation to cover all ICD-10 chapters and medical entity types.
- [ ] **Human pronunciation review queue** — Clinician review of medical term pronunciations before TTS synthesis.
- [ ] **pyannote + WhisperX integration** — Word-level speaker attribution for doctor-patient transcript analysis.
- [ ] **DER/JER computation** — If reference RTTM available, compute speaker diarization error rates.
- [ ] **Public dataset release** — Package metadata, reports, and approved data with license documentation.
- [ ] **Production-scale PhoWhisper fine-tuning** — Multi-GPU training with hyperparameter optimization.

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| ICD-10 dual-language ingestion | HIGH | MEDIUM | P1 |
| Medical term taxonomy | HIGH | MEDIUM | P1 |
| ViMedCSS coverage audit | HIGH | LOW | P1 |
| LLM conversation generation pilot | HIGH | HIGH | P1 |
| TTS model comparison | HIGH | MEDIUM | P1 |
| PhoWhisper zero-shot baseline | HIGH | LOW | P1 |
| ASR metrics by domain | HIGH | LOW | P1 |
| Voice pool inventory | MEDIUM | MEDIUM | P2 |
| Synthetic TTS pilot | MEDIUM | HIGH | P2 |
| VietMed feasibility audit | MEDIUM | MEDIUM | P2 |
| PhoWhisper fine-tuning ablation | HIGH | HIGH | P2 |
| pyannote 3.1 diarization | MEDIUM | MEDIUM | P2 |
| Voice profile cards | LOW | LOW | P3 |
| pyannote + WhisperX integration | MEDIUM | MEDIUM | P3 |
| DER/JER computation | MEDIUM | LOW | P3 |
| Full LLM dataset (10K+) | MEDIUM | VERY HIGH | P3 |
| Public dataset release | MEDIUM | HIGH | P3 |

**Priority key:**
- P1: Must have for Phase 2 validation
- P2: Should have if resources permit
- P3: Nice to have, defer to v2

## Competitor Feature Analysis

| Feature | ViMedCSS (baseline) | VietMed | Our Approach |
|---------|---------------------|---------|--------------|
| Dataset size | 34.6 hours, 15,818 rows | 16h labeled, 1000h unlabeled | Build on ViMedCSS + VietMed for real audio; generate synthetic for term coverage |
| Code-switching support | Yes (EN medical terms in VI) | Limited (monolingual VI) | Target EN medical term recognition in VI context as primary differentiator |
| ICD-10 coverage | Implicit via topics | All ICD-10 chapters covered | Explicit ICD-10 grounding; map CS terms to ICD codes |
| Medical entity taxonomy | CS terms only | Broad medical terms | 9 entity types: disease, drug, lab, procedure, abbreviation, hormone, biomarker, device, unit |
| Synthetic data | None | None | LLM-generated conversations + TTS for term coverage expansion |
| ASR fine-tuning | Baseline only | Pre-trained models available | Ablation study: synthetic vs. real vs. combined |
| Speaker diversity | Video source diversity | 8 recording conditions | Voice pool with dialect (North/Central/South) and gender metadata |
| Evaluation metrics | WER/CER | WER/CER | Extended: CS-WER, Term Recall, MWER/MCER, DER/JER |

## Sources

### Official/Authoritative Sources

1. **VN Core FHIR Implementation Guide v0.6.0** (https://fhir.hl7.org.vn/)
   - `vn-icd10-cs`: 15,026 ICD-10 VN codes (QĐ 4469/QĐ-BYT)
   - `vn-snomed-subset-cs`: 77,393 SNOMED CT VN codes
   - `vn-loinc-cs`: 66,077 LOINC VN codes
   - `VNMedicalDeviceNomenclatureCS`: 956 medical device terms
   - Dual-language via `display` (VI) + `designation[en]` (EN)

2. **VieNeu-TTS** (https://github.com/pnnbao97/vieneu-tts)
   - sea-g2p phonemizer for EN/VI code-switching
   - 10,000+ hours bilingual training data
   - Voice cloning with 3-5 seconds reference audio

3. **PhoWhisper** (https://github.com/VinAIResearch/PhoWhisper)
   - PhoWhisper-small: 244M params, fine-tuned on 844h Vietnamese
   - State-of-the-art Vietnamese ASR

### Research Papers

1. **ViMedCSS** (LREC 2026): Vietnamese Medical Code-Switching Speech Dataset
   - 34.6 hours, 16,576 utterances
   - LoRA/Attention Guide fine-tuning outperforms decoder-only methods
   - CS-WER halved with parameter-efficient adaptation on PhoWhisper-small

2. **VietMed** (LREC-COLING 2024): 16h labeled + 1000h unlabeled medical speech
   - Covers all ICD-10 disease groups
   - 8 recording conditions, multiple speaker roles

3. **MedSynth** (2025): Synthetic Medical Dialogue-Note Pairs
   - Dual-agent (Doctor + Patient) architecture
   - Judge LLM with majority voting for quality

4. **High-Quality Medical Dialogue Synthesis** (EMNLP 2025 Industry)
   - Two-stage quality control: rule-based filtering + reward-based assessment
   - Rule-based checks: role consistency, terminology validity, utterance length

5. **NVIDIA Clinical ASR Evaluation Flywheel** (2025)
   - Pronunciation validation before TTS synthesis
   - LLM-proposed IPA candidates + human review gate

6. **Synthetic Doctor-Patient Dialogue for Medical ASR** (EACL 2026 Industry)
   - Vocabulary expansion + privacy preservation
   - MWER/kwWER metrics for medical term accuracy

### Datasets

| Dataset | Size | Speakers | Key Metadata | License |
|---------|------|----------|--------------|---------|
| ViMedCSS | 34.6h | Video source diversity | topic, cs_terms, segment_text | CC-BY |
| VietMed | 16h labeled | Multiple | ICD-10, speaker roles, recording conditions | Check license |
| PhoAudiobook | 941h | 735 | Speaker IDs | ACL 2025 paper |
| VieNeu-TTS-500h-Dialects | 500h | Multiple | North/Central/South dialect labels | CC-BY |
| ViMD | 63 dialects | Speaker IDs | Province, region, gender | Public |
| HoangHa/medical-data | 10K+ conversations | Personas | 1,236 diseases, CFPC/OPQRST frameworks | HF |
| ViMed-SFT | 10,085 | N/A | ChatML format, medical Q&A | HF |
| Meddies/patient-safety | 22,336 queries | N/A | 5 safety axes, LLM-as-judge filtering | HF |

## Research Gaps to Address in Later Phases

1. **VietMed license verification**: Cannot proceed without explicit license confirmation from dataset owners.
2. **Human pronunciation review workflow**: Clinician involvement needed for medical term IPA validation.
3. **Diarization reference RTTM**: VietMed-test may not have speaker turn annotations; may need subset labeling.
4. **Fine-tuning compute budget**: PhoWhisper-small fine-tuning requires GPU resources; need allocation.
5. **ICD-10 endpoint SLA**: KCB ICD-10 endpoint is reverse-engineered; no official SLA.

---

*Feature research for: VietMedVoice Phase 2 Enhancement (v1.1)*
*Researched: 2026-06-19*
