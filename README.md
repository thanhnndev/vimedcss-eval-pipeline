# ViMedCSS Term Coverage & ASR Code-Switching Evaluation Pipeline

Pipeline đánh giá mức độ bao phủ của thuật ngữ y tế (Term Coverage) và hiệu năng ASR trên tập dữ liệu trộn mã Anh/Việt (Code-Switching) `tensorxt/ViMedCSS` từ Hugging Face. Toàn bộ quy trình hướng đến câu hỏi nghiên cứu chính: *ViMedCSS cover các thuật ngữ y tế CS thuộc domain nào, và ASR yếu ở đâu với tiếng Anh/Việt trộn ngôn ngữ?*

---

## 1. Kiến trúc tổng thể

Pipeline được chia thành 5 nhóm xử lý chính theo dõi từ input metadata Hugging Face đến báo cáo cuối:

```text
INPUT
├── HF dataset ViMedCSS
├── Paper và dataset card
├── Medical domain taxonomy
├── Medical entity schema
└── External medical term inventory

PROCESS 1: HF ingestion
├── Fetch metadata từ HF
├── Verify local metadata
└── Download audio khi cần

PROCESS 2: Term inventory
├── Extract cs_terms_list
├── Normalize terms
└── Build unique term inventory

PROCESS 3: LLM classification
├── Classify term với GPT-5 mini
├── Validate JSON output
└── Tạo hàng đợi human review

PROCESS 4: Coverage analysis
├── Nhóm theo medical domain
├── Nhóm theo entity type
├── So với external inventory
└── Phân tích hard/rare terms

PROCESS 5: ASR evaluation
├── Build ASR manifest
├── Run ASR baseline
├── Compute ASR metrics
└── Phân tích ASR errors

OUTPUT FILES
├── raw_hf_metadata
├── verified_dataset_stats.json
├── cs_terms_inventory.csv
├── cs_terms_classified.csv
├── domain_coverage_matrix.csv
├── external_inventory_coverage.csv
├── hard_terms_report.csv
├── asr_manifest.jsonl
├── asr_predictions.jsonl
├── asr_metrics_by_domain.csv
└── final_report_vi.md
```

Luồng chi tiết từ HF đến báo cáo cuối:

```text
HF metadata --> Audit --> Extract terms --> Normalize --> Classify --> Coverage --> Report
                                          \--> External match --> ASR eval --> ASR report
```

---

## 2. Câu hỏi nghiên cứu

Pipeline tập trung trả lời 3 câu hỏi chính:

### 2.1 ViMedCSS cover những medical terms nào?

- Liệt kê unique CS terms, tần suất, split xuất hiện, topic tương ứng, và ví dụ câu chứa term.
- Phân loại entity category và medical domain/specialty.
- Đánh dấu common/rare/hard-only/unknown.
- Ghi confidence và nguồn phân loại.

### 2.2 ASR yếu ở đâu với code-switching Anh/Việt?

- Xác định term nào bị ASR nhận sai nhiều nhất.
- Phân loại lỗi: bỏ mất term, phiên âm Việt hóa, nhầm spelling, thay bằng từ Việt khác.
- Phân tích theo domain (drug/lab/procedure/abbreviation/hormone/pathogen).
- So sánh hard split với test split thường.

### 2.3 Dataset hiện tại cover tốt chưa?

- So sánh ViMedCSS với VietMed, PhoASR, VietSuperSpeech, và các nguồn tham chiếu khác.
- Kết luận trung thực về điểm mạnh/điểm yếu và thiếu label nào để đánh giá medical ASR tốt hơn.

---

## 3. Kiến trúc thư mục

