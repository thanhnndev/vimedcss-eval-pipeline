# Pitfalls Research

**Domain:** Vietnamese Medical Code-Switching ASR Data Pipeline — Phase 2 Enhancement
**Researched:** 2026-06-19
**Confidence:** MEDIUM-HIGH

> Adding ICD-10 ingestion, medical term inventory, LLM conversation generation, TTS, voice pool, PhoWhisper fine-tuning, and ASR/diarization evaluation to an existing Vietnamese medical code-switching ASR evaluation pipeline.

## Critical Pitfalls

### Pitfall 1: Joining ICD-10 EN/VI by Label Text Instead of Code

**What goes wrong:**
ICD-10 disease labels differ between English and Vietnamese translations. Joining by label text produces zero or near-zero matches, resulting in an effectively empty dual-language inventory.

**Why it happens:**
- English label: "Essential hypertension" → Vietnamese label: "Tăng huyết áp nguyên phát"
- The KCB endpoint serves EN and VI separately; teams assume translations are identical across languages
- Developers copy-paste English labels into Vietnamese columns assuming positional correspondence
- The Vietnamese free-text search endpoint is unreliable for code lookup, tempting teams to use fuzzy label matching

**How to avoid:**
- **Mandatory:** Join EN/VI records exclusively by `code` field (e.g., `I10` maps to `I10`)
- Normalize codes (strip whitespace, uppercase, handle `I10-I15` range codes vs. leaf codes like `I10`)
- If code mapping fails, fall back to searching by code in the VI endpoint's `code` field, not free-text
- Log every unmatched code with both EN and VI response payloads for debugging
- Verify parent-child hierarchy separately from the label join

**Warning signs:**
- Dual-language inventory has >90% null `label_vi` fields
- Coverage audit reports "0 Vietnamese disease terms matched"
- Ingestion error log shows "label mismatch" for common codes like `I10`, `E11`, `J18`

**Phase to address:** FR1 — ICD-10 Ingestion (Week 1)

---

### Pitfall 2: ICD-10 Endpoint Fragility — No Retry, No Caching, No Versioning

**What goes wrong:**
The reverse-engineered KCB ICD-10 endpoint has no official SLA. Queries fail silently (empty JSON), timeout, or return malformed HTML. Without retry logic, caching, and response versioning, the pipeline produces incomplete inventories with no traceability.

**Why it happens:**
- Teams treat the endpoint as a stable API with guaranteed responses
- Single HTTP request without exponential backoff or circuit breaker
- No local cache of raw responses — every run re-queries the endpoint
- No `fetched_at` timestamp or endpoint version tracking — impossible to reproduce the exact inventory
- No error categorization — transient vs. permanent failures not distinguished

**How to avoid:**
- Implement exponential backoff retry (3-5 attempts, starting at 1s delay)
- Cache raw JSON/HTML responses to `data/raw/icd10/cache/` with `code + lang + timestamp` keys
- Store the full raw response alongside parsed output for debugging
- Add `source_url` and `fetched_at` to every record
- Track endpoint version/schema changes; alert when response structure changes
- Maintain a fallback: if >10% of codes fail, flag and halt — do not silently continue with partial data
- Have a manual fallback CSV ready for critical codes that consistently fail

**Warning signs:**
- Ingestion report shows "N codes failed out of M total"
- Error log contains "Connection timeout" or "Empty response"
- Dual-language file has fewer records than expected (ICD-10 has ~14,000+ codes at 3-4 character depth)
- No `source_url` field in output records

**Phase to address:** FR1 — ICD-10 Ingestion (Week 1)

---

### Pitfall 3: Treating ICD-10 as Sufficient for All Medical Terms

**What goes wrong:**
ICD-10 covers diseases only. Drug names (metformin, amoxicillin), lab tests (HbA1c, eGFR), procedures (MRI, CT, ECG), abbreviations (NPO, PRN, stat), biomarkers, hormone names, device names, units, and dosages are NOT in ICD-10. Building a term inventory from ICD-10 alone produces a fundamentally incomplete system.

**Why it happens:**
- ICD-10 is the most well-known medical vocabulary, so teams assume it is comprehensive
- PRD explicitly flags this, but implementation teams often overlook it under time pressure
- External lexicon lists have unclear licenses, making teams hesitant to ingest them
- The term inventory ends up dominated by disease terms, with no coverage of the other 7+ entity types

