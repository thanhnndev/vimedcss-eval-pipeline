# Nhận dạng tiếng nói y tế — 3 vấn đề

> **Điểm yếu nhận dạng · Chuyển mã Anh–Việt · Độ phủ dữ liệu công khai**

> 🧭 **Phạm vi.** Báo cáo ngắn, tách bạch **3 vấn đề độc lập**: (1) điểm yếu của nhận dạng tiếng nói; (2) chuyển mã (xen lẫn) ngôn ngữ Anh–Việt; (3) dữ liệu công khai hiện tại có phủ tốt miền y tế chưa. Số liệu định lượng về dữ liệu được trích từ phân tích trên *ViMedCSS — Tập hợp & phân nhóm domain thuật ngữ + So sánh với thuật ngữ y khoa phổ biến*.

---

## Vấn đề 1 — Điểm yếu của nhận dạng tiếng nói

> ❓ **Câu hỏi:** Nhận dạng tiếng nói hiện tại yếu ở đâu? *(xét cả mô hình tổng quát và mô hình y tế)*

### 1.1. Điểm yếu cốt lõi

| Điểm yếu | Diễn giải |
| --- | --- |
| **Giả định đầu vào đơn ngữ** | Các hệ nhận dạng tiếng nói thường giả định toàn bộ đầu vào không chuyển sang ngôn ngữ khác giữa câu nói; khi xảy ra chuyển mã thì hệ thống dễ hỏng. |
| **Nhầm lẫn ngôn ngữ** | Nhận dạng lời nói có chuyển mã gặp khó do nhầm lẫn ngôn ngữ, phát sinh từ giọng nói, sự giống nhau về âm thanh và việc chuyển ngôn ngữ liền mạch. |
| **Tỷ lệ lỗi từ tăng vọt khi có chuyển mã** | Trên âm thanh có chuyển mã, tỷ lệ lỗi từ có thể suy giảm thêm khoảng 30–50%, thậm chí cao gấp nhiều lần so với lời nói đơn ngữ. Với hệ chuyên ngành, tỷ lệ lỗi từ nền có thể lên tới khoảng 82%, chỉ giảm còn khoảng 35% sau khi tinh chỉnh. |
| **Bịa nội dung không được nói** | Mô hình giải mã theo cơ chế chú ý (như Whisper) linh hoạt nhưng dễ sinh dư thừa nội dung; việc bịa nội dung bắt nguồn từ dữ liệu gán nhãn yếu cộng với kiến trúc — trong y tế có thể bịa cả liều lượng hoặc triệu chứng. |
| **Coi chuyển mã là "trạng thái lỗi"** | Phần lớn mô hình xem chuyển mã như một trạng thái lỗi, dẫn tới tỷ lệ lỗi từ cao và bản ghi bị bịa nội dung. |

### 1.2. Điểm yếu riêng trong miền y tế

| Điểm yếu | Diễn giải |
| --- | --- |
| **Sai trên từ vựng lâm sàng, nhất là tên thuốc** | Các mô hình hiện có, kể cả những hệ phổ biến như Whisper, vẫn mắc tỷ lệ lỗi cao trên từ vựng lâm sàng, đặc biệt là tên thuốc. |
| **Khan hiếm dữ liệu âm thanh – bản ghi y tế** | Nguyên nhân gốc là sự khan hiếm dữ liệu âm thanh kèm bản ghi có gán nhãn trong miền y tế. |
| **Tỷ lệ lỗi nền cao ngay cả khi đơn ngữ y tế Việt** | Trên bộ chuẩn y tế tiếng Việt VietMed, mô hình tốt nhất vẫn còn tỷ lệ lỗi từ khoảng 27–30% — vẫn cao. |

---

## Vấn đề 2 — Chuyển mã ngôn ngữ Anh–Việt

> ❓ **Câu hỏi:** Hiện tượng này là gì và vì sao đặc biệt khó với cặp Anh–Việt?

### 2.1. Bản chất hiện tượng

- **Định nghĩa & bối cảnh:** Chuyển mã là khi lời nói tiếng Việt xen lẫn từ tiếng Anh, ví dụ tên thuốc hay thủ thuật; đây là hiện tượng phổ biến trong giao tiếp y tế tại Việt Nam, và trước đây chưa có bộ chuẩn nào cho bài toán này.
- **Kiểu khó nhất — xen ngay trong câu:** thuật ngữ Anh nằm rải khắp câu tiếng Việt. Định lượng trên ViMedCSS: vị trí từ tiếng Anh ở **đầu 39% · giữa 29% · cuối 32%**, mật độ **khoảng 0,051 thuật ngữ trên mỗi từ** (xấp xỉ 1 từ tiếng Anh trong 20 từ).
- **Đuôi dài, nhiều từ hiếm:** **889** thuật ngữ riêng biệt trên 16.581 lượt; **18%** chỉ xuất hiện đúng một lần, **48,8%** xuất hiện không quá 5 lần — quá ít tín hiệu để mô hình học.
- **Nhóm thuốc/hoá chất áp đảo:** nhóm Hoá chất & Thuốc chiếm **50,4%** số lượt — đúng chỗ mô hình hay sai nhất (tên thuốc).

