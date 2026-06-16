# Báo cáo nghiên cứu tiếng Việt — Điểm yếu của ASR với medical code-switching Anh/Việt và mức độ bao phủ của các bộ dữ liệu hiện tại

**Ngày tạo:** 2026-06-16  
**Trọng tâm:** nghiên cứu điểm yếu của ASR, đặc biệt với hiện tượng code-switching các thuật ngữ y tế Anh/Việt; đánh giá xem các bộ dữ liệu hiện tại đã cover tốt chưa.  
**Dataset trung tâm:** [`tensorxt/ViMedCSS`](https://huggingface.co/datasets/tensorxt/ViMedCSS)  
**Nguyên tắc viết report:** chỉ ghi số liệu có nguồn; phần nào chưa có bằng chứng trực tiếp thì ghi rõ là “chưa thấy công bố trong nguồn đã đọc”; không tự suy diễn thành sự thật.

---

## 1. Phạm vi kiểm chứng và giới hạn trung thực

### 1.1. Những gì đã kiểm tra được

Report này dựa trên các nguồn công khai sau:

| Mã nguồn | Nguồn | Nội dung dùng trong report |
|---|---|---|
| S1 | ViMedCSS Hugging Face dataset card: https://huggingface.co/datasets/tensorxt/ViMedCSS | Số liệu metadata trên HF: số row, thời lượng, topic, split, data fields, license, file size. |
| S2 | ViMedCSS file tree: https://huggingface.co/datasets/tensorxt/ViMedCSS/tree/main | Cấu trúc repo, dung lượng 18.3GB, folder metadata 5.33MB, 4 file metadata CSV. |
| S3 | ViMedCSS paper arXiv: https://arxiv.org/html/2602.12911v1 | Pipeline xây dataset, số liệu paper, long-tail CS terms, hard split, baseline ASR, fine-tuning results. |
| S4 | VietMed ACL Anthology: https://aclanthology.org/2024.lrec-main.1509/ | Số liệu VietMed: 16h labeled medical speech, 1000h unlabeled medical speech, 1200h unlabeled general-domain speech; coverage ICD-10 và accents. |
| S5 | PhoASR paper: https://arxiv.org/html/2603.14779v1 | Số liệu PhoASR: unified 500h high-quality dataset, PhoASR-3100h, general Vietnamese ASR pipeline. |
| S6 | VietSuperSpeech paper: https://arxiv.org/abs/2603.01894 | Số liệu VietSuperSpeech: 52,023 pairs, 267.39h, conversational Vietnamese, split train/dev-test. |
| S7 | viVoice HF: https://huggingface.co/datasets/capleaf/viVoice | Số liệu viVoice: 887,772 samples, 1,016.97h, 24kHz, train-only, 169GB, TTS-oriented. |
| S8 | TTS augmentation paper: https://arxiv.org/abs/2601.00935 | Dẫn chứng rằng TTS augmentation có thể giúp CS-ASR trong bối cảnh Chinese-English, nhưng chưa phải Vietnamese medical. |

### 1.2. Những gì chưa kiểm tra được

| Hạng mục | Trạng thái | Lý do / cách hiểu đúng |
|---|---|---|
| Full audio-level audit của ViMedCSS | **Chưa thực hiện trong report này** | Dataset có tổng dung lượng HF khoảng 18.3GB. Report này không chạy nghe audio, không chạy ASR lại từ đầu, không đánh giá acoustic quality bằng signal processing. |
| Recompute toàn bộ thống kê từ raw CSV/audio | **Chưa thực hiện đầy đủ** | Report dùng số liệu HF dataset card, file tree, metadata preview và paper. Không tự bịa lại thống kê nếu chưa trực tiếp tải và xử lý toàn bộ file. |
| Đánh giá lỗi ASR bằng mô hình tự chạy | **Chưa thực hiện** | Các con số WER/CER/CS-WER/N-WER trong report lấy từ paper ViMedCSS, không phải kết quả chạy lại. |
| Phân loại `cs_terms_list` thành drug/lab/disease/procedure | **Chưa có trong dataset field công khai đã thấy** | HF card công bố `cs_terms_list`, `cs_terms_count`, `topic`; chưa thấy field entity type chi tiết như `drug`, `lab_test`, `disease`, `procedure`. |

---

## 2. Kết luận điều hành

### 2.1. Câu trả lời ngắn

**ASR hiện tại yếu rõ nhất ở phần nhận diện các “English medical terms” nằm trong câu tiếng Việt.** Đây không chỉ là lỗi nhận dạng tiếng Việt chung, mà là lỗi ở các “đảo ngôn ngữ” như tên thuốc, hoạt chất, hormone, xét nghiệm, viết tắt, thủ thuật, biomarker, thuật ngữ sinh học/y sinh.

**Các bộ dữ liệu hiện tại chưa cover đủ tốt toàn bộ bài toán medical code-switching Anh/Việt.** ViMedCSS là bộ sát nhất hiện tại, vì nó được thiết kế riêng cho Vietnamese medical code-switching ASR. Tuy nhiên, ViMedCSS vẫn chưa đủ cho hướng VietMedVoice nếu mục tiêu là làm một benchmark term-aware sâu hơn theo từng loại lỗi như Drug-WER, Lab-WER, Disease-WER, Abbreviation-WER, Number/Unit Error Rate và TTS augmentation.

### 2.2. Dẫn chứng mạnh nhất

| Dẫn chứng | Số liệu / bằng chứng | Ý nghĩa |
|---|---:|---|
| ViMedCSS paper nói thẳng rằng ASR hiện tại khó nhận đúng English medical terms trong câu tiếng Việt | Paper nêu “current most ASR systems struggle to recognize correctly English medical terms within Vietnamese sentences” | Đây là gap chính của bài toán. |
| ViMedCSS có long-tail rõ | 889 distinct CS terms; 160 term xuất hiện đúng 1 lần; 435 term xuất hiện tối đa 5 lần; 207 term xuất hiện ít nhất 20 lần | Medical terms rất lệch phân phối; nhiều term hiếm nên ASR khó học đủ. |
| Hard split được thiết kế để test rare/unseen CS terms | Hard split chứa các CS medical terms xuất hiện 1–2 lần trong toàn bộ collection; mọi occurrence của các term đó bị loại khỏi Train/Dev/Test để tránh leakage | Đây là setup đúng để kiểm tra generalization với thuật ngữ hiếm/chưa thấy. |
| Zero-shot ASR còn yếu ở CS-WER | VietASR có Test WER 27.56 nhưng Test CS-WER 58.38; Whisper-Large-v3 có Test WER 34.47 nhưng Test CS-WER 46.69 | Ngay cả model mạnh vẫn sai nhiều ở code-switched spans. |
| Fine-tuning giúp test thường nhưng hard CS vẫn khó | PhoWhisper-Small + Attention Guide: Test CS-WER 19.50 nhưng Hard CS-WER 57.29 | Khi gặp rare/unseen terms, lỗi tăng mạnh dù đã fine-tune. |
| Dataset hiện có thiếu entity-level medical tags | HF card thấy `cs_terms_list`, `cs_terms_count`, `topic`; chưa thấy field `entity_type` như drug/lab/disease/procedure | Chưa đủ để đánh giá lỗi theo từng nhóm y tế quan trọng. |

---

## 3. ViMedCSS là gì và hiện có những số liệu nào?

### 3.1. Mô tả theo paper

Theo paper ViMedCSS, dataset này là một Vietnamese medical code-switching speech dataset, trong đó **mỗi utterance có ít nhất một English medical term** lấy từ một bilingual lexicon. Paper báo cáo:

| Chỉ tiêu | Số liệu paper |
|---|---:|
| Tổng thời lượng | 34.57 giờ, paper kết luận làm tròn 34.6 giờ |
| Tổng utterances | 16,576 utterances |
| Số topic | 5 topic |
| Nguồn lexicon | Meddict English–Vietnamese medical lexicon |
| Số entry trong Meddict | 64,232 entries |
| Số CS terms trích xuất từ dictionary để query/crawl | 3,203 CS terms |
| Nguồn audio/video | Public Vietnamese medical videos, chủ yếu YouTube theo mô tả paper |
| Số video được crawl | hơn 13,000 YouTube videos |
| Tổng audio được xử lý ban đầu | hơn 700 giờ |
| CS terms distinct trong dataset cuối | 889 distinct CS terms |
| Segment length | 3–29 giây |
| Quality check | sample 500 utterances, khoảng 1 giờ, stratified theo 5 topics, 2 annotators review |

### 3.2. Mô tả theo Hugging Face dataset card

HF dataset card báo cáo thống kê metadata như sau:

| Split | # Rows | Duration hours | Avg duration seconds | Total CS terms |
|---|---:|---:|---:|---:|
| train | 11,832 | 24.30 | 7.39 | 12,314 |
| validation | 1,714 | 3.57 | 7.49 | 1,814 |
| test | 1,614 | 3.39 | 7.56 | 1,695 |
| hard | 658 | 1.38 | 7.57 | 758 |
| **Total** | **15,818** | **32.64** | **7.43** | **16,581** |

Tỷ lệ theo metadata HF:

| Split | % rows | % duration | % CS terms |
|---|---:|---:|---:|
| train | 74.80% | 74.45% | 74.27% |
| validation | 10.84% | 10.94% | 10.94% |
| test | 10.20% | 10.39% | 10.22% |
| hard | 4.16% | 4.23% | 4.57% |

### 3.3. Điểm không khớp giữa paper và HF metadata

Đây là điểm bắt buộc phải ghi trung thực:

| Nguồn | Tổng utterances / rows | Tổng thời lượng | Ghi chú |
|---|---:|---:|---|
| Paper ViMedCSS | 16,576 utterances | 34.57h / 34.6h | Số liệu trong paper. |
| HF metadata card | 15,818 rows | 32.64h | Số liệu từ `ViMedCSS-Metadata` trên HF. |
| Chênh lệch | 758 rows | 1.93h | Chưa xác định nguyên nhân từ nguồn công khai đã đọc. Không nên tự suy đoán. |

Cách dùng đúng trong nghiên cứu: khi viết paper/proposal nên ghi rõ “paper reports 34.57h / 16,576 utterances, while the currently visible HF metadata reports 32.64h / 15,818 rows.” Không nên gom hai con số này thành một thống kê duy nhất.

---

## 4. Dataset ViMedCSS cover code-switching tốt tới đâu?

### 4.1. Điểm mạnh

| Tiêu chí | Đánh giá | Dẫn chứng |
|---|---|---|
| Có target rõ cho medical code-switching | **Mạnh** | Mỗi utterance có ít nhất một CS medical term theo paper. |
| Có term list ở từng segment | **Mạnh** | HF fields có `cs_terms_list` và `cs_terms_count`. |
| Có hard split | **Rất mạnh** | Hard split dành cho rare/unseen CS terms, tránh leakage với Train/Dev/Test. |
| Có benchmark ASR | **Mạnh** | Paper báo cáo WER, CER, CS-WER, N-WER cho nhiều model. |
| Có topic coverage | **Khá tốt** | Có 5 topic: Medical Sciences, Pathology & Pathogens, Treatments, Nutrition, Diagnostics. |
| Có source metadata | **Tốt cho traceability** | HF fields có original video link/title, start_time, end_time. |

### 4.2. Topic coverage theo HF metadata

| Topic | # Rows | % rows | Duration hours | % duration | Total CS terms | % CS terms |
|---|---:|---:|---:|---:|---:|---:|
| Medical Sciences | 6,836 | 43.22% | 14.68 | 44.98% | 7,459 | 44.99% |
| Pathology & Pathogens | 4,827 | 30.52% | 10.00 | 30.64% | 4,951 | 29.86% |
| Treatments | 1,969 | 12.45% | 3.80 | 11.64% | 1,985 | 11.97% |
| Nutrition | 1,155 | 7.30% | 2.14 | 6.56% | 1,155 | 6.97% |
| Diagnostics | 1,031 | 6.52% | 2.02 | 6.19% | 1,031 | 6.22% |
| **Total** | **15,818** | **100%** | **32.64** | **100%** | **16,581** | **100%** |

Nhận xét trung thực: dataset có topic y tế rõ, nhưng phân bổ nghiêng nhiều về **Medical Sciences** và **Pathology & Pathogens**. Phần **Diagnostics** chỉ chiếm khoảng 6.19% duration theo HF metadata. Nếu mục tiêu của dự án là đánh mạnh vào lab tests, xét nghiệm, chỉ số y khoa, đơn vị đo, thì ViMedCSS có ích nhưng có thể chưa đủ.

### 4.3. Ví dụ thật từ metadata/paper

Các ví dụ dưới đây lấy từ metadata preview trên HF hoặc từ paper. Mục đích là minh họa loại code-switching xuất hiện trong dataset, không phải thống kê toàn bộ.

| Segment / nguồn | Câu tiếng Việt chứa term Anh/ngoại lai | `cs_terms_list` | Nhận xét ASR-risk |
|---|---|---|---|
| HF metadata preview | “Vậy thì methionin có nhiều ở trong các cái loại thực phẩm nào?” | methionin | Tên hoạt chất/dinh dưỡng; dễ bị ASR Việt hóa sai chính tả. |
| HF metadata preview | “Đồng thời là tổng hợp glutathion, đây là một chất chống oxy hóa cực mạnh...” | glutathion | Term sinh hóa; có nhiều biến thể viết/phát âm. |
| HF metadata preview | “...tiết ra hóc môn sinh dục... estrogen và progesteron.” | estrogen; progesteron | Hormone; có cách viết/phát âm Anh–Việt khác nhau. |
| HF metadata preview | “Nüchtern hoặc Nüchternwert là chỉ số glucose lúc đói...” | glucose | Có cả term Đức/ngoại lai và glucose; rất khó cho ASR nếu không có domain bias. |
| Hard set preview | “Bệnh cường giáp là một rối loạn nội tiết xảy ra khi tuyến giáp sản xuất quá mức hormone thyroxine và triiodothyronine.” | hormone; thyroxine; triiodothyronine | Nhiều term trong cùng câu; term dài, dễ sai tokenization. |
| Hard set preview | “...đột biến gen HGD, dẫn đến cơ thể không thể phân giải hoàn toàn homogentisic acid.” | homogentisic | Term hiếm; đúng kiểu hard/long-tail. |
| Hard set preview | “...hệ renin, Angiotensin, aldosterone...” | renin; Angiotensin; aldosterone | Cụm sinh lý bệnh/tim mạch; có viết hoa/thường không đồng nhất. |
| Hard set preview | “...thuốc kháng aldosterone á, à cái đại diện là Spironolactone...” | aldosterone | Term thuốc/hormone trong câu nói tự nhiên, có filler “á, à”. |

### 4.4. Những điểm ViMedCSS chưa cover đủ cho VietMedVoice

| Thiếu hụt | Bằng chứng | Vì sao quan trọng |
|---|---|---|
| Chưa thấy entity type chi tiết | HF fields công bố `cs_terms_list`, `cs_terms_count`, `topic`; chưa thấy field `entity_type` | Không đo trực tiếp được Drug-WER, Lab-WER, Disease-WER, Procedure-WER nếu không annotate thêm. |
| Chưa thấy dosage/unit-specific labels | Chưa thấy field riêng cho số, đơn vị, liều lượng như mg, ml, %, mmol/L | Medical ASR cần kiểm soát lỗi số/đơn vị vì sai liều có rủi ro cao. |
| Chưa thấy speaker/role metadata | HF fields công bố source video, time, text, CS terms, topic; chưa thấy speaker_id / speaker_role | Không đủ cho doctor-patient role, diarization, speaker diversity analysis. |
| Chưa phải TTS augmentation dataset | ViMedCSS là ASR benchmark; không có synthetic_tts_segments hoặc synthetic_speaker_id | Không trực tiếp trả lời câu hỏi “TTS có giúp ASR nhận term hiếm không?” |
| Nguồn YouTube/public video | Paper nói crawl public Vietnamese medical videos; HF cũng giữ original video link/title | Có ích cho scale, nhưng cần kiểm tra license/redistribution khi dùng hoặc publish lại. |
| Diagnostics coverage còn nhỏ | HF metadata: Diagnostics 2.02h / 32.64h, khoảng 6.19% duration | Nếu muốn lab-test/code như HbA1c/eGFR/CRP/AST/ALT thì cần bổ sung hoặc annotate sâu hơn. |

---

## 5. Điểm yếu của ASR với code-switching Anh/Việt trong y tế

### 5.1. Điểm yếu 1 — ASR nghe tốt phần tiếng Việt nhưng rớt ở term Anh/ngoại lai

Dẫn chứng từ ViMedCSS paper: kết quả zero-shot cho thấy model Vietnamese-optimized thường tốt hơn về WER/N-WER, nhưng multilingual model tốt hơn ở CS-WER.

| Model zero-shot | Test WER | Test CS-WER | Test N-WER | Chênh lệch CS-WER − N-WER | Nhận xét |
|---|---:|---:|---:|---:|---|
| VietASR | 27.56 | 58.38 | 28.25 | +30.13 | WER tổng tốt nhất trong bảng zero-shot, nhưng CS-WER vẫn rất cao. |
| PhoWhisper-Large | 31.24 | 55.05 | 32.36 | +22.69 | Vietnamese-adapted model tốt phần tiếng Việt hơn, nhưng CS terms vẫn khó. |
| Whisper-Large-v3 | 34.47 | 46.69 | 35.26 | +11.43 | Multilingual model bắt CS tốt hơn, nhưng WER tổng không tốt nhất. |

Kết luận: đây là trade-off rất rõ. Mô hình tối ưu tiếng Việt không tự động giỏi nhận English medical insertions. Mô hình multilingual có lợi ở phần English insertions nhưng không nhất thiết tốt nhất ở toàn câu tiếng Việt.

### 5.2. Điểm yếu 2 — Rare/unseen medical terms vẫn rất khó dù đã fine-tune

Dẫn chứng từ kết quả fine-tuning trong paper:

| Method trên PhoWhisper-Small | Test WER | Test CS-WER | Hard WER | Hard CS-WER | Nhận xét |
|---|---:|---:|---:|---:|---|
| Frozen | 36.31 | 62.55 | 46.27 | 66.01 | Không fine-tune, CS-WER rất cao. |
| LoRA | 27.13 | 30.26 | 37.27 | 60.71 | Test thường cải thiện mạnh, nhưng hard CS vẫn cao. |
| Attention Guide | 23.67 | 19.50 | 33.73 | 57.29 | Tốt nhất trên Test CS-WER, nhưng Hard CS-WER vẫn 57.29. |
| AG + AdaCS | 25.82 | 20.86 | 35.00 | 57.29 | Không cải thiện Hard CS-WER so với AG trong bảng paper. |

Điểm quan trọng: **Attention Guide giảm Test CS-WER xuống 19.50, nhưng Hard CS-WER vẫn 57.29**. Chênh lệch này là **+37.79 điểm tuyệt đối**. Điều đó cho thấy bài toán term hiếm/chưa thấy vẫn chưa được giải quyết tốt.

### 5.3. Điểm yếu 3 — Long-tail term distribution làm ASR thiếu ví dụ học

Paper báo cáo ViMedCSS có **889 distinct code-switched medical terms**. Trong đó:

| Nhóm tần suất | Số term | Tỷ lệ trên 889 terms | Ý nghĩa |
|---|---:|---:|---|
| Xuất hiện đúng 1 lần | 160 | 18.00% | Rất khó học ổn định nếu chỉ dựa vào real data. |
| Xuất hiện tối đa 5 lần | 435 | 48.93% | Gần một nửa vocabulary là low-frequency. |
| Xuất hiện ít nhất 20 lần | 207 | 23.28% | Chỉ một phần nhỏ có đủ occurrence tương đối tốt. |

Kết luận: vấn đề không chỉ là thiếu giờ audio. Vấn đề là **thiếu occurrence cho từng term hiếm**. Với y tế, long-tail là bản chất: tên thuốc, hoạt chất, marker, gene, thủ thuật, biến thể bệnh, xét nghiệm chuyên sâu thường không xuất hiện nhiều trong dữ liệu tự nhiên.

### 5.4. Điểm yếu 4 — Normalization và surface variants gây lỗi

Paper mô tả họ phải normalize surface forms về canonical dictionary, gồm orthography, hyphenation, casing, common variants. Điều này cho thấy ngay trong dữ liệu gốc, cùng một term có thể có nhiều cách viết/cách xuất hiện. Ví dụ từ metadata có thể thấy các term như `Angiotensin`, `aldosterone`, `estrogen`, `progesteron`, `methionin`, `glucose`, `glycosyl`, `thyroxine`, `triiodothyronine`.

Rủi ro ASR thực tế:

| Loại biến thể | Ví dụ | Rủi ro |
|---|---|---|
| Viết hoa/thường | Angiotensin vs angiotensin | WER/CER có thể bị phạt nếu normalization không thống nhất. |
| Anh hóa / Việt hóa | progesterone vs progesteron | ASR có thể sinh dạng khác transcript gold. |
| Term dài | triiodothyronine, homogentisic acid | Dễ sai token, sai âm tiết, thiếu ký tự. |
| Viết tắt/chữ cái | HGD, HbA1c, HDAC | Cần metric riêng cho abbreviation; report này chưa thấy ViMedCSS công bố field riêng. |
| Số/đơn vị | 250 mg, 80–120 mg/dl | Rất quan trọng trong y tế; chưa thấy field riêng trong metadata công khai. |

### 5.5. Điểm yếu 5 — Câu nói tự nhiên có filler, lặp từ, ngắt nhịp

Một số ví dụ trong hard set preview có style nói tự nhiên, ví dụ câu có “á, à”, lặp từ, hoặc cấu trúc không hoàn toàn như văn viết. Điều này làm ASR khó hơn vì model phải vừa nhận tiếng Việt tự nhiên vừa nhận term Anh/ngoại lai.

Ví dụ metadata preview:

> “Nếu mà chúng ta sử dụng kháng aldosterone á, à cái đại diện là Spironolactone á là nó nó là cái thuốc kháng aldosterone.”

Dẫn chứng này cho thấy medical CS không chỉ là câu sạch kiểu textbook. Nó có thể là lời giảng/giải thích tự nhiên, có filler và lặp từ.

---

## 6. Các bộ dữ liệu hiện tại đã cover tốt chưa?

### 6.1. Bảng so sánh theo trọng tâm code-switching medical Anh/Việt

| Dataset | Quy mô có nguồn | Domain | Có medical? | Có code-switch Anh/Việt y tế? | Có hard rare-term split? | Có entity-type tags drug/lab/disease? | Đánh giá cho mục tiêu VietMedVoice |
|---|---:|---|---|---|---|---|---|
| ViMedCSS | Paper: 34.57h, 16,576 utterances; HF metadata: 32.64h, 15,818 rows | Vietnamese medical code-switching | Có | Có, rất rõ | Có | Chưa thấy field chi tiết trong HF card | **Tốt nhất hiện tại làm baseline**, nhưng chưa đủ term-aware sâu/TTS augmentation. |
| VietMed | 16h labeled medical + 1000h unlabeled medical + 1200h unlabeled general-domain | Vietnamese medical ASR | Có | Chưa thấy abstract nói tập trung CS Anh/Việt | Chưa thấy trong abstract | Chưa kết luận từ nguồn đã đọc | **Rất quan trọng cho medical ASR**, nhưng không thay thế ViMedCSS cho CS benchmark. |
| PhoASR | 500h high-quality unified dataset; PhoASR-3100h experiment | General Vietnamese ASR | Không chuyên y tế | Không phải trọng tâm | Không phải trọng tâm | Không | **Tốt cho ASR nền/pipeline**, không cover medical CS. |
| VietSuperSpeech | 52,023 audio-text pairs, 267.39h; train 46,822 samples / 240.67h, dev-test 5,201 samples / 26.72h | Conversational Vietnamese | Không chuyên y tế | Không phải trọng tâm | Không phải trọng tâm | Không | **Tốt cho conversational style**, nhưng không cover medical CS. |
| viVoice | 887,772 samples, 1,016.97h, 24kHz, train-only, 169GB | TTS-oriented Vietnamese from YouTube | Không chuyên y tế | Không phải trọng tâm | Không | Không | **Hữu ích cho TTS tiếng Việt**, nhưng không phải medical CS ASR benchmark. |
| VietSpeech | Over 1,100h theo HF/GitHub result | General Vietnamese ASR | Không chuyên y tế | Không phải trọng tâm | Không rõ | Không rõ | **Có ích cho general ASR**, không giải quyết trực tiếp medical CS. |
| Bud500 | Khoảng 500h broad-topic Vietnamese speech | General Vietnamese ASR | Không chuyên y tế | Không phải trọng tâm | Không rõ | Không rõ | **Có ích cho general ASR**, không đủ cho medical code-switching. |

### 6.2. Kết luận coverage

| Câu hỏi | Trả lời trung thực |
|---|---|
| Có dataset nào hiện cover trực tiếp Vietnamese medical code-switching không? | **Có: ViMedCSS là bộ rõ nhất hiện tại** theo paper và HF card. |
| ViMedCSS đã đủ cho research gap chưa? | **Chưa đủ nếu mục tiêu là VietMedVoice đầy đủ.** Nó tốt cho ASR benchmark CS, nhưng chưa đủ entity-type metrics, TTS augmentation, speaker/role, dosage/unit labels. |
| VietMed có thể thay ViMedCSS không? | **Không nên xem là thay thế.** VietMed mạnh về medical ASR tổng quát, labeled/unlabeled medical speech, ICD-10/accent coverage; nhưng nguồn đã đọc không cho thấy nó tập trung vào English/Vietnamese CS terms như ViMedCSS. |
| General Vietnamese ASR datasets có giải quyết được term Anh/Việt y tế không? | **Không đủ bằng chứng.** Các dataset như PhoASR, VietSuperSpeech, viVoice, VietSpeech, Bud500 giúp ASR/TTS tiếng Việt nói chung, nhưng không được thiết kế để đo medical CS term errors. |
| Có dataset nào sẵn cho TTS augmentation medical CS tiếng Việt chưa? | **Chưa thấy trong các nguồn đã đọc.** viVoice là TTS-oriented nhưng không medical-specific; ViMedCSS là ASR benchmark, không phải synthetic TTS augmentation dataset. |

---

## 7. Vì sao đây là research gap tốt cho VietMedVoice?

### 7.1. Gap hiện tại

Các nguồn hiện tại tách rời thành ba nhóm:

| Nhóm | Dataset tiêu biểu | Mạnh ở đâu | Còn thiếu gì |
|---|---|---|---|
| Medical ASR | VietMed | Medical domain, labeled + unlabeled medical speech, ICD-10/accent coverage | Không phải benchmark chính cho English/Vietnamese CS terms theo nguồn đã đọc. |
| Medical CS-ASR | ViMedCSS | Đúng trọng tâm code-switching y tế; có hard split và CS-WER | Thiếu entity-type metrics, TTS augmentation, synthetic speaker, dosage/unit labels. |
| General Vietnamese ASR/TTS | PhoASR, VietSuperSpeech, viVoice, VietSpeech, Bud500 | Scale lớn, accent/style/general speech | Không y tế, không CS term-aware. |

Vì vậy, khoảng trống hợp lý là:

> **Một benchmark/pipeline tiếng Việt y tế có real ASR + controlled medical text + synthetic TTS augmentation + term-aware evaluation cho các nhóm drug/lab/disease/procedure/abbreviation/number-unit.**

### 7.2. Dẫn chứng TTS augmentation có tiềm năng nhưng chưa trực tiếp giải quyết Vietnamese medical CS

Paper “Improving Code-Switching Speech Recognition with TTS Data Augmentation” báo cáo trong bối cảnh Chinese-English SEAME rằng augment real speech bằng synthetic TTS speech giảm MER từ **12.1% xuống 10.1%** trên DevMan và từ **17.8% xuống 16.0%** trên DevSGE. Paper này cho thấy hướng TTS augmentation có tiềm năng cho CS-ASR, nhưng đây không phải Vietnamese medical domain.

Cách dùng trung thực cho VietMedVoice: không nói “TTS chắc chắn cải thiện Vietnamese medical ASR”, mà nên viết:

> Prior CS-ASR work suggests that multilingual TTS augmentation can improve code-switching ASR in Chinese-English conversational speech. Vietnamese medical code-switching remains untested under this augmentation setup, especially for rare medical terms.

---

## 8. Tiêu chí đánh giá nên dùng cho VietMedVoice

Dựa trên điểm yếu đã thấy, chỉ dùng WER/CER là chưa đủ. Nên bổ sung metric theo term.

| Metric | Có trong ViMedCSS paper? | Có sẵn field để tính trực tiếp từ HF metadata? | Cần bổ sung gì? |
|---|---|---|---|
| WER | Có | Cần prediction ASR | Chạy ASR/fine-tune để tính. |
| CER | Có | Cần prediction ASR | Chạy ASR/fine-tune để tính. |
| CS-WER | Có | Có `cs_terms_list`, nhưng vẫn cần align/prediction | Cần evaluation script. |
| N-WER | Có | Cần span separation/prediction | Cần evaluation script. |
| Drug-WER | Chưa thấy | Chưa thấy drug labels | Cần annotate `entity_type=drug`. |
| Disease-WER | Chưa thấy | Chưa thấy disease labels | Cần annotate `entity_type=disease`. |
| Lab-WER | Chưa thấy | Chưa thấy lab labels | Cần annotate `entity_type=lab_test`. |
| Procedure-WER | Chưa thấy | Chưa thấy procedure labels | Cần annotate `entity_type=procedure`. |
| Abbreviation-WER | Chưa thấy | Chưa thấy abbreviation labels | Cần annotate abbreviations như HbA1c, CT, MRI, ECG, ICU. |
| Number/Unit Error Rate | Chưa thấy | Chưa thấy dosage/unit fields | Cần annotate số, đơn vị, liều lượng. |
| Rare-Term Recall | Có hướng hard split, nhưng chưa thấy metric riêng tên này trong paper | Cần list rare terms và prediction | Nên thêm cho VietMedVoice. |

---

## 9. Đề xuất research direction sau khi đánh giá dataset

### 9.1. Không nên làm gì

Không nên chỉ làm “một dataset ASR y tế tiếng Việt khác”. ViMedCSS đã có hướng medical CS benchmark rất gần. Nếu làm lại cùng cấu trúc, novelty yếu.

Không nên tuyên bố dataset hiện tại “cover hết medical code-switching”. Bằng chứng hiện tại chỉ cho thấy ViMedCSS cover tốt một phần quan trọng: English/foreign-root medical terms trong Vietnamese utterances, có topic và hard split. Nhưng chưa thấy cover sâu theo entity type, dosage/unit, speaker role, hoặc TTS augmentation.

### 9.2. Nên làm gì

Hướng mạnh hơn:

> Xây VietMedVoice như một extension/evaluation pipeline trên gap của ViMedCSS: term-aware Vietnamese medical CS-ASR + TTS-based augmentation cho rare medical terms.

Các module nên có:

| Module | Mục tiêu | Vì sao khác biệt |
|---|---|---|
| Real ASR benchmark | Có real-only train/dev/test/hard | Giữ benchmark thực tế, không đánh giá trên synthetic test. |
| Medical text corpus | Tạo câu có kiểm soát theo drug/lab/disease/procedure/abbreviation | Chủ động cover term hiếm thay vì chờ xuất hiện tự nhiên. |
| Synthetic TTS augmentation | Sinh audio cho hard/rare terms với nhiều synthetic speakers | Trực tiếp test giả thuyết TTS giúp ASR nhận term hiếm. |
| Entity-type annotation | Gắn nhãn drug/lab/disease/procedure/abbreviation/number-unit | Cho phép metric sâu hơn CS-WER chung. |
| Error analysis | Phân tích lỗi theo type, rarity, topic, pronunciation variant | Biến dataset thành benchmark nghiên cứu nghiêm túc. |

### 9.3. Câu research question đề xuất

> Can TTS-generated synthetic Vietnamese medical speech improve ASR robustness on rare English–Vietnamese medical code-switching terms, especially drug names, lab tests, abbreviations, diseases, procedures, and dosage/unit expressions, when evaluated on a real-only test set?

---

## 10. Checklist đánh giá dataset trước khi dùng tiếp

| Hạng mục | Với ViMedCSS hiện tại | Việc cần làm tiếp |
|---|---|---|
| Xác nhận số liệu paper vs HF | Có chênh lệch 16,576/34.57h vs 15,818/32.64h | Tải metadata CSV đầy đủ và đối chiếu commit/version. |
| Kiểm tra audio accessibility | Repo HF có data 18.3GB | Tải thử bằng `datasets` hoặc Git LFS ở môi trường có mạng ổn định. |
| Kiểm tra transcript quality | Paper có sample 500 utterances/2 annotators | Nghe lại sample riêng 100–300 clips để xác nhận cho use case của mình. |
| Kiểm tra term taxonomy | Chưa thấy entity type | Map `cs_terms_list` sang dictionary drug/lab/disease/procedure. |
| Kiểm tra hard split leakage | Paper nói hard terms removed khỏi Train/Dev/Test | Recompute từ metadata CSV để xác nhận. |
| Kiểm tra legal/reuse | HF license cc-by-4.0; nhưng paper/HF note có YouTube và Meddict IP | Cần rà lại redistribution/commercial/internal-use policy trước khi publish derivative dataset. |
| Kiểm tra TTS suitability | Chưa có synthetic view | Tạo `medical_texts.jsonl` và `synthetic_tts_segments.jsonl`. |

---

## 11. Kết luận cuối cùng

### 11.1. ASR yếu ở đâu?

ASR yếu nhất ở các **code-switched medical spans**: tên thuốc/hoạt chất, hormone, xét nghiệm, biomarker, viết tắt, thủ thuật, term sinh học/y sinh. Bằng chứng trực tiếp là CS-WER cao hơn rõ rệt so với N-WER trong zero-shot baseline của ViMedCSS. Ví dụ VietASR có Test WER 27.56 nhưng Test CS-WER 58.38; Attention Guide fine-tuning giảm Test CS-WER còn 19.50 nhưng Hard CS-WER vẫn 57.29.

### 11.2. Dataset hiện tại cover tốt chưa?

**Chưa đủ.** ViMedCSS cover tốt nhất phần Vietnamese medical code-switching hiện tại, nhưng chưa cover đầy đủ các yêu cầu cần cho một benchmark VietMedVoice hoàn chỉnh:

1. chưa thấy entity-type labels cho drug/lab/disease/procedure;
2. chưa thấy dosage/unit-specific labels;
3. chưa có TTS synthetic augmentation view;
4. chưa có synthetic speaker diversity;
5. chưa thấy speaker role/diarization metadata;
6. diagnostics coverage còn nhỏ theo HF metadata;
7. số liệu paper và HF metadata có chênh lệch cần đối chiếu trước khi dùng làm thống kê chính thức.

### 11.3. Hướng đi nên chốt

ViMedCSS nên được dùng làm **baseline/reference dataset**, không nên xem là đối thủ phải làm lại y chang. Khoảng trống tốt hơn là:

> **VietMedVoice: Vietnamese medical code-switching ASR benchmark extension with controlled medical text, TTS-based rare-term augmentation, and entity-level medical error metrics.**

---

## 12. Phụ lục — Nguồn tham khảo

1. ViMedCSS Hugging Face dataset card: https://huggingface.co/datasets/tensorxt/ViMedCSS  
2. ViMedCSS file tree: https://huggingface.co/datasets/tensorxt/ViMedCSS/tree/main  
3. ViMedCSS metadata folder: https://huggingface.co/datasets/tensorxt/ViMedCSS/tree/main/ViMedCSS-Metadata  
4. ViMedCSS paper: https://arxiv.org/html/2602.12911v1  
5. VietMed ACL Anthology: https://aclanthology.org/2024.lrec-main.1509/  
6. PhoASR paper: https://arxiv.org/html/2603.14779v1  
7. VietSuperSpeech paper: https://arxiv.org/abs/2603.01894  
8. viVoice dataset: https://huggingface.co/datasets/capleaf/viVoice  
9. TTS augmentation for CS-ASR: https://arxiv.org/abs/2601.00935