```text
vimedcss-eval-pipeline/
├── README.md
├── Makefile
├── requirements.txt
├── configs/
│   ├── dataset.yaml          # Cấu hình dataset (repo, splits, expected fields)
│   ├── taxonomy.yaml         # Phân nhóm tần suất thuật ngữ
│   ├── llm.yaml              # Cấu hình LLM Classifier
│   ├── asr.yaml              # Cấu hình ASR Baseline
│   ├── external.yaml         # Cấu hình external reference match
│   └── report.yaml           # Cấu hình báo cáo
├── data/
│   ├── raw/                  # Dữ liệu gốc tải về từ HF (đã ignore)
│   ├── interim/              # Dữ liệu trung gian
│   └── processed/            # Dữ liệu đã xử lý/chuẩn hóa
├── src/
│   ├── hf_client/            # Module tương tác với Hugging Face Hub
│   ├── audit/                # Kiểm chứng dữ liệu & schema mapping
│   ├── terms/                # Extract/normalize/count/match terms
│   ├── llm/                  # LLM classification wrapper
│   ├── asr/                  # ASR runners (đang phát triển)
│   ├── reports/              # Markdown report generator (đang phát triển)
│   └── shared/               # Cấu hình chung, Logging, I/O
├── cli.py                    # Command Line Interface chính
├── outputs/
│   ├── audit/                # Kết quả audit dữ liệu
│   ├── term_coverage/        # Kết quả thống kê thuật ngữ
│   ├── asr_eval/             # Kết quả đánh giá ASR
│   └── reports/              # Báo cáo tiếng Việt tự động sinh
└── tests/                    # Thư mục kiểm thử tự động (pytest)
```

---

## 4. Cài đặt môi trường

Yêu cầu: Python 3.8+ và môi trường ảo (`.venv`).

```bash
# 1. Tạo môi trường ảo
python3 -m venv .venv

# 2. Kích hoạt môi trường ảo
source .venv/bin/activate        # Linux/macOS
# hoặc
.venv\Scripts\activate           # Windows

# 3. Cài dependencies
make install
```

---

## 5. Hướng dẫn sử dụng

### 5.1 Chạy toàn bộ pipeline (đã có sẵn)

```bash
make pipeline
```

Thứ tự thực hiện:
1. `make download` — Tải metadata từ Hugging Face
2. `make audit` — Kiểm chứng schema và thống kê
3. `make terms` — Trích xuất và chuẩn hóa CS terms
4. `make classify` — Phân loại term taxonomy bằng LLM
5. `make external` — So với external medical term inventory

### 5.2 Chạy từng bước

#### HF Metadata Acquisition
```bash
make download
# tương đương:
PYTHONPATH=. .venv/bin/python src/cli.py download-metadata
```

#### Metadata Audit
```bash
make audit
# tương đương:
PYTHONPATH=. .venv/bin/python src/cli.py audit-metadata
```

#### Term Extraction & Normalization
```bash
make terms
# tương đương:
PYTHONPATH=. .venv/bin/python src/cli.py extract-terms
```

#### LLM Classification
```bash
# Chạy thật (cần OPENAI_API_KEY trong .env)
make classify

# Chạy mock/smoke test không cần API
make classify-mock
# tương đương:
PYTHONPATH=. .venv/bin/python src/cli.py classify-terms --mock --limit 20
```

#### External Reference Matching
```bash
# Chạy thật (cần external inventory trong data/raw/external/)
make external

# Chạy mock/smoke test
make external-mock
# tương đương:
PYTHONPATH=. .venv/bin/python src/cli.py match-external --mock --limit 50
```

### 5.3 Kiểm thử và dọn dẹp

```bash
make test        # Chạy pytest
make clean       # Dọn cache, logs, và outputs
```

### 5.4 ASR Evaluation (đang phát triển)

```bash
make asr
# Lưu ý: Module ASR đang trong giai đoạn Phase 04.
# Khi hoàn thành sẽ hỗ trợ build manifest, chạy baseline, và tính WER/CER.
```

### 5.5 Report Generation (đang phát triển)

```bash
make report
# Lưu ý: Module tạo báo cáo tiếng Việt cuối cùng đang phát triển.
# Sẽ tổng hợp term coverage + ASR metrics thành final_report_vi.md.
```

---

## 6. CLI Reference

| Lệnh | Mô tả | Cờ |
|------|-------|-----|
| `download-metadata` | Tải metadata CSV từ Hugging Face | — |
| `audit-metadata` | Kiểm chứng schema và thống kê | — |
| `extract-terms` | Trích xuất và chuẩn hóa CS terms | — |
| `classify-terms` | Phân loại term taxonomy bằng LLM | `--mock`, `--limit N` |
| `match-external` | So với external medical term inventory | `--mock`, `--limit N` |

Tất cả lệnh đều chạy qua `PYTHONPATH=. .venv/bin/python src/cli.py <command>`.

---

## 7. Output Files

### 7.1 Audit outputs (`outputs/audit/`)

