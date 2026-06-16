# Pitfalls Research

**Domain:** ViMedCSS Term Coverage & ASR Code-Switching Evaluation Pipeline
**Researched:** 2026-06-16
**Confidence:** HIGH

## Critical Pitfalls

### Pitfall 1: Quá chuẩn hóa (Over-normalization) làm mất thuật ngữ y tế

**What goes wrong:**
Việc đưa văn bản kết quả ASR và văn bản gốc về dạng chuẩn thông thường (lowercase, xóa dấu câu, chuyển số thành chữ) có thể làm biến dạng hoàn toàn các thuật ngữ y học viết tắt (ví dụ: `HbA1c` thành `hba1c` hoặc tách rời thành `h b a 1 c`, `T3` thành `t 3`).

**Why it happens:**
Các bộ chuẩn hóa ASR thông thường (như Whispers normalizer) không được cấu hình riêng để bảo vệ các cụm từ viết tắt y tế và code-switching terms.

**How to avoid:**
Tách riêng logic chuẩn hóa thông thường và chuẩn hóa bảo vệ thuật ngữ (keep medical abbreviations & numbers/units). Giữ nguyên trạng cả cột `raw_term` và `normalized_term`.

**Warning signs:**
CS-Term Exact Recall bằng 0% mặc dù văn bản nhận diện nghe rất sát.

**Phase to address:**
Phase 2: CS term extraction & normalization.

---

### Pitfall 2: Bịa số liệu hoặc coi LLM Classifier là Ground Truth tuyệt đối

**What goes wrong:**
Sử dụng LLM để phân loại entity category/domain và trực tiếp đưa vào thống kê báo cáo mà không có cơ chế đánh dấu độ tin cậy thấp, dẫn đến số liệu y khoa bị sai lệch hoặc không trung thực.

**Why it happens:**
LLM có thể phân loại sai các thuật ngữ viết tắt hiếm hoặc context mơ hồ (ví dụ: `T3` có thể là hormone tuyến giáp hoặc phân loại giai đoạn ung thư).

**How to avoid:**
Đưa trường `confidence` và `needs_human_review` vào output JSON của LLM. Bất kỳ term nào có confidence < `confidence_threshold_review` (ví dụ: 0.80) sẽ bị gán nhãn flag review.

**Warning signs:**
Nhầm lẫn domain nghiêm trọng (ví dụ: thuốc tim mạch phân vào domain dạ dày) nhưng report vẫn báo độ chính xác 100%.

**Phase to address:**
Phase 3: Term taxonomy & LLM classification.

---

### Pitfall 3: Tắc nghẽn bộ nhớ/CPU khi chạy ASR trên tập dữ liệu lớn

**What goes wrong:**
Chạy ASR baseline trực tiếp trên toàn bộ 32 tiếng âm thanh mà không chạy smoke test thử trước, gây tràn RAM (OOM) hoặc chạy mất nhiều ngày trên CPU.

**Why it happens:**
Hệ thống tải toàn bộ dữ liệu âm thanh vào RAM cùng lúc, hoặc sử dụng model Whisper kích thước quá lớn (large-v3) trên thiết bị không có GPU hỗ trợ tăng tốc CUDA.

**How to avoid:**
1. Cung cấp flag `run_mode: sample_first` để chạy thử nghiệm subset nhỏ (như 100 files).
2. Sử dụng `faster-whisper` thay thế cho thư viện `transformers` gốc để tối ưu hóa tốc độ và bộ nhớ.
3. Cho phép cấu hình size model (tiny, base, large-v3) linh hoạt tùy cấu hình phần cứng.

**Warning signs:**
Hệ thống treo cứng không log ra terminal, hoặc logs bị ngắt đột ngột do tiến trình bị KILL (Out of memory).

**Phase to address:**
Phase 5: Audio verification & ASR manifest.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Regex trích xuất term cứng thay vì JSON parse | Code nhanh trong 10 phút. | Lỗi khi gặp format danh sách phức tạp hoặc ký tự lạ. | Chỉ dùng làm bước tiền xử lý lọc sơ bộ ban đầu. |
| Bỏ qua audio check (chỉ check file tồn tại) | Tiết kiệm vài phút khởi chạy. | Chạy ASR bị lỗi crash nửa chừng do file âm thanh bị lỗi hoặc rỗng. | Không nên, cần kiểm chứng định dạng file wav/mp3 trước khi chạy baseline. |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Hugging Face LFS | Chỉ tải file metadata.csv mà không cài LFS để kéo file audio lớn. | Sử dụng `huggingface_hub` API tải từng file cụ thể theo nhu cầu, tránh `git clone` toàn bộ repo LFS nếu mạng yếu. |
| OpenAI API Key | Hard-code API key vào code hoặc YAML. | Nạp qua biến môi trường `OPENAI_API_KEY` và log cảnh báo nếu thiếu. |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Đồng bộ hóa API calls cho từng term | Chạy phân loại 8xx terms mất 30 phút. | Sử dụng batching (ví dụ: 50 terms/batch) để gom nhóm gọi LLM. | Khi số lượng term > 100. |

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| API OpenAI bị rate limit | LOW | Thêm cơ chế exponential backoff retry (max_retries = 3). |
| File audio tải về bị hỏng | MEDIUM | Xóa file cục bộ bị lỗi, chạy lại download client để trigger download/checksum lại. |

---
*Pitfalls research for: ViMedCSS Evaluation*
*Researched: 2026-06-16*
