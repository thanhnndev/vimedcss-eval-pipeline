# Architecture Research

**Domain:** ViMedCSS Term Coverage & ASR Code-Switching Evaluation Pipeline
**Researched:** 2026-06-16
**Confidence:** HIGH

## Standard Architecture

### System Overview

```
 ┌─────────────────────────────────────────────────────────────┐
 │                         Ingestion                           │
 ├─────────────────────────────────────────────────────────────┤
 │    ┌──────────────┐             ┌────────────────┐          │
 │    │  HF Client   │ ──────────> │   Raw Data     │          │
 │    │ (download.py)│             │ (CSVs, Audios) │          │
 │    └──────────────┘             └───────┬────────┘          │
 └─────────────────────────────────────────┼───────────────────┘
                                           │
 ┌─────────────────────────────────────────▼───────────────────┐
 │                      Analysis Pipeline                      │
 ├─────────────────────────────────────────────────────────────┤
 │  ┌────────────────┐       ┌────────────────┐                │
 │  │ Auditor        │       │ Terms Extractor│                │
 │  │ (auditor.py)   │       │ & Normalizer   │                │
 │  └───────┬────────┘       └────────┬───────┘                │
 │          │                         │                        │
 │          ▼                         ▼                        │
 │  ┌────────────────┐       ┌────────────────┐                │
 │  │  Audit reports │       │ LLM Classifier │                │
 │  │  (Schema, Stats│       │ (llm/gpt_mini) │                │
 │  │  Quality issues│       └────────┬───────┘                │
 │  └────────────────┘                │                        │
 │                                    ▼                        │
 │                           ┌────────────────┐                │
 │                           │ Taxonomy Tables│                │
 │                           │ (Entity,Domain)│                │
 │                           └────────┬───────┘                │
 └────────────────────────────────────┼────────────────────────┘
                                      │
 ┌────────────────────────────────────┼────────────────────────┐
 │                    Evaluation & Reporting                   │
 ├────────────────────────────────────┼────────────────────────┤
 │                                    │  ┌──────────────────┐  │
 │  ┌────────────────┐                │  │ faster-whisper   │  │
 │  │ ASR Runner     │ <──────────────┘  │ (local/cuda)     │  │
 │  │ (asr_engine.py)│ <──────────────── │ ASR Engine       │  │
 │  └───────┬────────┘                   └──────────────────┘  │
 │          │                                                  │
 │          ▼                                                  │
 │  ┌────────────────┐                                         │
 │  │ Metrics Engine │                                         │
 │  │ (WER/CER/CS)   │                                         │
 │  └───────┬────────┘                                         │
 │          │                                                  │
 │          ▼                                                  │
 │  ┌────────────────┐                                         │
 │  │ Report Gen     │ ──────────> report_vi_vimedcss_...md    │
 │  │ (markdown reports)                                       │
 │  └────────────────┘                                         │
 └─────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| `hf_client` | Tải metadata và tệp tin audio từ HF Hub, theo dõi revision và lưu manifest. | `huggingface_hub` Python client. |
| `audit` | Ánh xạ cấu trúc CSV, tính toán stats phân phối, phát hiện lỗi dữ liệu. | `pandas`, `numpy` dùng để thống kê. |
| `terms` | Trích xuất terms thô, chuẩn hóa về chữ thường, đếm tần suất theo splits. | Python regex, JSON parser, custom rules. |
| `llm` | Gọi OpenAI API với structured schema để gán nhãn entity category và medical domain cho từng term. | `openai` client với Pydantic response format. |
| `asr` | Tải âm thanh thực tế, chạy Whisper baseline và xuất văn bản dự đoán. | `faster-whisper` sử dụng CUDA/CPU. |
| `metrics` | So khớp hypothesis và reference, tính WER, CER, CS-term recall và breakdown lỗi. | `jiwer` kết hợp thuật toán so khớp token. |
| `reports` | Tổng hợp số liệu từ audit, term và asr_eval để sinh các file Markdown báo cáo tiếng Việt. | Python Markdown template renderer. |

## Recommended Project Structure

```
src/
├── hf_client/          # Tải dữ liệu và quản lý manifest
│   ├── __init__.py
│   └── download.py     # HfHub Client download metadata & audio
├── audit/              # Kiểm chứng dữ liệu & schema mapping
│   ├── __init__.py
│   └── auditor.py      # Metadata Auditor
├── terms/              # Trích xuất và chuẩn hóa CS terms
│   ├── __init__.py
│   ├── extractor.py    # CS term parsing & normalization
│   └── external.py     # External inventory manager
├── llm/                # Giao tiếp LLM để phân loại taxonomy
│   ├── __init__.py
│   ├── classifier.py   # OpenAI structured taxonomy classification
│   └── prompts.py      # System and user prompts definition
├── asr/                # Chạy ASR Baselines
│   ├── __init__.py
│   └── engine.py       # faster-whisper runner
├── metrics/            # Tính toán WER, CER, CS-term metrics
│   ├── __init__.py
│   └── evaluator.py    # Metric computations & error parser
├── reports/            # Sinh báo cáo Markdown tiếng Việt
│   ├── __init__.py
│   └── generator.py    # Report aggregator & writer
├── shared/             # Cấu hình chung, Logging, I/O
│   ├── config.py       # YAML config loaders
│   └── logging.py      # Custom logger wrapper
└── cli.py              # Điểm chạy CLI chính của dự án (Makefile target)
```

### Structure Rationale

- **src/terms/**: Tách biệt logic chuẩn hóa và trích xuất để dễ dàng viết các bài kiểm thử unit test (`tests/test_term_normalization.py`).
- **src/llm/**: Module hóa LLM để tránh trộn lẫn logic prompt và logic gọi API, đồng thời giúp dễ thay thế model bằng config YAML.
- **src/asr/**: Đóng gói execution của model Whisper để kiểm soát độc lập việc load CUDA/CPU và quản lý bộ nhớ GPU.

## Architectural Patterns

### Pattern 1: Configuration-driven Schema Mapping

**What:** Ánh xạ các tên cột khác biệt trong CSV qua file config YAML thay vì viết code cứng.
**When to use:** Khi các split CSV của dataset trên Hugging Face có tên trường khác nhau (ví dụ: `Topic` viết hoa chữ T ở Test set, hoặc `duration_seconds` vs `duration`).
**Trade-offs:** Tăng tính linh hoạt nhưng cần viết code kiểm tra mapping hợp lệ lúc runtime.

### Pattern 2: Structured LLM Output with Schema Validation

**What:** Sử dụng tính năng Structured Outputs của OpenAI API (nhận response trực tiếp khớp với Pydantic model) để phân loại taxonomy.
**When to use:** Tránh lỗi LLM trả về chuỗi JSON lỗi cấu trúc hoặc thiếu trường dữ liệu y khoa bắt buộc.
**Trade-offs:** Tốc độ gọi API có thể chậm hơn một chút khi validate schema, nhưng loại bỏ hoàn toàn lỗi parsing.

## Data Flow

### Request Flow

```
[CLI Command: audit/classify/eval]
    ↓
[cli.py] → [Config Loader] → [Module Runner (Auditor/Classifier/Evaluator)]
    ↓                                              ↓
[Console Log / Error Output] <─────────── [Save Output to CSV/JSON/MD]
```

### Key Data Flows

1. **Flow Phân loại Taxonomy:**
   `Raw CSVs` -> `CS Term Extractor` -> `Unique Inventory CSV` -> `LLM Classifier` -> `Taxonomy Tables (CSVs)` + `llm_classification_audit.jsonl` (Audit log).
2. **Flow Đánh giá ASR:**
   `Audio & Metadata` -> `ASR Engine (transcribe)` -> `ASR hypothesis output` -> `Metrics evaluator` -> `WER/CER & CS Metric CSVs` -> `Report generator`.

---
*Architecture research for: ViMedCSS Evaluation*
*Researched: 2026-06-16*
