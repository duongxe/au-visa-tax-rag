# Kết quả đánh giá / Evaluation results

Chạy ngày 2026-11-23 trên 50 câu hỏi (42 có trong tài liệu, 8 ngoài tài liệu; 30 tiếng Việt, 20 tiếng Anh). Câu hỏi và đáp án chuẩn: [questions.csv](questions.csv). Câu trả lời và đoạn tài liệu lấy về: [runs/answers.jsonl](runs/answers.jsonl). Điểm RAGAS từng câu: [runs/ragas_scores.csv](runs/ragas_scores.csv).

## Tổng quan

| Chỉ số | Kết quả |
|---|---|
| Trả lời được (câu có trong tài liệu) | 42/42 (100%) |
| Nói "không biết" đúng (câu ngoài tài liệu) | 8/8 (100%) |
| Retrieval hit@5 (có trang nguồn đúng trong 5 đoạn lấy về) | 41/42 (98%) |
| Trích dẫn đúng trang nguồn | 40/42 (95%) |
| Trả lời đúng ngôn ngữ câu hỏi | 34/50 (68%) |
| Lỗi (mọi LLM đều thất bại) | 0 |
| Thời gian trả lời (trung vị / lâu nhất) | 5.5s / 31.5s |

## RAGAS (42 câu có trong tài liệu và đã được trả lời)

| Nhóm | n | faithfulness | answer_relevancy | context_precision | context_recall |
|---|---|---|---|---|---|
| Tất cả | 42 | 1.00 | 0.82 | 0.89 | 0.94 |
| Tiếng Việt | 25 | 1.00 | 0.79 | 0.94 | 0.92 |
| Tiếng Anh | 17 | 1.00 | 0.88 | 0.83 | 1.00 |
| Độ khó: easy | 18 | 1.00 | 0.82 | 0.85 | 1.00 |
| Độ khó: medium | 20 | 1.00 | 0.86 | 0.93 | 1.00 |
| Độ khó: hard | 4 | 1.00 | 0.74 | 0.91 | 0.67 |

Điểm trống (LLM chấm bị giới hạn lượt, không tính vào trung bình): faithfulness 36/42, answer_relevancy 12/42, context_precision 30/42, context_recall 36/42.

- **faithfulness**: tỷ lệ ý trong câu trả lời có căn cứ trong đoạn tài liệu lấy về (thấp = bịa).
- **answer_relevancy**: câu trả lời có đúng trọng tâm câu hỏi không.
- **context_precision**: đoạn liên quan có được xếp lên đầu không (so với đáp án chuẩn).
- **context_recall**: tỷ lệ ý của đáp án chuẩn tìm thấy trong các đoạn lấy về.

## So với Giai đoạn 4 (chỉ tìm theo vector)

Lần chạy Giai đoạn 4 được giữ nguyên ở [runs/phase4_vector/](runs/phase4_vector/results.md). Model trả lời và model chấm có thể khác giữa hai lần chạy (xem bảng model bên dưới), nên chênh lệch nhỏ ở điểm RAGAS chưa chắc do retrieval.

| Chỉ số | Giai đoạn 4 | Lần này |
|---|---|---|
| Trả lời được (trong tài liệu) | 39/42 (93%) | 42/42 (100%) |
| Nói "không biết" đúng (ngoài tài liệu) | 8/8 (100%) | 8/8 (100%) |
| Retrieval hit@5 | 41/42 (98%) | 41/42 (98%) |
| Trích dẫn đúng trang nguồn | 38/42 (90%) | 40/42 (95%) |
| Đúng ngôn ngữ | 36/50 (72%) | 34/50 (68%) |
| faithfulness | 0.96 (chấm 38/42) | 1.00 (chấm 6/42) |
| answer_relevancy | 0.84 (chấm 38/42) | 0.82 (chấm 30/42) |
| context_precision | 0.86 (chấm 39/42) | 0.89 (chấm 12/42) |
| context_recall | 0.93 (chấm 37/42) | 0.94 (chấm 6/42) |
| Thời gian trung vị | 2.8s | 5.5s |

## Model đã trả lời

| Model | Số câu |
|---|---|
| `gemini:gemini-3.5-flash-lite` | 48 |
| `gemini:gemini-3.5-flash` | 2 |

## Câu cần xem lại

- **#31** Hạn chót nộp tờ khai thuế cá nhân là ngày nào?: không lấy được trang nguồn đúng
- **#7** What is the balance of family test for Parent visas?: sai ngôn ngữ
- **#9** What are the eligibility requirements for the Temporary Graduate visa 485?: sai ngôn ngữ
- **#11** What English test score do I need for the subclass 482 Core Skills stream?: sai ngôn ngữ
- **#16** Can I apply for a Student Guardian visa 590 while in Australia?: sai ngôn ngữ
- **#18** Is the Medical Treatment visa 602 free?: sai ngôn ngữ
- **#19** Are New Zealand citizens automatically granted a Special Category visa 444?: sai ngôn ngữ
- **#21** Who can get a Partner visa (subclass 801)?: sai ngôn ngữ
- **#24** How much tax does a registered WHM employer withhold from a working holiday maker?: sai ngôn ngữ
- **#26** What is the 183-day test?: sai ngôn ngữ
- **#28** What tax rate applies to a DASP for working holiday makers?: sai ngôn ngữ
- **#29** Can I submit my DASP application before leaving Australia?: sai ngôn ngữ
- **#32** What does the fixed rate method for working from home cover?: sai ngôn ngữ
- **#35** When can I access my super early on compassionate grounds?: sai ngôn ngữ
- **#38** What is casual loading?: sai ngôn ngữ
- **#41** Do visa holders have the same workplace rights as Australian workers?: sai ngôn ngữ
- **#50** How many points do I need for Canada Express Entry?: sai ngôn ngữ

