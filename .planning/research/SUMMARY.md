# Project Research Summary

**Project:** ViMedCSS Term Coverage & ASR Code-Switching Evaluation Pipeline
**Domain:** Medical Code-Switching ASR & Corpus Evaluation
**Researched:** 2026-06-16
**Confidence:** HIGH

## Executive Summary

Tài liệu này tóm tắt kết quả nghiên cứu hệ sinh thái công nghệ, cấu trúc và điểm cần lưu ý khi xây dựng Pipeline đánh giá Term Coverage và điểm yếu ASR trên dataset `tensorxt/ViMedCSS`. Tập dữ liệu chứa khoảng 34 giờ nói trộn tiếng Anh/Việt với hơn 8xx distinct medical terms.

Để đảm bảo tính chính xác cho nghiên cứu, pipeline sẽ chia thành 2 phần lớn: phần phân tích độ bao phủ thuật ngữ (Metadata & Term Analysis) và phần đánh giá baseline nhận dạng tiếng nói (ASR baseline evaluation). Chúng tôi khuyến nghị sử dụng Python 3.10+ kết hợp `faster-whisper` để tăng tốc độ nhận dạng và `OpenAI API (Structured Output)` cho bài toán phân loại taxonomy y học tự động.

Các rủi ro chính bao gồm việc chuẩn hóa quá tay làm hỏng chính tả của thuật ngữ y tế viết tắt và việc tràn bộ nhớ khi chạy ASR trên tập dữ liệu lớn. Các biện pháp giảm thiểu (giữ nguyên cột raw_term, hỗ trợ chạy sample_first) đã được thiết kế sẵn.

## Key Findings

### Recommended Stack

Hệ thống được đề xuất xây dựng bằng Python với các thư viện:
- **faster-whisper**: Chạy baseline Whisper hiệu năng cao trên CUDA/CPU.
- **OpenAI Structured Outputs**: Trả về dữ liệu phân loại dưới dạng JSON khớp chính xác với Pydantic schema của hệ thống.
- **jiwer & pandas**: Tính toán metrics (WER, CER, CS-recall) và quản lý dữ liệu bảng.

### Expected Features

**Must have (table stakes):**
- Tải metadata và ghi file manifest của HF Hub.
- Trích xuất và chuẩn hóa term từ `cs_terms_list`.
- Chạy Whisper ASR baseline và tính WER/CER tổng thể.
- Xuất báo cáo tiếng Việt tự động.

**Should have (differentiators):**
- Sử dụng LLM phân loại Entity Category (drug, disease, biomarker, etc.) và Medical Domain (cardiology, endocrinology, etc.).
- So sánh mức độ bao phủ với các từ điển y học bên ngoài (như ICD-10, ATC, Meddict).
- Phân tích chi tiết các loại lỗi ASR trên code-switching terms (phonetic, spelling, missing).
- Cấu hình subset/smoke test mode (`sample_first`) cho ASR.

### Architecture Approach

Hệ thống được thiết kế theo dạng Module hóa tuyến tính:
1. **Module Acquisition (`hf_client/download.py`)**: Tải dữ liệu thô.
2. **Module Audit (`audit/auditor.py`)**: Kiểm chứng và map schema.
3. **Module Terms (`terms/extractor.py` & `terms/external.py`)**: Trích xuất, chuẩn hóa term và so khớp external lexicons.
4. **Module LLM (`llm/classifier.py`)**: Gọi API phân loại taxonomy.
5. **Module ASR & Metrics (`asr/engine.py` & `metrics/evaluator.py`)**: Chạy baseline và tính metrics.
6. **Module Report (`reports/generator.py`)**: Gom số liệu sinh báo cáo.

### Critical Pitfalls

1. **Chuẩn hóa quá tay làm mất chính tả y tế** — Cần giữ nguyên trạng cột `raw_term` song song với `normalized_term`.
2. **Tràn bộ nhớ / Chạy ASR quá lâu trên CPU** — Sử dụng `faster-whisper` và cung cấp cấu hình `run_mode: sample_first` chạy thử subset 100 dòng.
3. **Lấy output LLM làm ground truth** — Bắt buộc trả về confidence từ LLM và đánh dấu flag `needs_human_review = true` nếu confidence thấp hơn 0.80.

## Implications for Roadmap

Dựa trên nghiên cứu, cơ cấu roadmap khuyến nghị chia thành các phase:

### Phase 1: CS Term Extraction & Normalization
**Rationale:** Cần trích xuất được danh sách unique terms thô và normalized forms từ metadata local đã tải để làm đầu vào cho toàn bộ các phân tích sau đó.
**Delivers:** `cs_terms_inventory.csv`, `cs_term_examples.jsonl`, `cs_terms_normalized.csv`.
**Avoids:** Trùng lặp thuật ngữ hoặc chuẩn hóa sai làm hỏng chính tả viết tắt.

### Phase 2: Term Taxonomy & LLM Classification
**Rationale:** Phân loại các terms thu được sang các entity categories và medical domains bằng LLM để phục vụ cho cả báo cáo coverage y học lẫn báo cáo lỗi ASR theo nhóm sau này.
**Delivers:** `cs_terms_by_entity_category.csv`, `cs_terms_by_domain.csv`, `llm_classification_audit.jsonl`.
**Uses:** OpenAI Structured outputs với Pydantic schema validation.

### Phase 3: External Medical Term Inventory Comparison
**Rationale:** Đối chiếu mức độ bao phủ thuật ngữ của ViMedCSS với các nguồn tham chiếu ngoài để tìm lỗ hổng dữ liệu trước khi đi vào phần âm thanh.
**Delivers:** `external_medical_term_inventory.csv`, `vimedcss_vs_external_coverage.csv`.
**Implements:** So khớp so sánh tỷ lệ bao phủ theo phân nhóm y khoa.

### Phase 4: ASR Baseline Evaluation & Error Analysis
**Rationale:** Tải âm thanh, chạy Whisper baseline và tính toán metrics chi tiết trên test/hard splits, phân tích các điểm yếu ASR đối với code-switching term.
**Delivers:** ASR Hypothesis transcripts, `eval_manifest_<split>.jsonl`, WER/CER metrics và `top_failed_terms.csv`.

### Phase 5: Vietnamese Report Generation
**Rationale:** Tổng hợp tất cả các số liệu verified thu được từ Phase 1-4 để sinh ra báo cáo markdown tiếng Việt hoàn chỉnh.
**Delivers:** `report_vi_vimedcss_term_coverage_and_asr_weakness.md`.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Python, pandas, faster-whisper, jiwer đều rất ổn định và thông dụng. |
| Features | HIGH | Các tính năng trích xuất và phân tích lỗi bám sát yêu cầu nghiên cứu. |
| Architecture | HIGH | Cấu trúc phân chia CLI và các package con đã được xác minh trên các dự án tương tự. |
| Pitfalls | HIGH | Đã lường trước các vấn đề về memory, over-normalization và LLM safety. |

**Overall confidence:** HIGH

### Gaps to Address

- **Khác biệt schema audio**: Cột start/end trong metadata gốc có định dạng chuỗi `MM:SS` thay vì số giây, cần xử lý parser thời gian trong ASR runner.
- **API Key & Cost**: LLM calls cần thực hiện gom batch để hạn chế chi phí gọi API.

## Sources

- ViMedCSS Paper (arXiv:2602.12911)
- OpenAI API Guides — Structured Outputs
- faster-whisper project page

---
*Research completed: 2026-06-16*
*Ready for roadmap: yes*
