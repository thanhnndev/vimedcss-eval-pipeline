# ViMedCSS Term Coverage & ASR Code-Switching Evaluation Pipeline

Pipeline đánh giá mức độ bao phủ của thuật ngữ y tế (Term Coverage) và hiệu năng ASR trên tập dữ liệu trộn mã Anh/Việt (Code-Switching) `tensorxt/ViMedCSS` từ Hugging Face.

---

## 1. Kiến trúc thư mục

Thư mục dự án được tổ chức gọn gàng và phân chia rõ ràng theo đặc tả:

```text
vimedcss-eval-pipeline/
├── README.md
├── Makefile
├── configs/                  # File cấu hình YAML
│   ├── dataset.yaml          # Config dataset (repo, splits, expected fields)
│   ├── taxonomy.yaml         # Phân nhóm tần suất thuật ngữ
│   ├── llm.yaml              # Cấu hình LLM Classifier
│   ├── asr.yaml              # Cấu hình ASR Baseline
│   └── report.yaml           # Cấu hình báo cáo
├── data/
│   ├── raw/                  # Dữ liệu gốc tải về từ HF (đã ignore)
│   ├── interim/              # Dữ liệu trung gian
│   └── processed/            # Dữ liệu đã xử lý/chuẩn hóa
├── src/
│   ├── hf_client/            # Module tương tác với Hugging Face Hub
│   ├── audit/                # Kiểm chứng dữ liệu & schema mapping
│   ├── shared/               # Cấu hình chung, Logging, I/O
│   └── cli.py                # Command Line Interface chính của dự án
├── outputs/
│   ├── audit/                # Kết quả audit dữ liệu (manifest, stats, issues)
│   ├── term_coverage/        # Kết quả thống kê thuật ngữ (Phase 2, 3, 4)
│   ├── asr_eval/             # Kết quả đánh giá ASR (Phase 5, 6)
│   └── reports/              # Báo cáo tiếng Việt tự động sinh ra
└── tests/                    # Thư mục kiểm thử tự động (pytest)
```

---

## 2. Hướng dẫn cài đặt

Dự án yêu cầu Python 3.8+ và sử dụng môi trường ảo (`.venv`).

1. Khởi tạo môi trường ảo Python:
   ```bash
   python3 -m venv .venv
   ```

2. Cài đặt các thư viện cần thiết:
   ```bash
   make install
   ```

---

## 3. Hướng dẫn sử dụng

Hệ thống cung cấp `Makefile` để tự động hóa các thao tác chính:

- **Tải Metadata từ Hugging Face**:
  Tải các tệp metadata CSV thuộc tập dữ liệu `tensorxt/ViMedCSS` về thư mục cục bộ `data/raw/vimedcss/` và ghi nhận manifest.
  ```bash
  make download
  ```

- **Kiểm chứng dữ liệu & Schema Audit**:
  Kiểm tra khớp cột, lập báo cáo schema mapping, thống kê thời lượng/dòng, và phát hiện các vấn đề trùng lặp ID hay thiếu trường dữ liệu.
  ```bash
  make audit
  ```

- **Chạy kiểm thử tự động**:
  Thực hiện chạy toàn bộ unit tests để kiểm tra độ tin cậy của các class/module.
  ```bash
  make test
  ```

- **Dọn dẹp cache và output**:
  ```bash
  make clean
  ```

---

## 4. Kết quả Kiểm chứng Metadata cục bộ (Local Verification)

- **Tổng số dòng dữ liệu**: 15,818 dòng.
- **Tổng thời lượng**: 32.64 giờ (117,516 giây).
- **Trùng lặp segment_id**: Phát hiện 4 dòng bị trùng lặp chéo giữa tập train, validation và test (Chi tiết lưu tại `outputs/audit/data_quality_issues.csv`).
- **Khác biệt Schema**: Tệp `test_set.csv` sử dụng tên trường `Topic` (viết hoa chữ T), hệ thống tự động ánh xạ thành công qua cơ chế so khớp không phân biệt chữ hoa/thường.
- **Chi tiết báo cáo Schema**: Xem tại [metadata_schema_report.md](outputs/audit/metadata_schema_report.md).