**How to avoid:**
- Design term taxonomy from Day 1 with entity types beyond disease: drug, lab_test, procedure, abbreviation, hormone, biomarker, device, unit, dosage
- Explicitly source each entity type from a named, licensed source
- For each entity type without a licensed source, create an `llm_generated_candidate` bucket with `review_status: not_verified`
- Track source coverage per entity type — if one type has zero sources, flag it explicitly
- Separate ICD-10 terms (disease backbone) from non-ICD terms clearly in schema and reporting

**Warning signs:**
- `entity_type` column is >80% "disease" or "null"
- No drug/lab/procedure terms in the term inventory
- Coverage audit cannot find any non-ICD terms to match against
- PRD requirement FR2 states "extended inventory" but output only contains ICD-10 terms

**Phase to address:** FR2 — Medical Term Taxonomy (Week 1-2)

---

### Pitfall 4: LLM Hallucination in Doctor-Patient Conversations — Medical Fact Fabrication

**What goes wrong:**
LLM generates medically inaccurate, contraindicated, or fabricated conversations. Drug dosages, symptom descriptions, disease progressions, or treatment recommendations in synthetic conversations are incorrect. Downstream TTS and ASR training then learns wrong medical patterns.

**Why it happens:**
- LLMs hallucinate when generating clinical content without grounding in a knowledge source
- Prompt without retrieval-augmented grounding allows free-form medical text generation
- SOAP format or consultation structure alone does not prevent factual hallucination
- Medical coherence ≠ medical accuracy — LLMs produce fluent but wrong medical content
- Code-switching amplifies hallucination: English medical terms embedded in Vietnamese are especially prone to "fluent nonsense"

**How to avoid:**
- Use retrieval-augmented generation (RAG): retrieve relevant ICD-10/drug/procedure facts before generating each conversation turn
- Require each conversation to trace back to a specific ICD code and term list — no free generation
- Implement post-generation medical fact validation: check drug names against RxNorm, dosages against standard ranges, procedures against CPT/ICD-10-PCS
- Add explicit safety flags: `safety_flags: ["contraindicated_drug_combo", "invalid_dosage"]`
- Human review sample rate: minimum 5-10% of conversations reviewed by a medical domain expert
- Never use LLM output as ground truth — label all LLM-generated content with `generation_model`, `prompt_version`, `llm_review_status`

**Warning signs:**
- Conversation validation errors log is empty (suggests no validation is running)
- Drug names in conversations are misspelled or non-existent compounds
- Safety flags column is always empty
- Human review queue has never been checked
- LLM model has no version pinning (gpt-4 vs gpt-5 outputs differ significantly)

**Phase to address:** FR5 — LLM Conversation Generation (Week 4)

---

### Pitfall 5: TTS Reading English Medical Terms Incorrectly in Vietnamese Sentences

**What goes wrong:**
TTS system mispronounces or garbles English medical terms embedded in Vietnamese sentences. Terms like "MRI", "CT scan", "ECG", "HbA1c", "eGFR", "metformin", "corticosteroid" are read with wrong phonemes, wrong stress, or wrong language mode switching. Round-trip ASR then fails on these terms, corrupting the synthetic evaluation signal.

**Why it happens:**
- Vietnamese TTS models are often trained primarily on Vietnamese-only data
- English code-switching pronunciation is handled poorly or not at all by local TTS models
- G2P (grapheme-to-phoneme) tools for Vietnamese do not handle English sub-word units
- Vietnamese speakers themselves substitute /θ/→/t/, /ð/→/d/, /ʃ/→/s/ for English sounds — TTS may or may not model this correctly
- Medical abbreviations (HbA1c, eGFR) have no standard TTS pronunciation rules
- Turbo/low-quality TTS modes sacrifice English pronunciation quality for speed

**How to avoid:**
- Test TTS pronunciation explicitly on a medical term list BEFORE committing to a TTS model
- Include both Vietnamese text AND English terms in test prompts — not just Vietnamese
- Check abbreviations individually: "MRI" vs "M.R.I." vs "mri" produce different outputs
- Use a bilingual/code-switching-capable TTS (e.g., VieNeu-TTS with sea-g2p) or have a fallback API TTS
- Implement round-trip ASR check with automatic flagging of terms where ASR output ≠ TTS input
- Log per-term pronunciation quality — do not aggregate away individual term failures
- Never use Turbo mode for medical terms — use GPU/Standard quality for pronunciation accuracy

