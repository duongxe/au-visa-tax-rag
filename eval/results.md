# Kết quả đánh giá / Evaluation results

Chạy ngày 2026-11-23 trên 50 câu hỏi (42 có trong tài liệu, 8 ngoài tài liệu; 30 tiếng Việt, 20 tiếng Anh). Câu hỏi và đáp án chuẩn: [questions.csv](questions.csv). Câu trả lời và đoạn tài liệu lấy về: [runs/answers.jsonl](runs/answers.jsonl). Điểm RAGAS từng câu: [runs/ragas_scores.csv](runs/ragas_scores.csv).

## Tổng quan

| Chỉ số | Kết quả |
|---|---|
| Trả lời được (câu có trong tài liệu) | 39/42 (93%) |
| Nói "không biết" đúng (câu ngoài tài liệu) | 8/8 (100%) |
| Retrieval hit@5 (có trang nguồn đúng trong 5 đoạn lấy về) | 41/42 (98%) |
| Trích dẫn đúng trang nguồn | 38/42 (90%) |
| Trả lời đúng ngôn ngữ câu hỏi | 36/50 (72%) |
| Lỗi (mọi LLM đều thất bại) | 0 |
| Thời gian trả lời (trung vị / lâu nhất) | 2.8s / 40.6s |

## RAGAS (39 câu có trong tài liệu và đã được trả lời)

| Nhóm | n | faithfulness | answer_relevancy | context_precision | context_recall |
|---|---|---|---|---|---|
| Tất cả | 39 | 0.96 | 0.84 | 0.86 | 0.93 |
| Tiếng Việt | 23 | 0.95 | 0.83 | 0.84 | 0.89 |
| Tiếng Anh | 16 | 0.98 | 0.85 | 0.90 | 0.98 |
| Độ khó: easy | 17 | 0.96 | 0.83 | 0.85 | 0.94 |
| Độ khó: medium | 19 | 0.95 | 0.84 | 0.86 | 0.94 |
| Độ khó: hard | 3 | 1.00 | 0.91 | 0.96 | 0.67 |

Điểm trống (LLM chấm bị giới hạn lượt, không tính vào trung bình): faithfulness 1/39, answer_relevancy 1/39, context_precision 0/39, context_recall 2/39.

- **faithfulness**: tỷ lệ ý trong câu trả lời có căn cứ trong đoạn tài liệu lấy về (thấp = bịa).
- **answer_relevancy**: câu trả lời có đúng trọng tâm câu hỏi không.
- **context_precision**: đoạn liên quan có được xếp lên đầu không (so với đáp án chuẩn).
- **context_recall**: tỷ lệ ý của đáp án chuẩn tìm thấy trong các đoạn lấy về.

## Model đã trả lời

| Model | Số câu |
|---|---|
| `gemini:gemini-3.5-flash-lite` | 40 |
| `gemini:gemini-3.5-flash` | 5 |
| `groq:openai/gpt-oss-120b` | 5 |

## Câu cần xem lại