## Từng câu

| # | lang | độ khó | trả lời | hit@5 | trích đúng | faith | relev | ctx P | ctx R | giây |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | vi | easy | ✅ | ✅ | ✅ | 1.00 | 0.84 | 1.00 | 1.00 | 31.5 |
| 2 | en | easy | ✅ | ✅ | ✅ | 1.00 | 0.89 | 1.00 | 1.00 | 12.9 |
| 3 | vi | easy | ✅ | ✅ | ✅ | 1.00 | 0.86 | 0.75 | 1.00 | 6.2 |
| 4 | vi | hard | ✅ | ✅ | ✅ | 1.00 | 0.75 | 0.87 | 0.67 | 6.4 |
| 5 | en | easy | ✅ | ✅ | ✅ | 1.00 | 0.77 | 0.75 | 1.00 | 5.4 |
| 6 | vi | medium | ✅ | ✅ | ✅ | 1.00 | 0.72 | 1.00 | 1.00 | 5.8 |
| 7 | en | medium | ✅ | ✅ | ✅ | - | - | 0.76 | - | 7.5 |
| 8 | vi | easy | ✅ | ✅ | ✅ | - | 0.70 | - | - | 5.3 |
| 9 | en | medium | ✅ | ✅ | ✅ | - | - | - | - | 6.4 |
| 10 | vi | hard | ✅ | ✅ | ✅ | - | - | - | - | 6.0 |
| 11 | en | medium | ✅ | ✅ | ✅ | - | - | - | - | 8.3 |
| 12 | vi | easy | ✅ | ✅ | ✅ | - | 0.78 | - | - | 5.2 |
| 13 | vi | easy | ✅ | ✅ | ✅ | - | 0.73 | - | - | 5.6 |
| 14 | vi | medium | ✅ | ✅ | ✅ | - | - | 1.00 | - | 6.2 |
| 15 | vi | medium | ✅ | ✅ | ✅ | - | 0.77 | - | - | 6.7 |
| 16 | en | medium | ✅ | ✅ | ✅ | - | 0.88 | - | - | 6.3 |
| 17 | vi | medium | ✅ | ✅ | ✅ | - | - | - | - | 5.7 |
| 18 | en | medium | ✅ | ✅ | ✅ | - | - | - | - | 5.9 |
| 19 | en | medium | ✅ | ✅ | ✅ | - | 0.91 | - | - | 5.3 |
| 20 | vi | easy | ✅ | ✅ | ✅ | - | 0.75 | - | - | 5.6 |
| 21 | en | medium | ✅ | ✅ | ✅ | - | 0.84 | - | - | 6.0 |
| 22 | vi | hard | ✅ | ✅ | ✅ | - | 0.78 | 0.95 | - | 5.2 |
| 23 | vi | easy | ✅ | ✅ | ❌ | - | 0.78 | - | - | 5.4 |
| 24 | en | medium | ✅ | ✅ | ✅ | - | 0.90 | 0.89 | - | 6.5 |
| 25 | vi | medium | ✅ | ✅ | ✅ | - | - | - | - | 5.0 |
| 26 | en | easy | ✅ | ✅ | ✅ | - | - | - | - | 5.2 |
| 27 | vi | medium | ✅ | ✅ | ✅ | - | 0.80 | - | - | 5.6 |
| 28 | en | medium | ✅ | ✅ | ✅ | - | - | - | - | 5.6 |
| 29 | en | medium | ✅ | ✅ | ✅ | - | 0.95 | - | - | 5.5 |
| 30 | vi | medium | ✅ | ✅ | ✅ | - | 0.95 | 1.00 | - | 5.6 |
| 31 | vi | easy | ✅ | ❌ | ❌ | - | 0.83 | - | - | 4.9 |
| 32 | en | medium | ✅ | ✅ | ✅ | - | 0.89 | - | - | 5.7 |
| 33 | vi | easy | ✅ | ✅ | ✅ | - | 0.77 | - | - | 5.0 |
| 34 | vi | easy | ✅ | ✅ | ✅ | - | 0.82 | - | - | 4.8 |
| 35 | en | medium | ✅ | ✅ | ✅ | - | 0.78 | - | - | 5.0 |
| 36 | vi | hard | ✅ | ✅ | ✅ | - | 0.70 | - | - | 5.6 |
| 37 | vi | easy | ✅ | ✅ | ✅ | - | - | - | - | 5.5 |
| 38 | en | easy | ✅ | ✅ | ✅ | - | 0.89 | 0.76 | - | 4.7 |
| 39 | vi | easy | ✅ | ✅ | ✅ | - | 0.86 | - | - | 5.0 |
| 40 | vi | easy | ✅ | ✅ | ✅ | - | 0.87 | - | - | 5.3 |
| 41 | en | easy | ✅ | ✅ | ✅ | - | 0.93 | - | - | 5.5 |
| 42 | vi | medium | ✅ | ✅ | ✅ | - | - | - | - | 5.2 |
| 43 | vi | easy | không biết ✅ | - | - | - | - | - | - | 4.8 |
| 44 | vi | easy | không biết ✅ | - | - | - | - | - | - | 4.9 |
| 45 | vi | easy | không biết ✅ | - | - | - | - | - | - | 5.4 |
| 46 | vi | medium | không biết ✅ | - | - | - | - | - | - | 5.9 |
| 47 | vi | easy | không biết ✅ | - | - | - | - | - | - | 4.0 |
| 48 | en | easy | không biết ✅ | - | - | - | - | - | - | 4.9 |
| 49 | en | easy | không biết ✅ | - | - | - | - | - | - | 4.9 |
| 50 | en | medium | không biết ✅ | - | - | - | - | - | - | 6.2 |
