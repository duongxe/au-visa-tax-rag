# So sánh retrieval (42 câu có trong tài liệu, câu hỏi gốc + câu viết lại đã lưu)

| Chế độ | hit@1 | hit@5 | hit@10 | MRR@10 | giây/câu |
|---|---|---|---|---|---|
| vector | 34/42 | 41/42 | 42/42 | 0.877 | 0.42 |
| hybrid | 31/42 | 42/42 | 42/42 | 0.848 | 0.10 |
| hybrid_rerank | 33/42 | 41/42 | 42/42 | 0.880 | 3.04 |

## Câu có thứ hạng thay đổi (hạng của trang nguồn đúng đầu tiên, - = ngoài top 10)

| # | câu hỏi | vector | hybrid | hybrid_rerank |
|---|---|---|---|---|
| 2 | Do student visa holders need health insurance? | 1 | 2 | 1 |
| 9 | What are the eligibility requirements for the Temporary Graduate visa 485? | 1 | 5 | 2 |
| 10 | Visa 482 cần bao nhiêu năm kinh nghiệm làm việc? | 6 | 1 | 1 |
| 12 | Visa 189 cần tối thiểu bao nhiêu điểm? | 2 | 1 | 3 |
| 14 | Điều kiện để xin visa Working Holiday 417 lần hai là gì? | 1 | 2 | 2 |
| 17 | Người giám hộ visa 590 cần bảo hiểm y tế như thế nào? | 1 | 1 | 2 |
| 19 | Are New Zealand citizens automatically granted a Special Category visa 444? | 4 | 3 | 2 |
| 25 | Mới sang Úc giữa năm thì ngưỡng miễn thuế tính thế nào? | 4 | 2 | 2 |
| 31 | Hạn chót nộp tờ khai thuế cá nhân là ngày nào? | 1 | 4 | 7 |
| 33 | Người không cư trú thuế có phải đóng Medicare levy không? | 3 | 1 | 1 |
| 35 | When can I access my super early on compassionate grounds? | 1 | 2 | 1 |
| 36 | Người nước ngoài bán nhà ở Úc có bị giữ lại tiền thuế không? | 2 | 2 | 1 |
| 37 | Lương tối thiểu ở Úc hiện nay là bao nhiêu? | 3 | 3 | 2 |
| 42 | Du học sinh bị trả lương thấp thì liên hệ ai? | 1 | 2 | 1 |