### 2.2. Vì sao cặp Anh–Việt khó

| Nguyên nhân | Diễn giải |
| --- | --- |
| **Phát âm tiếng Anh theo giọng ngôn ngữ nền** | Bộ nhận diện ngôn ngữ thường khó nhận đúng tiếng Anh khi được nói bằng giọng của ngôn ngữ chủ đạo — đúng tình huống từ tiếng Anh nói theo giọng Việt. |
| **Đánh đổi giữa mô hình tiếng Việt và mô hình đa ngữ** | Thử nghiệm trên ViMedCSS: mô hình đa ngữ bắt **phần tiếng Anh** tốt; mô hình tối ưu cho tiếng Việt lại bắt **phần tiếng Việt** tốt hơn → không mô hình đơn lẻ nào cân bằng cả hai; cách kết hợp mới cho cân bằng tốt nhất. |
| **Cần xử lý chuyên biệt cho cặp Việt–Anh** | Đã xuất hiện các kiến trúc riêng cho chuyển mã Việt–Anh và các bộ điều hợp "nhận biết ngôn ngữ" gắn vào mô hình — dấu hiệu cho thấy quy trình thông thường thường không đủ. |

### 2.3. Đánh giá định lượng điểm yếu (trên benchmark ViMedCSS)

Số liệu dưới đây trích từ bộ chuẩn ViMedCSS, dùng hai chỉ số tách biệt: **CS-WER** (tỷ lệ lỗi từ chỉ tính trên vùng từ tiếng Anh chuyển mã) và **N-WER** (tỷ lệ lỗi từ trên phần tiếng Việt nền).

> 📉 **Điểm yếu cốt lõi:** ngay cả mô hình tốt nhất ở chế độ chưa tinh chỉnh cũng có **CS-WER ≥ 46,69%** — tức **gần một nửa số từ tiếng Anh y khoa bị nhận dạng sai**, trong khi phần tiếng Việt nền (N-WER) thấp hơn nhiều. Đây là minh chứng định lượng cho việc chuyển mã Anh–Việt là điểm gãy chính.

**Bảng A — Lỗi tách biệt theo vùng (zero-shot, trên tập Test; thấp hơn = tốt hơn):**

| Mô hình | WER toàn câu | **CS-WER** (vùng tiếng Anh) | N-WER (phần tiếng Việt nền) |
| --- | --- | --- | --- |
| Whisper-Large-v3 (đa ngữ) | 34,47 | **46,69** | 35,26 |
| PhoWhisper-Large (tối ưu tiếng Việt) | 31,24 | 55,05 | 32,36 |
| VietASR (tối ưu tiếng Việt) | 27,56 | 58,38 | 28,25 |

> 🔀 **Đánh đổi không cân bằng:** mô hình đa ngữ (Whisper-Large-v3) bắt vùng tiếng Anh tốt nhất (CS-WER thấp nhất) nhưng yếu hơn ở phần tiếng Việt; mô hình tối ưu tiếng Việt (VietASR) có WER/N-WER thấp nhất nhưng CS-WER lại cao nhất (58,38). Không một mô hình đơn lẻ nào mạnh đồng thời ở cả hai vùng.

### 2.4. Điểm yếu vẫn còn ngay cả sau khi tinh chỉnh

| Điểm yếu | Bằng chứng định lượng |
| --- | --- |
| **Từ hiếm / chưa từng gặp vẫn rất khó** | Trên tập Hard (chỉ gồm thuật ngữ xuất hiện 1–2 lần), phương pháp tốt nhất (Attention Guide) vẫn còn CS-WER **57,29%** — khả năng khái quát ra ngoài từ vựng huấn luyện còn hạn chế. |
| **Can thiệp ở tầng giải mã hiệu quả thấp** | Các kỹ thuật thiên lệch từ vựng ở decoder (Dynamic Vocabulary, Rank & Selection) chỉ cải thiện nhẹ so với mô hình nền (CS-WER 62,55 → 60,07). |
| **Chuẩn hoá ngữ cảnh đánh đổi độ chính xác chung** | AdaCS giảm mạnh CS-WER (62,55 → 32,91) nhưng làm **tăng WER/CER toàn câu** — đánh đổi giữa bắt đúng term và giữ đúng câu nền. |
| **Cải thiện không đều theo chủ đề** | Sau tinh chỉnh (AG), Nutrition dễ nhất (CS-WER 13,85) nhưng Diagnostics gần như không cải thiện (vẫn 44,40) — điểm yếu tập trung ở một số miền nhỏ. |

