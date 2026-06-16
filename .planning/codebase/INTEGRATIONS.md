# External Integrations

**Analysis Date:** 2026-06-16

## APIs & External Services

**Hugging Face Hub API:**
- Nguồn tải dữ liệu metadata CSV và tệp âm thanh (audio files).
  - SDK/Client: `huggingface_hub` (sử dụng `HfApi` và `hf_hub_download`).
  - Auth: Không bắt buộc token đối với tập dữ liệu công khai `tensorxt/ViMedCSS`.
  - Endpoint sử dụng: Danh sách tệp tin trong repo, tải metadata CSV và tải audio files.

**OpenAI API:**
- Phân loại thuật ngữ y khoa (medical terms classification) theo phân loại y khoa và chuyên khoa.
  - SDK/Client: `openai` (với model `gpt-5-mini` theo cấu hình mặc định).
  - Auth: Khóa API được cung cấp qua biến môi trường `OPENAI_API_KEY`.
  - Tích hợp: Trực tiếp qua REST API (sử dụng Structured Output JSON).

## Data Storage

**Dữ liệu cục bộ (Local Storage):**
- **Đường dẫn dữ liệu gốc:** `data/raw/vimedcss/` (bao gồm cả thư mục con `ViMedCSS-Metadata/` chứa 4 file CSV: `train_set.csv`, `valid_set.csv`, `test_set.csv`, `hard_set.csv`).
- **Đường dẫn trung gian:** `data/interim/` (chứa các manifest và dữ liệu chuẩn bị).
- **Đường dẫn đã xử lý:** `data/processed/` (dữ liệu sạch và chuẩn hóa).
- **Đường dẫn xuất kết quả (Outputs):**
  - `outputs/audit/` (kết quả audit schema, manifest, lỗi chất lượng dữ liệu).
  - `outputs/term_coverage/` (phân loại, thống kê độ bao phủ thuật ngữ y tế).
  - `outputs/asr_eval/` (file phiên âm và kết quả đánh giá ASR baseline).
  - `outputs/reports/` (báo cáo phân tích tiếng Việt tự động).

## Monitoring & Observability

**Hệ thống Logs cục bộ:**
- Sử dụng module logging Python (`logging`) được thiết lập tại `src/shared/logging.py`.
- Xuất log ra console và đồng thời ghi nhận quá trình download trong `outputs/audit/download_log.jsonl`.
- LLM input/output thô được lưu vết tại `outputs/term_coverage/llm_classification_audit.jsonl` (khi cấu hình `save_raw_io: true`).

## CI/CD & Deployment

- **Pipeline chạy cục bộ:** Không sử dụng nền tảng hosting bên ngoài. Pipeline được chạy hoàn toàn trên máy local/server thông qua CLI và `Makefile`.
- **CI/CD:** Không cấu hình GitHub Actions hay CI/CD tự động trong repo hiện tại. Các bài kiểm thử đơn vị được thực thi thủ công qua lệnh `make test`.

## Environment Configuration

- **Biến môi trường cần thiết:**
  - `OPENAI_API_KEY` - Khóa bí mật kết nối OpenAI API để thực hiện phân loại thuật ngữ bằng LLM.
- **Vị trí lưu trữ cấu hình:** `configs/`
  - `dataset.yaml` (Hugging Face repo details & schema mapping)
  - `taxonomy.yaml` (Frequency buckets & threshold rules)
  - `llm.yaml` (LLM parameters & batch options)
  - `asr.yaml` (ASR configurations & normalization switches)
  - `report.yaml` (Language & formatting options)

## Webhooks & Callbacks

- Không có (no incoming or outgoing webhooks).

---

*Integration audit: 2026-06-16*
*Update when adding/removing external services*
