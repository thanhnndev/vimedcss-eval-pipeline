# Feature Research

**Domain:** ViMedCSS Term Coverage & ASR Code-Switching Evaluation Pipeline
**Researched:** 2026-06-16
**Confidence:** HIGH

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| HF Acquisition (metadata-only) | Tải nhanh danh sách files và chỉ tải metadata CSVs trước để phân tích. | LOW | Sử dụng `huggingface_hub`. |
| Schema Normalization | Ánh xạ tên cột chênh lệch giữa các split (ví dụ: `Topic` vs `topic`, `duration` vs `duration_seconds`) sang schema chung. | LOW | Thực hiện trong module `audit`. |
| CS Term Extraction | Trích xuất chính xác danh sách các medical term trộn mã từ trường `cs_terms_list`. | MEDIUM | Cần xử lý dạng JSON list hoặc string list phân cách bởi dấu phẩy. |
| Basic ASR Evaluation | Chạy ASR baseline (như Whisper) trên sample hoặc split và tính tổng thể WER, CER. | MEDIUM | Dùng `jiwer` kết hợp `faster-whisper`. |
| Vietnamese Markdown Report | Xuất báo cáo kết quả đánh giá bằng tiếng Việt có cấu trúc chặt chẽ và số liệu cụ thể. | LOW | Đảm bảo tính minh bạch, tách rõ số liệu local verified. |

### Differentiators (Competitive Advantage)

Features that set the product apart. Not required, but valuable.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| LLM Term Classification | Tự động phân loại 8xx unique code-switching term thành các nhóm y khoa và chuyên khoa y tế. | HIGH | Sử dụng OpenAI Structured Output với Pydantic schema validation. |
| External Inventory Comparison | So khớp mức độ bao phủ của ViMedCSS với từ điển y học bên ngoài (như Meddict, ATC, ICD-10). | MEDIUM | Giúp xác định mức độ bao phủ của tập dữ liệu đối với các thuật ngữ y học thông dụng. |
| Detailed CS Error Taxonomy | Phân loại các lỗi nhận dạng ASR đối với các term tiếng Anh (ví dụ: mất từ, Việt hóa phiên âm, nhầm chính tả). | HIGH | Giúp hiểu rõ điểm yếu của model đối với code-switching. |
| Subset/Smoke Test Mode | Cho phép chạy thử nghiệm nhanh toàn bộ pipeline trên một tập subset nhỏ (như 100 câu) để tiết kiệm thời gian/chi phí. | LOW | Hỗ trợ cấu hình `run_mode: sample_first` trong yaml. |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Model Fine-tuning | Người dùng muốn tiện tay fine-tune ASR model trong pipeline luôn. | Tăng cực kỳ nhiều độ phức tạp, tốn tài nguyên GPU lớn và làm loãng mục tiêu chính là "Đánh giá & Phân tích". | Độc lập hóa bước fine-tune, chỉ nạp model checkpoint vào pipeline để chạy evaluation. |
| Automatic Medical Spelling Correction | Tự động sửa lỗi chính tả trong metadata gốc. | Làm mất tính trung thực của dữ liệu gốc, gây sai lệch báo cáo chất lượng dữ liệu (data quality issues). | Chỉ ghi nhận lỗi vào `data_quality_issues.csv` và giữ nguyên trạng dữ liệu gốc. |

## Feature Dependencies

```
[Metadata Normalization] ──requires──> [HF Acquisition]
[CS Term Extraction] ──requires──> [Metadata Normalization]
[LLM Term Classification] ──requires──> [CS Term Extraction]
[External Coverage Analysis] ──requires──> [LLM Term Classification]
[ASR Evaluation baseline] ──requires──> [HF Acquisition (Full Audio)]
[ASR CS Error Analysis] ──requires──> [ASR Evaluation baseline] & [LLM Term Classification]
[Vietnamese Report Generation] ──requires──> [External Coverage Analysis] & [ASR CS Error Analysis]
```

### Dependency Notes

- **ASR CS Error Analysis requires LLM Term Classification:** Cần phân loại được taxonomy của term trước thì mới phân tích được lỗi ASR theo từng nhóm chuyên khoa và danh mục y tế.
- **Vietnamese Report Generation requires ASR CS Error Analysis:** Báo cáo tổng hợp cần tích hợp kết quả phân tích lỗi để trả lời các câu hỏi nghiên cứu cốt lõi.

## MVP Definition

### Launch With (v1)

Minimum viable product — what's needed to validate the concept.

- [x] HF Metadata Download & File Manifest — essential for tracking repo revisions.
- [x] Local Metadata Schema Audit & Data Quality Reporting — essential for data validation.
- [ ] CS Term Extraction & Normalization — essential to obtain unique term inventory.
- [ ] LLM Term Classification (Entity & Domain) — essential for taxonomic evaluation.
- [ ] External Lexicon Integration & Coverage Match — essential for finding dataset coverage gaps.
- [ ] ASR Evaluation on Test/Hard Splits (WER/CER/CS Term Recall) — essential for identifying baseline limits.
- [ ] Detailed ASR Error Taxonomy (phonetic, missing, spelling errors) — essential for researching ASR weaknesses.
- [ ] Final Vietnamese Markdown Report — essential to deliver results to researchers.

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| HF Metadata Audit | HIGH | LOW | P1 |
| CS Term Normalization | HIGH | MEDIUM | P1 |
| LLM Term Classification | HIGH | HIGH | P1 |
| External Inventory match | HIGH | MEDIUM | P1 |
| ASR baseline run & WER | HIGH | MEDIUM | P1 |
| CS term error analysis | HIGH | HIGH | P1 |
| Vietnamese report generator | HIGH | LOW | P1 |

## Sources

- ViMedCSS Paper (arXiv:2602.12911)
- Coding Agent Requirements ViMedCSS Evaluation Pipeline v2.0

---
*Feature research for: ViMedCSS Evaluation*
*Researched: 2026-06-16*