> ⚠️ **Tóm lại:** phương pháp tốt nhất (Attention Guide trên PhoWhisper-Small) kéo CS-WER trên Test xuống còn **19,50%**, nhưng vẫn còn (1) khoảng cách lớn trên từ hiếm (Hard CS-WER 57,29), (2) đánh đổi giữa vùng chuyển mã và câu nền, và (3) phụ thuộc dữ liệu tinh chỉnh trong miền — nên chuyển mã Anh–Việt vẫn là điểm yếu chưa được giải quyết triệt để.

---

## Vấn đề 3 — Dữ liệu công khai có phủ tốt miền y tế chưa?

> ❓ **Câu hỏi:** Các bộ dữ liệu công khai hiện tại đã phủ tốt bài toán *nhận dạng tiếng nói y tế có chuyển mã Việt–Anh* chưa?

### 3.1. Bản đồ dữ liệu: Y tế? × Chuyển mã Việt–Anh? × Dạng dữ liệu

| Bộ dữ liệu | Y tế? | Chuyển mã Việt–Anh? | Dạng dữ liệu | Quy mô |
| --- | --- | --- | --- | --- |
| **ViMedCSS** | Có | Có (lời nói, mức từ) | Tiếng nói | Khoảng 34 giờ, hơn 16.500 câu nói, có thuật ngữ y khoa tiếng Anh, 5 chủ đề y khoa |
| **VietMed** | Có | Không (đơn ngữ Việt) | Tiếng nói | Bộ chuẩn nhận dạng tiếng nói y tế tiếng Việt; tỷ lệ lỗi tốt nhất khoảng 27–30% |
| **MedEV** | Có | Không (song ngữ dịch máy, không phải chuyển mã trong lời nói) | Văn bản (dịch máy) | Dịch máy y khoa Việt–Anh |

### 3.2. Kết luận

> ⚠️ **Chưa phủ tốt.** Các bộ dữ liệu công khai đều mạnh nhưng **tách rời theo từng trục**: y tế *đơn ngữ* tiếng Việt (VietMed, MedEV). Đúng tại **giao điểm "y tế + chuyển mã trong lời nói Việt–Anh"**, ViMedCSS là bộ chuẩn **đầu tiên và công khai** cho bài toán này.

### 3.3. Khoảng trống còn lại

- **Quy mô nhỏ:** ViMedCSS chỉ khoảng 34 giờ với hơn 16.500 câu nói — nhỏ hơn nhiều bậc so với dữ liệu nhận dạng tiếng nói đơn ngữ; bản thân nhóm tác giả cũng định vị đây là bộ chuẩn khởi đầu.
- **Đuôi dài chưa phủ:** 18% thuật ngữ chỉ xuất hiện một lần, 48,8% không quá 5 lần → còn rất nhiều tên thuốc, tên riêng và viết tắt thực tế chưa xuất hiện đủ.
- **Thiếu dữ liệu lâm sàng thật:** khan hiếm dữ liệu âm thanh kèm bản ghi y tế có gán nhãn là nguyên nhân gốc khiến mô hình sai.
- **Thiếu nhãn ngôn ngữ ở mức từ:** khó học việc chuyển ngữ ngay trong câu khi giọng nói làm bộ nhận diện ngôn ngữ bị nhầm.

---

## Ghi chú thuật ngữ

> 📖 Giải thích ngắn gọn các thuật ngữ viết tắt và tên chủ đề được dùng trong báo cáo. Các chỉ số lỗi đều theo quy ước **thấp hơn = tốt hơn**.

### Các chỉ số lỗi (metrics)

| Thuật ngữ | Viết tắt của | Ý nghĩa |
| --- | --- | --- |
| **WER** | Word Error Rate (tỷ lệ lỗi từ) | Tỷ lệ từ bị sai trên toàn bộ câu (tính cả chèn, xóa, thay thế từ so với bản ghi đúng). Đo chất lượng nhận dạng ở mức từ. |
| **CER** | Character Error Rate (tỷ lệ lỗi ký tự) | Giống WER nhưng tính ở mức **ký tự** thay vì từ — nhạy hơn với sai sót nhỏ (dấu, chính tả) và hữu ích cho tiếng Việt có dấu. |
| **CS-WER** | Code-Switching WER | WER **chỉ tính trên vùng từ chuyển mã** (từ tiếng Anh xen trong câu) — đo riêng năng lực nhận dạng term tiếng Anh y khoa. |
| **N-WER** | Non-codeswitch WER (từ không cần chuẩn hoá) | WER **chỉ tính trên phần tiếng Việt nền** (ngoài vùng chuyển mã) — đo chất lượng nhận dạng câu nền. |
