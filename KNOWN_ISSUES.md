# Các lỗi đã biết (để sửa sau)

Ghi lại trong lúc làm, xếp theo mức ảnh hưởng. Mỗi mục có: hiện tượng, nguyên nhân, cách sửa gợi ý.
Kết quả đánh giá chi tiết: [eval/results.md](eval/results.md).

## Trả lời (ưu tiên sửa trước)

### A. Hỏi tiếng Anh nhưng trả lời bằng tiếng Việt (14/20 câu tiếng Anh)
- **Hiện tượng**: trong lần đánh giá, `gemini-3.5-flash-lite` trả lời bằng tiếng Việt cho 14/20 câu hỏi tiếng Anh (ví dụ #5, #7, #38). Nội dung và trích dẫn vẫn đúng, chỉ sai ngôn ngữ.
- **Nguyên nhân (dự đoán)**: `SYSTEM` trong `src/generation/prompt.py` có câu "(many are Vietnamese)" và quy tắc 4 nói nhiều về tiếng Việt; model nhỏ bám theo đó thay vì ngôn ngữ câu hỏi. Các câu do `gemini-3.5-flash` trả lời (4 câu đầu) không bị.
- **Cách sửa**: trong `build_prompt`, dùng `detect_lang(question)` và ghi rõ ở cuối prompt: "Answer in English." / "Trả lời bằng tiếng Việt."; bỏ "(many are Vietnamese)". Chạy lại `python -X utf8 -m src.evaluation.run_answers --fresh` để kiểm tra.

### B. Trả lời đúng nhưng quên trích nguồn bị tính là "không biết"
- **Hiện tượng**: câu #39 ("Nhân viên casual có được nghỉ phép năm có lương không?") được trả lời đúng ("Không...") nhưng không có [n], nên `found=False`, API không trả nguồn nào.
- **Nguyên nhân**: `answer.py` coi câu trả lời không có trích dẫn là câu "không biết".
- **Cách sửa**: so sánh với câu `NOT_FOUND` thay vì chỉ đếm trích dẫn; nếu trả lời mà không trích dẫn thì gọi lại model một lần yêu cầu thêm [n], hoặc gắn tất cả nguồn đã lấy về.

### B2. Có đoạn đúng nhưng vẫn nói "không tìm thấy"
- **Hiện tượng**: #19 ("Are New Zealand citizens automatically granted a Special Category visa 444?"): 2/5 đoạn lấy về là trang visa 444, nhưng model (Flash-Lite) trả lời "không có thông tin", lại bằng tiếng Việt.
- **Cách sửa**: xem lại sau khi sửa mục A; thử model lớn hơn cho bước trả lời, hoặc tăng k.

### C. Bước viết lại câu hỏi đôi khi dùng tên cũ hoặc dịch sai
- **Hiện tượng**: #10 (visa 482) được viết lại thành "Temporary Skill Shortage visa subclass 482" (tên cũ, trang hiện tại gọi là "Skills in Demand"), kéo kết quả sang visa 186/187. #39 có truy vấn tiếng Việt vô nghĩa "lãnh đạo làm việc casual...".
- **Cách sửa**: thêm vào `REWRITE_SYSTEM` yêu cầu chỉ viết tiếng Anh và dùng tên hiện hành; quan trọng hơn là BM25 (mục 3) để không phụ thuộc vào cách viết lại.

## Dữ liệu

### 1. Giá visa bị mất khi tải trang Home Affairs
- **Hiện tượng**: các đoạn tài liệu ghi "The visa costs from for the main applicant", "This visa costs from: - for a visa of up to 3 years" nhưng không có con số. Có 9 đoạn bị như vậy, ví dụ visa 500, 870, 602. Hỏi "visa 500 bao nhiêu tiền" thì hệ thống không trả lời được hoặc trả lời thiếu số tiền.
- **Nguyên nhân**: giá được trang web chèn bằng JavaScript (lấy từ Visa Pricing Estimator) nên khi tải HTML tĩnh không có số.
- **Cách sửa**: (a) tải trang bằng trình duyệt headless (Playwright) cho các trang visa, hoặc (b) lấy bảng giá từ trang "Visa pricing" của Home Affairs và nối vào từng visa, hoặc (c) ít nhất thêm vào prompt: hỏi về phí thì hướng người dùng tới Visa Pricing Estimator.

### 2. Dữ liệu có hạn (chụp tại một thời điểm)
- **Hiện tượng**: lương tối thiểu, ngưỡng thuế, quy định visa thay đổi theo năm (ví dụ quy định mới cho visa 500/590 từ 2/10/2026, lương tối thiểu từ 1/7/2026).
- **Cách sửa**: lên lịch tải lại dữ liệu (ví dụ mỗi tháng), ghi ngày tải (`downloaded_at` đã có trong `sources.csv`) vào câu trả lời.

## Tìm kiếm (retrieval)

### 3. Câu "Visa 482 cần bao nhiêu năm kinh nghiệm?" lấy sai đoạn
- **Hiện tượng**: tìm kiếm bằng vector (bge-m3) không đưa đoạn "Have worked in your nominated occupation ... for at least 1 year" của visa 482 vào top 5.
- **Nguyên nhân**: câu hỏi ngắn, tìm kiếm vector bỏ lỡ từ khoá cụ thể ("482", "1 year").
- **Cách sửa**: Giai đoạn 5, thêm BM25 (tìm theo từ khoá) và gộp với RRF, sau đó rerank.

### 4. Câu bố mẹ sang thăm trả lời visa 870 thay vì 600 khi chỉ chạy bằng Groq
- **Hiện tượng**: khi Gemini không dùng được, bước viết lại câu hỏi bằng `groq:openai/gpt-oss-20b` chỉ sinh truy vấn về "Parent visa", nên câu trả lời là visa 870 (đúng nhưng thiếu visa 600).
- **Đã làm**: đưa `groq:qwen/qwen3.8-27b` lên trước trong chuỗi viết lại câu hỏi; khi thử riêng Qwen viết đúng "visitor visa subclass 600".
- **Còn lại**: chưa chạy lại toàn bộ câu này chỉ bằng Groq sau khi đổi. Kiểm tra lại bằng `LLM_CHAIN` và `LLM_FAST_CHAIN` chỉ chứa Groq.

## Model ngôn ngữ (LLM)

### 5. Gemini Flash hay quá tải, trả lời chậm
- **Hiện tượng**: lỗi 503/504 ("overloaded"), có câu mất 20-40 giây. `gemini-2.5-flash` báo "no longer available to new users".
- **Đã làm**: tắt retry của SDK, đặt timeout 45 giây, chuỗi dự phòng và thời gian tạm bỏ qua (cooldown).
- **Hết lượt miễn phí trong ngày**: khi chạy đánh giá, `gemini-3.5-flash` báo 429 "exceeded your current quota" sau khoảng 4 câu hỏi; 46/50 câu còn lại do `gemini-3.5-flash-lite` trả lời. Kết quả đánh giá vì vậy chủ yếu đo Flash-Lite.
- **Cách sửa thêm**: đưa `gemini-3.5-flash-lite` lên đầu nếu chất lượng đủ (nhanh hơn nhiều), hoặc dùng key trả phí.

### 6. Groq gói miễn phí bị giới hạn token mỗi phút
- **Hiện tượng**: hỏi liên tục khoảng 3 câu là bị lỗi 429 với `openai/gpt-oss-120b`; Qwen báo "Request too large" khi phải trả lời với 5 đoạn tài liệu.
- **Đã làm**: tạm bỏ qua 60 giây khi gặp giới hạn theo phút; Qwen chỉ dùng để viết lại câu hỏi.
- **Lưu ý**: Groq chỉ hợp làm dự phòng.

### 7. `gpt-oss-120b` với `reasoning_effort=low` trả lời tiếng Việt kém
- **Hiện tượng**: sai chính tả ("siêuannuation"), sai nội dung, hỏi tiếng Việt lại trả lời tiếng Anh.
- **Đã làm**: chỉ đặt `low` cho `gpt-oss-20b` (dùng để viết lại câu hỏi).

## Môi trường / thư viện

### 8. Cài RAGAS đã hạ phiên bản `openai` từ 3.57.0 xuống 1.109.1
- **Hiện tượng**: `pip install ragas` kéo theo `langchain-openai`, yêu cầu `openai<2`, nên `openai` bị hạ cấp.
- **Ảnh hưởng**: code gọi Groq/OpenRouter/DeepSeek/OpenAI dùng `chat.completions.create`, vẫn chạy được ở bản 1.x; chưa thử lại với key OpenAI thật.
- **Cách sửa**: tách môi trường đánh giá (requirements-eval.txt) khỏi môi trường chạy app, hoặc ghim phiên bản (`pip freeze`) trước khi deploy (Giai đoạn 6-7).

### 9. `requirements.txt` chưa ghim phiên bản
- **Cách sửa**: `pip freeze` khi đã chạy ổn, trước khi build Docker.

## Đánh giá

### 10. Model chấm điểm cùng họ với model trả lời
- **Hiện tượng**: RAGAS dùng Gemini để chấm câu trả lời cũng do Gemini viết, có thể chấm dễ hơn thực tế.
- **Cách sửa**: đặt `EVAL_CHAIN` sang model khác (ví dụ Groq `gpt-oss-120b` hoặc Claude) khi có key, so sánh điểm.

### 11. Bộ câu hỏi nhỏ và do một người soạn
- 50 câu (42 có trong tài liệu, 8 ngoài tài liệu). Đáp án chuẩn soạn từ chính tài liệu nên chưa đo được câu hỏi kiểu người dùng thật (viết tắt, sai chính tả, hỏi nhiều ý).