| File | Nội dung |
|------|----------|
| `hf_file_manifest.json` | Danh sách file HF, size, path, revision, timestamp |
| `metadata_schema_report.md` | Báo cáo schema mapping và khác biệt |
| `local_dataset_stats.json` | Tổng dòng, split count, duration, missing fields |
| `split_stats.csv` | Thống kê theo split |
| `topic_stats.csv` | Thống kê theo topic |
| `duration_stats.csv` | Phân bố thời lượng |
| `data_quality_issues.csv` | Các vấn đề phát hiện (thiếu trường, trùng lặp...) |

### 7.2 Term coverage outputs (`outputs/term_coverage/`)

| File | Nội dung |
|------|----------|
| `cs_terms_inventory.csv` | Unique CS terms, frequency, split, topic, examples |
| `cs_terms_by_domain.csv` | Phân nhóm theo medical domain |
| `cs_terms_by_entity_category.csv` | Phân nhóm theo entity type |
| `cs_term_examples.jsonl` | Ví dụ câu chứa từng term |
| `common_terms.csv` | Terms có tần suất >= 20 |
| `rare_terms.csv` | Terms có tần suất < 5 |
| `hard_only_terms.csv` | Terms chỉ xuất hiện ở hard split |
| `cs_terms_classified.csv` | Term domain/entity/confidence/review flag |
| `llm_classification_audit.jsonl` | Audit log cho từng lần classify |
| `term_taxonomy_summary.md` | Tóm tắt phân loại taxonomy |
| `external_sources_registry.csv` | Metadata nguồn external (pilot) |
| `external_medical_term_inventory.csv` | Bản sao external inventory |
| `vimedcss_vs_external_coverage.csv` | Bảng coverage ratio theo category/domain |
| `external_coverage_summary.md` | Tóm tắt coverage bằng tiếng Việt |

### 7.3 ASR evaluation outputs (`outputs/asr_eval/`)

| File | Nội dung |
|------|----------|
| `asr_manifest.jsonl` | Audio segment, transcript, CS terms, domain, entity |
| `asr_predictions.jsonl` | Output ASR model cho từng segment |
| `asr_metrics_by_domain.csv` | WER, CER, CS recall theo domain/entity/split |
| `error_examples.jsonl` | Ví dụ lỗi ASR điển hình |
| `top_failed_terms.csv` | Terms bị nhận sai nhiều nhất |
| `error_type_summary.csv` | Tổng hợp loại lỗi |

### 7.4 Report outputs (`outputs/reports/`)

| File | Nội dung |
|------|----------|
| `final_report_vi.md` | Báo cáo tiếng Việt tổng hợp với số liệu, ví dụ, giới hạn, kết luận |

---

## 8. Nguyên tắc bắt buộc

Pipeline phục vụ nghiên cứu, do đó ưu tiên **tính đúng, truy vết được nguồn, và không bịa số liệu**.

1. **Không tự tạo số liệu.** Mọi con số trong report phải lấy từ metadata local, audio đã kiểm chứng, kết quả ASR/evaluation script thực tế, paper/dataset card có URL nguồn, hoặc output LLM có lưu đầy đủ input/prompt version/model/timestamp/confidence/review status.
2. **Tách rõ nguồn số liệu.** Phân biệt rõ `paper_reported`, `hf_reported`, `local_verified`, `llm_inferred`. Không trộn các nhóm này thành kết luận chắc chắn nếu chưa kiểm chứng.
3. **Không coi output LLM là ground truth.** LLM chỉ hỗ trợ phân loại term/domain/entity. Kết quả phải có confidence, evidence, và flag `needs_human_review`.
4. **Mọi pipeline phải chạy được ở chế độ subset/smoke test** trước khi chạy full dataset.
5. **Mọi artifact quan trọng phải lưu thành file.** Không chỉ in ra terminal.
6. **Report cuối phải là tiếng Việt.** Thuật ngữ kỹ thuật giữ tiếng Anh nhưng phải giải thích rõ.

---

## 9. Lưu ý phát triển

- Hiện tại các lệnh `download`, `audit`, `terms`, `classify`, `external` đã sẵn sàng sử dụng.
- ASR evaluation và báo cáo tổng hợp đang trong giai đoạn hoàn thiện (Phase 04 và Phase 05 theo roadmap).
- Tất cả path đều được cấu hình qua `configs/*.yaml`, không hard-code đường dẫn tuyệt đối.
- Sử dụng `--mock` để smoke test không cần API key hoặc external inventory thật.