- **#4** Bố mẹ tôi muốn sang Úc thăm tôi thì xin visa gì?: điểm thấp: context_recall 0.33
- **#6** Visa 870 cho bố mẹ ở được bao lâu và cần điều kiện gì trước khi nộp?: điểm thấp: context_precision 0.42
- **#10** Visa 482 cần bao nhiêu năm kinh nghiệm làm việc?: không trả lời được; không lấy được trang nguồn đúng
- **#12** Visa 189 cần tối thiểu bao nhiêu điểm?: điểm thấp: context_precision 0.50
- **#19** Are New Zealand citizens automatically granted a Special Category visa 444?: không trả lời được; sai ngôn ngữ
- **#20** Visa 400 dùng để làm gì?: điểm thấp: context_recall 0.00
- **#25** Mới sang Úc giữa năm thì ngưỡng miễn thuế tính thế nào?: điểm thấp: context_precision 0.50
- **#33** Người không cư trú thuế có phải đóng Medicare levy không?: điểm thấp: context_precision 0.33
- **#39** Nhân viên casual có được nghỉ phép năm có lương không?: không trả lời được
- **#5** How long can I stay in Australia on a Sponsored Family visitor visa?: sai ngôn ngữ
- **#7** What is the balance of family test for Parent visas?: sai ngôn ngữ
- **#9** What are the eligibility requirements for the Temporary Graduate visa 485?: sai ngôn ngữ
- **#11** What English test score do I need for the subclass 482 Core Skills stream?: sai ngôn ngữ
- **#16** Can I apply for a Student Guardian visa 590 while in Australia?: sai ngôn ngữ
- **#18** Is the Medical Treatment visa 602 free?: sai ngôn ngữ
- **#21** Who can get a Partner visa (subclass 801)?: sai ngôn ngữ
- **#24** How much tax does a registered WHM employer withhold from a working holiday maker?: sai ngôn ngữ
- **#28** What tax rate applies to a DASP for working holiday makers?: sai ngôn ngữ
- **#29** Can I submit my DASP application before leaving Australia?: sai ngôn ngữ
- **#32** What does the fixed rate method for working from home cover?: sai ngôn ngữ
- **#38** What is casual loading?: sai ngôn ngữ
- **#41** Do visa holders have the same workplace rights as Australian workers?: sai ngôn ngữ

## Từng câu