**Warning signs:**
- Round-trip ASR check shows systematic failures on English terms only (Vietnamese terms pass)
- TTS model has no explicit code-switching support documented
- Term pronunciation test results show >20% English term failure rate
- TTS report recommends "acceptable quality" without per-term breakdown

**Phase to address:** FR7 — TTS Model Research (Week 5)

---

### Pitfall 6: Synthetic Audio Overwhelming Real Data in PhoWhisper Fine-Tuning

**What goes wrong:**
Fine-tuning PhoWhisper with too much synthetic TTS audio causes the model to overfit to synthetic speech characteristics — clean audio, uniform prosody, limited speaker diversity, robotic cadence. The fine-tuned model performs worse than zero-shot on real medical audio.

**Why it happens:**
- Synthetic data is cheap and scalable, tempting teams to use it as the primary training source
- Real medical speech (VietMed) has high variance: overlapping speakers, filler words, disfluencies, regional accents, background noise
- Synthetic audio lacks these characteristics; training on synthetic teaches the model the wrong distribution
- Batch normalization statistics become biased toward synthetic data characteristics
- No rejection sampling — low-quality synthetic samples still contribute to training
- PRD correctly states "synthetic only for train/augmentation" but teams misread this as "synthetic is fine to dominate"

**How to avoid:**
- Cap synthetic data at 20-30% of total training volume (never >50%)
- Keep a real-data-only checkpoint as the ablation baseline (E0 in PRD's E0/E1/E2/E3 framework)
- Apply noise augmentation and reverberation to synthetic audio to increase variance
- Use separate batch normalization statistics for real vs. synthetic samples during training
- Implement rejection sampling: filter synthetic samples where round-trip ASR fails or WER is high
- Evaluate on real medical audio after each fine-tune run — never evaluate on synthetic test
- Monitor for catastrophic forgetting: zero-shot baseline should be evaluated alongside fine-tuned models on the same test set

**Warning signs:**
- Fine-tuned model WER is worse than zero-shot on real test audio
- Training logs show synthetic data dominates (synthetic hours > real hours)
- No ablation study comparing real-only vs. synthetic+real vs. synthetic-only
- Batch normalization statistics not tracked separately for real vs. synthetic
- Round-trip ASR filtering is not implemented

**Phase to address:** FR11 — TV3 ASR & Diarization (Week 7-8)

---

### Pitfall 7: Catastrophic Forgetting in PhoWhisper Fine-Tuning

**What goes wrong:**
Fine-tuning PhoWhisper on Vietnamese medical speech causes it to lose its multilingual capabilities and general ASR performance. The model becomes worse at recognizing non-Vietnamese languages, edge cases, or even Vietnamese words outside the medical domain.

**Why it happens:**
- PhoWhisper is initialized from multilingual Whisper checkpoints with broad language coverage
- Full-parameter fine-tuning on a narrow medical dataset updates all weights, erasing general capabilities
- Small medical datasets (even synthetic) relative to PhoWhisper's parameter count cause overfitting
- Vietnamese medical code-switching is already a niche — the fine-tuned model becomes hyper-specialized

**How to avoid:**
- Use parameter-efficient fine-tuning (PEFT): LoRA or bottleneck adapters instead of full fine-tuning
- Freeze lower encoder layers — fine-tune only the upper encoder layers and decoder
- Implement two-stage fine-tuning: Stage 1 on general Vietnamese speech, Stage 2 on medical speech
- Use metric-driven donor dataset selection (e.g., Fréchet DeepSpeech Distance) to choose the most similar general-domain dataset for Stage 1
- Evaluate on both medical domain test set AND general Vietnamese ASR benchmark — monitor for regression
- Keep the original PhoWhisper checkpoint as a restoration point

**Warning signs:**
- Fine-tuned model WER on general Vietnamese speech (non-medical) is worse than zero-shot
- Per-layer gradient analysis shows updates in bottom encoder layers (should be frozen)
- No LoRA/bottleneck adapter configuration in training config
- Training loss drops to near-zero quickly (sign of overfitting, not convergence)

**Phase to address:** FR11 — TV3 ASR & Diarization (Week 7-8)

---

### Pitfall 8: DER/JER Without Reference Diarization — Claiming Accuracy That Doesn't Exist

**What goes wrong:**
Teams report DER/JER metrics on VietMed-test audio without having a human-annotated ground truth diarization (RTTM). The reported DER is meaningless because there is no reference to compare against — they are computing self-consistency, not evaluation.

**Why it happens:**
- pyannote 3.1 outputs RTTM files, giving the appearance of a valid evaluation
- DER formula looks mathematically rigorous, but it compares hypothesis to hypothesis (no ground truth)
- Teams conflate "diarization system output" with "diarization evaluation"
- VietMed dataset does not ship with speaker turn annotations, so teams use pyannote output as if it were ground truth

**How to avoid:**
- Only report DER/JER when a human-annotated RTTM exists — this is a gating condition
- If no reference RTTM exists: report only qualitative metrics — speaker count accuracy, turn statistics, sample qualitative analysis
- Clearly label all RTTM files: `pyannote_hypothesis.rttm` vs `reference.rttm` — never mix them
- If evaluating DER without reference: report it as "proxy DER" or "self-consistency score", not as a real metric
- Plan to create a human-labeled RTTM subset for at least a sample of VietMed-test audio

**Warning signs:**
- `diarization_metrics.csv` contains DER values but there is no `reference.rttm` file
- Report claims "DER of X%" without stating the reference source
- pyannote output is used in DER computation without distinguishing hypothesis vs. reference
- File naming does not distinguish hypothesis from ground truth

**Phase to address:** FR11 — TV3 ASR & Diarization (Week 7-8)

---

### Pitfall 9: Claiming ASR Improvement Without Controlled Ablation on Real Audio

**What goes wrong:**
Team reports that fine-tuned PhoWhisper "improves WER by X%" based on evaluation against synthetic TTS audio or without comparing against the zero-shot baseline. Claims of improvement are invalid because the test set is not real, the baseline is missing, or the evaluation is not controlled.

**Why it happens:**
- Evaluating on synthetic audio gives artificially low WER because the ASR model was partially trained on similar synthetic data
- Comparing fine-tuned to zero-shot on different test sets gives incomparable results
- Teams want to show improvement and selectively report favorable comparisons
- The ablation design (E0/E1/E2/E3 in PRD) is not implemented — only one model is evaluated

**How to avoid:**
- Every evaluation run must include the zero-shot baseline (E0) as a comparison point
- Test set must be real medical audio only — never synthetic audio for final evaluation
- All E0/E1/E2/E3 runs must be evaluated on the identical test set with identical preprocessing
- Report absolute WER change AND relative change: "WER improved from 25.3% to 18.1% (28% relative reduction)"
- If no improvement is observed, report it honestly: "E1 (synthetic-only) showed no improvement over E0 on real test audio"
- Separate the ablation report from the final claim: first show E0→E1→E2→E3 comparison, then interpret

**Warning signs:**
- ASR evaluation report shows improvement but does not include E0 zero-shot baseline
- Test set includes synthetic TTS audio
- Improvement is reported only on synthetic or on a different test set than the baseline
- No ablation study — only one model is evaluated

**Phase to address:** FR10 + FR11 — ASR Evaluation (Week 6, 8)

---

### Pitfall 10: Inferring Speaker Gender/Age/Region Without Evidence

**What goes wrong:**
Team guesses or uses automated models to infer speaker gender, age bucket, or regional accent from audio when the source dataset does not provide this metadata. Downstream slice evaluation then reports metrics "by gender/region/age" that are based on fabricated labels.

**Why it happens:**
- Voice pool datasets (viVoice) may not publish speaker metadata
- Team wants to show slice-level ASR metrics for fairness analysis
- Automated gender/age estimation models exist, tempting teams to use them
- No explicit policy against guessing is enforced in the pipeline

**How to avoid:**
- Default to `unknown` for any speaker attribute not explicitly provided by the dataset
- If using estimated attributes from a model, label them as `estimated_gender`, `estimated_age_bucket`, `estimated_region` with a confidence score
- Store `*_status` fields: `provided`, `estimated`, `unknown` — never store inferred values as if they were facts
- In reporting, filter out slices with <N samples (e.g., <20) or with `unknown` status
- PRD constraint is explicit: "Do not guess gender/age/region when metadata is not provided"

**Warning signs:**
- Voice profile cards show gender/age/region without a `*_status` field
- ASR metrics by slice include demographics that are not in the source dataset
- No `estimated_*` prefix on any metadata field
- Voice pool report claims regional diversity without citing source evidence

**Phase to address:** FR8 — Voice Pool Research (Week 5)

---

### Pitfall 11: Mixing Synthetic and Real Audio in Test Set

**What goes wrong:**
The final ASR evaluation uses a test set that mixes synthetic TTS audio with real medical audio. Reported WER/CER/term recall numbers are meaningless because synthetic audio has fundamentally different acoustic characteristics than real speech.

**Why it happens:**
- Synthetic and real audio get stored in the same directory without clear labeling
- The test set manifest does not have a `source` field distinguishing synthetic from real
- The evaluation harness loads all audio from a single manifest without filtering
- Pipeline outputs are mixed and reported together

**How to avoid:**
- The PRD constraint is explicit: "Final ASR test must be real-only"
- Enforce this at the manifest level: `data/eval/eval_manifest.jsonl` must have `source: vietmed` or `source: vimedcss` — never `source: synthetic`
- Implement a manifest preflight check: fail if any row in the test manifest has `source: synthetic`
- Keep synthetic audio in a separate directory tree: `data/synthetic_tts/` vs. `data/vietmed/`
- Evaluation report must explicitly state "Test set: real medical audio only (N segments from VietMed/ViMedCSS)"

**Warning signs:**
- Test manifest contains rows with mixed `source` values
- Synthetic audio files appear in the eval manifest
- Report does not specify whether test audio is synthetic or real
- No preflight check preventing synthetic test data

**Phase to address:** FR9 — Synthetic TTS Pilot (Week 5) + FR10 — ASR Evaluation (Week 6)

---

### Pitfall 12: Conflating ASR-Oriented Diarization with Ground Truth

**What goes wrong:**
Diarization outputs from pyannote 3.1 are treated as ground truth speaker turns for DER computation, but ASR-oriented datasets (like VietMed) often merge speaker turns, ignore pauses, or use utterance-level rather than turn-level annotations. Comparing pyannote's fine-grained speaker segmentation against coarse ASR annotations inflates DER artificially.

**Why it happens:**
- VietMed was designed for ASR, not for diarization evaluation
- pyannote produces detailed speaker segment boundaries; VietMed annotations are rougher
- DER penalizes accurate detection of pauses and turn boundaries that the ASR annotation intentionally ignores
- Teams do not realize that annotation granularity mismatch makes DER meaningless in this context

**How to avoid:**
- For datasets without proper diarization annotations, do not compute DER at all
- Report qualitative diarization metrics: speaker count accuracy, turn frequency, sample transcript comparisons
- If DER must be computed, use a forgiveness collar (250ms-500ms) to ignore minor boundary shifts
- Set `skip_overlap=True` if overlap detection is not part of the evaluation scope
- Document the annotation mismatch in the report — "DER computed against ASR-oriented annotations, which may inflate error rates"
- Consider creating a small human-labeled RTTM subset for accurate DER evaluation

**Warning signs:**
- DER on VietMed-test is very high (>30%) without explanation
- Report does not mention that VietMed annotations are ASR-oriented
- pyannote output is compared directly against VietMed speaker labels without collar adjustment
- No mention of annotation granularity mismatch

**Phase to address:** FR11 — TV3 ASR & Diarization (Week 7-8)

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Joining ICD-10 EN/VI by label text | Simpler SQL/join logic | Empty dual-language inventory; rework required | Never |
| Skipping retry on ICD-10 endpoint | Faster pipeline build | Incomplete inventory; non-reproducible results | Never |
| Using ICD-10 as sole term source | Single vocabulary to manage | Term inventory misses 7+ entity types | Never for production |
| Skipping medical fact validation in LLM generation | Faster conversation output | Fabricated medical content in dataset | Never |
| Evaluating fine-tune on synthetic test audio | Easier to show "improvement" | Invalid improvement claim | Never |
| Computing DER without reference RTTM | Appears to have a metric | False precision; misleading report | Never |
| Using estimated speaker metadata as facts | Richer slice reporting | Fabricated demographic labels | Only with `estimated_*` prefix and confidence |
| Full-parameter PhoWhisper fine-tuning | Simpler training code | Catastrophic forgetting; compute waste | Only if LoRA is proven insufficient |
| Using Turbo TTS mode for production | Faster audio generation | Garbled English terms | Only for rapid prototyping, not evaluation |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| KCB ICD-10 endpoint | Treating as stable API with guaranteed responses | Exponential backoff retry, caching, raw response storage, partial-failure gating |
| VietMed dataset | Downloading without checking license | QA/Ethics approval before any data access; audit only if license permits |
| PhoWhisper model | Full fine-tune without PEFT | LoRA or adapter-based fine-tuning; freeze lower encoder layers |
| pyannote 3.1 | Assuming gated model access is automatic | Accept model conditions on Hugging Face; prepare fallback or skip diarization |
| WhisperX alignment | Using WhisperX output as ground truth | Label as "hypothesis" only; require human review before treating as reference |
| LLM conversation generation | No JSON schema enforcement | Use structured output with Pydantic/JSON schema validation; reject malformed responses |
| TTS + ASR round-trip | Aggregating WER instead of per-term analysis | Per-term flagging: which specific terms fail round-trip |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| ICD-10 code range expansion | Dual-language inventory has 3x expected records (range codes like I00-I99 expand) | Parse chapter/section/type hierarchy; separate range codes from leaf codes | At coverage audit phase |
| Medical term inventory growth | Inventory grows to 50K+ terms without deduplication | Canonical normalization before ingestion; case/accent-insensitive dedup | At LLM generation phase (prompt inflation) |
| Synthetic audio dominates training | >50% synthetic in fine-tune → worse real audio WER | Hard cap at 20-30% synthetic; separate batch normalization | After fine-tuning, when real test fails |
| pyannote overlap handling | DER inflated on doctor-patient audio with overlaps | Use `skip_overlap=True` or implement overlap module; report overlap-aware metrics separately | On audio with >2 speakers or overlapping speech |
| ASR slice metrics on small samples | High WER variance per slice; meaningless conclusions | Minimum N per slice (e.g., 20 segments); report confidence intervals | At WER by region/gender/specialty reporting |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Publishing real patient audio | PHI exposure, GDPR/HIPAA violation | Never include VietMed audio in public release without explicit license and consent verification |
| Voice cloning without consent | Identity theft, impersonation | Restrict to `synthetic_speaker_id`; never store or clone real voice characteristics |
| LLM generating medical advice in conversations | Legal liability, safety incident | Include explicit `synthetic_context` flag; add safety review queue; never present as real consultations |
| Storing API keys in pipeline config | Key exposure in version control | Use environment variables; never commit keys to repo |
| Claiming ICD-10 coverage without verified audit | Misleading dataset card, research integrity issue | Local verified numbers only; separate paper_reported vs. local_verified |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Coverage report in English only | Vietnamese researchers cannot read findings | PRD requires Vietnamese final report; produce bilingual metrics tables |
| Missing term examples in coverage report | Researchers cannot verify accuracy | Every coverage claim needs 2-3 concrete term + sentence examples |
| DER metric reported without context | Non-specialists misinterpret DER as accuracy | Explain DER components (false alarm, missed detection, confusion); compare to benchmark baselines |
| No error log for failed TTS pronunciations | Engineers cannot debug term-level failures | Per-term quality status field; failed pronunciations must be logged, not silently dropped |

---

## "Looks Done But Isn't" Checklist

- [ ] **ICD-10 Ingestion:** Has dual-language join been verified by code (not label text)? Check 10 random codes manually.
- [ ] **ICD-10 Ingestion:** Are there raw cached responses for every code in `data/raw/icd10/cache/`?
- [ ] **Term Inventory:** Does the inventory cover all 9 entity types (disease, drug, lab_test, procedure, abbreviation, hormone, biomarker, device, unit, dosage)?
- [ ] **Term Inventory:** Are all non-ICD terms traced to a named source with license verification?
- [ ] **LLM Conversations:** Is every conversation traceable to a specific ICD code and term list?
- [ ] **LLM Conversations:** Does the validation log capture JSON schema errors, medical fact errors, and safety flag triggers separately?
- [ ] **LLM Conversations:** Has a medical domain expert reviewed at least 5% of conversations?
- [ ] **TTS Research:** Has the TTS model been tested specifically on English medical terms in Vietnamese sentences?
- [ ] **TTS Research:** Are per-term pronunciation results logged, not just aggregate MOS scores?
- [ ] **Voice Pool:** Are all speaker attributes labeled as `provided`, `estimated`, or `unknown` — never unlabeled?
- [ ] **Synthetic TTS:** Does the round-trip ASR check flag per-term failures, not just aggregate WER?
- [ ] **Synthetic TTS:** Are failed pronunciations logged and excluded from training?
- [ ] **ASR Evaluation:** Is the test set confirmed real-only (no synthetic audio)?
- [ ] **ASR Evaluation:** Does every evaluation run include E0 zero-shot baseline?
- [ ] **ASR Evaluation:** Are WER improvements reported with absolute and relative change on the same test set?
- [ ] **PhoWhisper Fine-tune:** Is PEFT (LoRA/adapter) used instead of full-parameter fine-tuning?
- [ ] **PhoWhisper Fine-tune:** Is there an ablation comparing E0/E1/E2/E3 on the same real test set?
- [ ] **Diarization:** Is there a human-annotated reference RTTM before claiming DER/JER?
- [ ] **Diarization:** Are pyannote outputs clearly labeled as hypothesis, not ground truth?
- [ ] **Privacy/License:** Has VietMed audio access been approved by QA/Ethics before any download?
- [ ] **Reporting:** Are `paper_reported`, `hf_reported`, `local_verified` metrics separated in all reports?

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| EN/VI join by label instead of code | HIGH — need to re-ingest all codes | Re-run ingestion with code-based join; verify with manual spot-check of 10 codes |
| Endpoint failures causing partial inventory | MEDIUM — need to retry failed codes | Use cached raw responses; re-parse only failed codes; compare old vs. new |
| Synthetic dominates training data | HIGH — need to retrain | Strip synthetic from training set; re-run fine-tune with 20-30% cap |
| Test set contains synthetic audio | HIGH — need to rebuild test manifest | Separate synthetic from real manifests; rebuild eval manifest with real-only |
| DER computed without reference | LOW-MEDIUM — just stop reporting it | Remove DER from report; switch to qualitative metrics; plan human annotation |
| Medical hallucination in conversations | HIGH — need to regenerate and revalidate | Regenerate conversations with RAG grounding; re-run validation; increase review rate |
| Speaker metadata guessed without evidence | MEDIUM — need to relabel | Change all guessed values to `estimated_*` with confidence; add `*_status: estimated` field |
| TTS garbles English terms | MEDIUM — need to switch TTS | Test alternative TTS; re-generate audio with code-switching-capable model; re-run round-trip |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| EN/VI join by label | FR1 — ICD-10 Ingestion | Spot-check 10 random codes manually |
| Endpoint fragility | FR1 — ICD-10 Ingestion | Verify cache exists; check ingestion error log |
| ICD-10 insufficient alone | FR2 — Term Taxonomy | Count entity types in inventory; flag any type with zero sources |
| LLM hallucination | FR5 — LLM Generation | Human review sample rate; validation error log |
| TTS mispronunciation | FR7 — TTS Research | Per-term round-trip ASR; flag >5% English term failure |
| Synthetic dominates fine-tuning | FR11 — TV3 ASR | Training data ratio log; ablation study E0→E3 |
| Catastrophic forgetting | FR11 — TV3 ASR | General Vietnamese ASR benchmark vs. zero-shot |
| DER without reference | FR11 — TV3 ASR | Reference RTTM file exists before reporting DER |
| Improvement claim without ablation | FR10 + FR11 | E0 baseline included in every evaluation |
| Guessed speaker metadata | FR8 — Voice Pool | `*_status` field present on every voice profile |
| Synthetic in test set | FR10 — ASR Evaluation | Manifest preflight check; source field on every row |
| Annotation mismatch | FR11 — TV3 ASR | DER report acknowledges ASR-oriented annotation limitations |

---

## Sources

- ICD-10 coding mistakes: [HealthOrbit](https://healthorbit.ai/blog/icd-10-coding-mistakes/), [AAPC](https://www.aapc.com/blog/73732-top-10-icd-10-cm-coding-errors/)
- ICD-10 NLP pipeline architecture: [Nirmitee Medical Coding AI](https://nirmitee.io/blog/medical-coding-ai-icd10-cpt-nlp-accuracy-challenges/)
- Hybrid-Code zero-hallucination ICD coding: [arXiv 2512.23743](https://arxiv.org/html/2512.23743v2)
- Medical term normalization challenges: [PMC4713367](https://pmc.ncbi.nlm.nih.gov/articles/PMC4713367/), [JMIR Medical Informatics](https://medinform.jmir.org/2021/1/e23104)
- Clinical entity extraction brittleness: [MLR Press Agrawal et al. 2020](http://proceedings.mlr.press/v126/agrawal20a/agrawal20a.pdf)
- LLM medical synthetic data: [MDPI MDPI-6-109](https://www.mdpi.com/2673-2688/6/6/109)
- Synthetic clinical notes evaluation: [arXiv 2605.17775](https://arxiv.org/html/2605.17775v1)
- Synthetic data for healthcare AI: [The Momentum](https://www.themomentum.ai/blog/creating-synthetic-training-data-for-healthcare-ai)
- Code-switching ASR challenges: [arXiv 2602.12911 ViMedCSS](https://arxiv.org/pdf/2602.12911)
- Contrastive training for code-switching: [arXiv 2606.06985](https://arxiv.org/html/2606.06985v1)
- BioBridge code-switched EMR: [arXiv 2412.11671](https://arxiv.org/html/2412.11671v1)
- Vietnamese pronunciation errors: [CTU Journal](https://ctujs.ctu.edu.vn/index.php/ctujs/article/download/448/610), [SSH Journal](https://sshjournal.com/index.php/sshj/article/view/1761/730)
- VieNeu-TTS: [GitHub pnnbao97/VieNeu-TTS](https://github.com/pnnbao97/VieNeu-TTS)
- TTS dataset quality: [Flaunt Audio](https://flauntaudio.com/what-makes-a-good-tts-dataset/)
- Audio dataset challenges: [Andovar](https://blog.andovar.com/challenges-audio-speech-datasets/)
- Metadata for speech data: [Andovar](https://blog.andovar.com/metadata-speech-data-audio-datasets/)
- Speaker diversity vs. dataset size: [INTERSPEECH 2023 Maison et al.](https://www.isca-archive.org/interspeech_2023/maison23_interspeech.pdf)
- Augmented datasheets for speech datasets: [arXiv 2305.04672](https://export.arxiv.org/pdf/2305.04672v1.pdf)
- Whisper fine-tuning strategies: [Springer JASMP 2024](https://link.springer.com/article/10.1186/s13636-024-00349-3)
- PhoWhisper: [arXiv 2406.02555](https://ar5iv.labs.arxiv.org/html/2406.02555)
- Two-stage Whisper fine-tuning: [JMST](https://online.jmst.info/index.php/csce/article/view/1889)
- Whisper fine-tune notebook: [GitHub HKAB/whisper-finetune-1-notebook](https://github.com/HKAB/whisper-finetune-1-notebook)
- pyannote DER evaluation: [pyannote.ai](https://www.pyannote.ai/blog/how-to-evaluate-speaker-diarization-performance)
- pyannote metrics documentation: [pyannote.github.io](https://pyannote.github.io/pyannote-metrics/reference.html)
- ASR corpus repurposed for diarization: [arXiv 2507.09226](https://arxiv.org/html/2507.09226v2)
- tcpWER and overlap-aware metrics: [wiki/charleschen.ai](https://wiki.charleschen.ai/arxiv/processed/2603.22709v1-who-spoke-what-when-evaluating-spoken-language-models-for-conversat)
- TTS augmentation for ASR: [arXiv 2503.08954](https://arxiv.org/html/2503.08954)
- Synt++ imperfect synthetic data: [arXiv 2110.11479](https://ar5iv.labs.arxiv.org/html/2110.11479)
- Synthetic speech data pitfalls: [FutureBee AI](https://www.futurebeeai.com/knowledge-hub/pitfalls-synthetic-speech-data)
- Synthetic vs. real human speech: [Andovar](https://blog.andovar.com/synthetic-data-isnt-enough-why-high-variance-human-speech-is-still-critical-for-model-robustness)
- Medical code validation agent: [Corti AI](https://www.corti.ai/agents/code-validation-agent)

---
*Pitfalls research for: VietMedVoice Phase 2 Enhancement (v1.1)*
*Researched: 2026-06-19*
*Confidence: MEDIUM-HIGH (web search sources verified against academic papers and official documentation; some domain-specific Vietnamese medical speech findings are from recent 2025-2026 papers)*