| # | lang | độ khó | trả lời | hit@5 | trích đúng | faith | relev | ctx P | ctx R | giây |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | vi | easy | ✅ | ✅ | ✅ | 1.00 | 0.91 | 0.95 | 1.00 | 40.6 |
| 2 | en | easy | ✅ | ✅ | ✅ | 1.00 | 0.89 | 1.00 | 1.00 | 19.6 |
| 3 | vi | easy | ✅ | ✅ | ✅ | 1.00 | 0.75 | 1.00 | 1.00 | 17.7 |
| 4 | vi | hard | ✅ | ✅ | ✅ | 1.00 | 0.95 | 1.00 | 0.33 | 23.8 |
| 5 | en | easy | ✅ | ✅ | ✅ | 1.00 | 0.76 | 1.00 | 1.00 | 7.4 |
| 6 | vi | medium | ✅ | ✅ | ✅ | 1.00 | 0.67 | 0.42 | 0.67 | 8.0 |
| 7 | en | medium | ✅ | ✅ | ✅ | 1.00 | 0.70 | 0.68 | 1.00 | 6.6 |
| 8 | vi | easy | ✅ | ✅ | ✅ | 1.00 | 0.84 | 0.70 | 1.00 | 5.7 |
| 9 | en | medium | ✅ | ✅ | ✅ | 1.00 | 0.83 | 0.76 | 1.00 | 6.6 |
| 10 | vi | hard | ❌ | ❌ | ❌ | - | - | - | - | 5.7 |
| 11 | en | medium | ✅ | ✅ | ✅ | 1.00 | 0.85 | 0.70 | 1.00 | 10.7 |
| 12 | vi | easy | ✅ | ✅ | ✅ | 0.50 | 0.82 | 0.50 | 1.00 | 6.9 |
| 13 | vi | easy | ✅ | ✅ | ✅ | 1.00 | 0.79 | 1.00 | 1.00 | 3.8 |
| 14 | vi | medium | ✅ | ✅ | ✅ | 1.00 | 0.92 | 1.00 | 1.00 | 3.8 |
| 15 | vi | medium | ✅ | ✅ | ✅ | 1.00 | 0.95 | 1.00 | 1.00 | 3.0 |
| 16 | en | medium | ✅ | ✅ | ✅ | 0.80 | 0.88 | 1.00 | 0.67 | 3.7 |
| 17 | vi | medium | ✅ | ✅ | ✅ | 0.50 | 0.84 | 1.00 | 1.00 | 2.7 |
| 18 | en | medium | ✅ | ✅ | ✅ | 1.00 | 0.85 | 1.00 | 1.00 | 2.3 |
| 19 | en | medium | ❌ | ✅ | ❌ | - | - | - | - | 2.5 |
| 20 | vi | easy | ✅ | ✅ | ✅ | 1.00 | 0.73 | 0.70 | 0.00 | 2.6 |
| 21 | en | medium | ✅ | ✅ | ✅ | 0.83 | 0.89 | 1.00 | 1.00 | 18.1 |
| 22 | vi | hard | ✅ | ✅ | ✅ | 1.00 | 0.84 | 0.89 | 1.00 | 1.4 |
| 23 | vi | easy | ✅ | ✅ | ✅ | 1.00 | 0.66 | 0.80 | 1.00 | 2.5 |
| 24 | en | medium | ✅ | ✅ | ✅ | 1.00 | 0.83 | 1.00 | 1.00 | 3.2 |
| 25 | vi | medium | ✅ | ✅ | ✅ | 1.00 | 0.81 | 0.50 | 1.00 | 3.1 |
| 26 | en | easy | ✅ | ✅ | ✅ | 1.00 | 0.76 | 1.00 | 1.00 | 2.6 |
| 27 | vi | medium | ✅ | ✅ | ✅ | 1.00 | 0.78 | 0.92 | 0.67 | 3.4 |
| 28 | en | medium | ✅ | ✅ | ✅ | 1.00 | 0.86 | 0.83 | 1.00 | 2.7 |
| 29 | en | medium | ✅ | ✅ | ✅ | 1.00 | 0.93 | 1.00 | 1.00 | 2.7 |
| 30 | vi | medium | ✅ | ✅ | ✅ | 1.00 | 0.96 | 1.00 | - | 2.7 |
| 31 | vi | easy | ✅ | ✅ | ✅ | - | 0.83 | 0.95 | 1.00 | 2.6 |
| 32 | en | medium | ✅ | ✅ | ✅ | 1.00 | 0.89 | 1.00 | 1.00 | 2.7 |
| 33 | vi | easy | ✅ | ✅ | ✅ | 0.83 | 0.99 | 0.33 | 1.00 | 4.1 |
| 34 | vi | easy | ✅ | ✅ | ✅ | 1.00 | 0.89 | 0.76 | 1.00 | 1.1 |
| 35 | en | medium | ✅ | ✅ | ✅ | 1.00 | 0.87 | 0.81 | 1.00 | 2.1 |
| 36 | vi | hard | ✅ | ✅ | ✅ | 1.00 | 0.93 | 1.00 | - | 2.9 |
| 37 | vi | easy | ✅ | ✅ | ✅ | 1.00 | 0.85 | 1.00 | 1.00 | 2.9 |
| 38 | en | easy | ✅ | ✅ | ✅ | 1.00 | - | 0.70 | 1.00 | 2.4 |
| 39 | vi | easy | ❌ | ✅ | ❌ | - | - | - | - | 2.1 |
| 40 | vi | easy | ✅ | ✅ | ✅ | 1.00 | 0.82 | 1.00 | 1.00 | 2.5 |
| 41 | en | easy | ✅ | ✅ | ❌ | 1.00 | 0.93 | 1.00 | 1.00 | 2.3 |
| 42 | vi | medium | ✅ | ✅ | ✅ | 1.00 | 0.60 | 0.80 | 1.00 | 2.9 |
| 43 | vi | easy | không biết ✅ | - | - | - | - | - | - | 2.3 |
| 44 | vi | easy | không biết ✅ | - | - | - | - | - | - | 2.0 |
| 45 | vi | easy | không biết ✅ | - | - | - | - | - | - | 37.4 |
| 46 | vi | medium | không biết ✅ | - | - | - | - | - | - | 2.7 |
| 47 | vi | easy | không biết ✅ | - | - | - | - | - | - | 2.2 |
| 48 | en | easy | không biết ✅ | - | - | - | - | - | - | 2.6 |
| 49 | en | easy | không biết ✅ | - | - | - | - | - | - | 2.3 |
| 50 | en | medium | không biết ✅ | - | - | - | - | - | - | 2.6 |
