# au-visa-tax-rag

Trợ lý hỏi đáp (RAG) về **visa, thuế và quyền lợi lao động tại Úc**, hỏi được bằng tiếng Việt lẫn tiếng Anh, trả lời có trích nguồn từ tài liệu chính phủ (homeaffairs.gov.au, ato.gov.au, fairwork.gov.au).

> ⚠️ **Không phải tư vấn di trú, thuế hay pháp lý.** Thông tin có thể đã cũ. Hãy kiểm tra lại trên trang chính thức hoặc hỏi registered migration agent / tax agent.

> 📅 Dữ liệu tính đến ngày: **22/11/2026** (ngày tải từng tài liệu ghi trong `sources.csv`)

## Trạng thái

| Giai đoạn | Nội dung | Trạng thái |
|---|---|---|
| 0 | Repo, cấu trúc, nguồn tài liệu | ✅ |
| 1 | Thu thập + làm sạch dữ liệu | ✅ |
| 2 | Chunking, embedding (bge-m3), FAISS | ✅ |
| 3 | Sinh câu trả lời có trích nguồn (baseline) | ✅ |
| 4 | Bộ 50 câu hỏi + RAGAS | ✅ |
| 5 | Hybrid BM25 + RRF + reranker | ⬜ |
| 6 | FastAPI + Streamlit + Docker | ⬜ |
| 7 | Deploy AWS App Runner | ⬜ |
| 8 | Hoàn thiện README, demo | ⬜ |

## Cấu trúc

```
data/raw/          # HTML/PDF tải về (không commit)
data/processed/    # JSON đã làm sạch + metadata
src/ingest/        # tải và làm sạch tài liệu
src/retrieval/     # chunking, embedding, FAISS, BM25, rerank
data/index/        # chunks.jsonl + faiss.index (build lại được, không commit)
src/generation/    # prompt + gọi Gemini, trích nguồn [n]
src/api/           # FastAPI (/ask)
app/               # Streamlit UI
eval/              # câu hỏi test + script RAGAS, results.md
sources.csv        # danh sách nguồn: url, tiêu đề, ngày tải
```

## Dữ liệu

1.466 tài liệu (~10,7 triệu ký tự, 18.852 mục) từ 3 trang chính phủ:

| Nguồn | Số tài liệu | Phạm vi |
|---|---|---|
| immi.homeaffairs.gov.au | 270 | Toàn bộ `/visas/getting-a-visa/visa-listing/`: mọi loại visa và các diện (stream) con |
| ato.gov.au | 1.185 | Toàn bộ `/individuals-and-families/` (bỏ trang theo năm cũ như hướng dẫn myTax 2016–2024) + thuế suất, ngưỡng super |
| fairwork.gov.au | 11 | Lương tối thiểu, quyền của người có visa, PALM & chương trình lao động Việt Nam, casual, payslip, nghỉ phép (gồm 4 PDF) |

ATO theo chủ đề: khấu trừ & hồ sơ (398), khai thuế (202), super (193), đầu tư & tài sản (165), khó khăn tài chính (42), việc làm (39), thanh toán ATO (37), đến/rời Úc (31), Medicare (23), TFN (19), thuế suất (13), khác (23).

`sources.csv` có 1.609 URL. 143 URL không có trong dữ liệu: 51 trang lỗi 401/404 (ghi `not found` ở cột `notes`), 11 trang có bố cục chưa hỗ trợ (đăng ký ballot, gia hạn TPV/SHEV), còn lại là trang mục lục chỉ có link (< 300 ký tự).

Mỗi tài liệu được lưu thành `data/processed/<doc_id>.json`:

```json
{
  "doc_id": "ato-working-holiday-makers",
  "title": "Working holiday makers",
  "url": "https://www.ato.gov.au/...",
  "site": "ato.gov.au",
  "doc_type": "html",
  "downloaded_at": "2026-11-22",
  "sections": [{"heading": "Tax withheld by your employer", "page": null, "text": "..."}]
}
```

`heading` là đường dẫn mục (ví dụ `Eligibility > Be a genuine student`), `page` là số trang với PDF. Hai trường này dùng để trích nguồn.

Tải và làm sạch lại dữ liệu:

```bash
python -m src.ingest.discover        # dựng lại sources.csv từ menu visa + sitemap ATO
python -m src.ingest.fetch           # tải file còn thiếu vào data/raw/ (--force để tải lại hết, ~45 phút)
python -m src.ingest.clean           # làm sạch -> data/processed/, in thống kê từng tài liệu
```

Ghi chú kỹ thuật:
- Trang visa của Home Affairs là ứng dụng Angular: nội dung không nằm trong HTML mà trong JSON ẩn (`PageSchemaHiddenField`) hoặc trong `div` `RichHtmlField`. `clean.py` đọc thẳng các nguồn này.
- ATO và Fair Work dùng `trafilatura` (chế độ `favor_recall` để giữ heading). PDF dùng `pymupdf`, tách mục theo cỡ chữ và giữ số trang.

## Tìm kiếm (Giai đoạn 2)

```bash
python -m src.retrieval.build_index      # chunk + embed bằng bge-m3 -> data/index/ (~5 phút trên RTX 3050 4 GB)
python -X utf8 -m src.retrieval.search "Du học sinh visa 500 được đi làm bao nhiêu giờ một tuần?"
```

- **Chunking** (`chunk.py`): theo từng mục của tài liệu. Mục nhỏ được gộp đến ≥ 400 token, mục dài bị cắt theo đoạn/câu, tối đa 550 token, overlap 80 token. Đếm token bằng tokenizer của bge-m3. Không gộp qua trang PDF khác để số trang trích dẫn luôn đúng. Mỗi chunk giữ `doc_id, title, url, site, headings, page`.
- **Lọc trùng**: mục có nội dung y hệt mục đã gặp ở tài liệu trước bị bỏ, chỉ giữ 1 bản (Fair Work → ATO → Home Affairs). Đã bỏ 5.213 / 18.852 mục, phần lớn là đoạn chung trên các trang visa.
- **Kết quả**: 5.564 chunk (ATO 3.761, Home Affairs 1.737, Fair Work 66), trung vị 419 token, p90 525, max 561.
- **Embedding**: `BAAI/bge-m3` (đa ngôn ngữ, 1024 chiều, fp16 trên GPU). Vector được chuẩn hoá, FAISS `IndexFlatIP` (= cosine). Văn bản đem embed = `tiêu đề > heading` + nội dung chunk.

Thử nhanh (top 1):

| Câu hỏi | Top 1 |
|---|---|
| Du học sinh visa 500 được đi làm bao nhiêu giờ một tuần? | Student visa (500) › When you have this visa › In Australia |
| Người có visa working holiday phải đóng thuế bao nhiêu? | Tax rates – working holiday maker |
| Làm sao để xin mã số thuế TFN? | What is a tax file number? |
| Khi rời Úc tôi có rút được tiền super không? | Returning to your home country › Claiming your super (top 2) |
| Lương tối thiểu ở Úc là bao nhiêu? | Fair Work: Minimum rates of pay |
| Can I claim my laptop as a work deduction? | Computers, laptops and software › Eligibility |

Điểm yếu thấy được: câu ngắn chứa mã visa ("Visa 482 cần bao nhiêu năm kinh nghiệm?") bị kéo sang visa khác vì tìm theo vector không bám chặt con số. Hỏi đầy đủ hơn ("Skills in Demand 482 diện Core Skills…") thì đúng. Giai đoạn 5 (BM25 + reranker) nhắm vào lỗi này.

## Trả lời có trích nguồn (Giai đoạn 3)

```bash
python -X utf8 -m src.generation.answer "Bố mẹ tôi muốn sang Úc thăm tôi thì xin visa gì?"
python -X utf8 -m src.generation.answer --show-context "Do I need a TFN to start working?"
python -X utf8 -m src.generation.answer --no-rewrite "..."     # không viết lại câu hỏi
```

Luồng xử lý: **viết lại câu hỏi → tìm kiếm nhiều truy vấn (RRF) → prompt → LLM (có dự phòng) → trả lời kèm `[n]`**.

**1. Viết lại câu hỏi** ([query.py](src/retrieval/query.py)). Một LLM nhanh đổi câu hỏi thành 1–3 truy vấn tiếng Anh dùng thuật ngữ chính thức. Câu gốc và từng câu viết lại được tìm riêng (top 20), rồi gộp bằng Reciprocal Rank Fusion. Bước này chỉ để tìm đúng tài liệu; câu trả lời vẫn chỉ dựa trên tài liệu. Nếu mọi LLM lỗi thì tìm bằng câu gốc như cũ.

> Ví dụ lỗi đã sửa: "Bố mẹ tôi muốn sang Úc thăm tôi thì xin visa gì?". Chỉ tìm theo vector thì chữ "bố mẹ" kéo kết quả về các trang **Parent visa** (103, 143, 804: visa định cư), còn trang đúng là **Visitor visa (600) – Sponsored Family stream** nằm ở hạng 14. Reranker bge-reranker-v2-m3 cũng không cứu được, vì trang đúng không có trong top 30 để xếp lại. Sau khi viết lại thành "Visitor visa subclass 600 Tourist stream" / "Sponsored Family visitor visa 600", trang đúng lên hạng 1 và câu trả lời đúng.

**2. Prompt** ([prompt.py](src/generation/prompt.py)). Chỉ dùng nguồn được đưa vào, ghi `[n]` sau mỗi ý, trả lời bằng ngôn ngữ của câu hỏi (tiếng Việt thì giữ tên chính thức tiếng Anh như "visa Student (subclass 500)"). Không có trong nguồn thì trả lời đúng một câu "Tôi không tìm thấy thông tin này trong tài liệu hiện có." / "I don't know…".

**3. Nhiều nhà cung cấp AI, tự chuyển khi lỗi** ([llm.py](src/generation/llm.py)). `LLM_CHAIN` là danh sách `provider:model`, thử lần lượt:

```
gemini:gemini-3.5-flash → gemini:gemini-3.5-flash-lite → gemini:gemini-3.8-flash
→ groq:openai/gpt-oss-120b → openrouter:openai/gpt-oss-120b → deepseek:deepseek-chat
→ openai:gpt-5-mini → anthropic:claude-haiku-5-5
```

Chuỗi nhanh (viết lại câu hỏi): Gemini 3.5-flash-lite → 3.5-flash → `groq:qwen/qwen3.8-27b` → `groq:openai/gpt-oss-20b` → …

- Nhà cung cấp nào chưa có key trong `.env` thì bỏ qua. Hỗ trợ: Gemini, Groq, OpenRouter, DeepSeek, OpenAI, Anthropic.
- Gặp bất kỳ lỗi nào (503 quá tải, 429 hết lượt, hết credit, sai key, timeout 45 giây) thì chuyển ngay sang bước sau. Bước lỗi bị đẩy xuống cuối hàng: 5 phút nếu quá tải, 1 giờ nếu lỗi tài khoản (401/402/403, quota, credit, billing).
- `LLM_FAST_CHAIN` là chuỗi riêng cho việc viết lại câu hỏi, ưu tiên model rẻ và nhanh.
- Kết quả có trường `model`, cho biết nhà cung cấp nào đã trả lời.
- Lỗi giới hạn theo phút (gói miễn phí của Groq) chỉ tạm bỏ 60 giây.

Ghi chú khi thử Groq (gói miễn phí):
- `gpt-oss-120b` trả lời tiếng Việt tốt, 2–15 giây. Giới hạn token mỗi phút thấp, nên hỏi liên tục 3 câu là bị 429; Groq hợp làm dự phòng, không hợp làm model chính.
- `gpt-oss-20b` đôi khi dùng hết `max_tokens` cho phần suy nghĩ và trả về rỗng → đặt `reasoning_effort=low`. Không đặt cho 120b: với mức thấp, câu trả lời tiếng Việt kém hẳn (sai chính tả, sai nội dung, trả lời tiếng Anh cho câu hỏi tiếng Việt).
- `qwen3.8-27b` viết lại câu hỏi tốt hơn `gpt-oss-20b` (ví dụ câu bố mẹ: ra "visitor visa subclass 600" thay vì "Parent visa 103"), nhưng không dùng để trả lời: prompt ~4.000 token + 2.048 token trả lời vượt giới hạn mỗi phút của model này ("request too large").

Kết quả trả về: `answer`, `found` (false khi không có trích dẫn = câu "không biết"), `sources` (chỉ những nguồn được trích), `contexts` (cả 5 chunk, dùng cho RAGAS ở giai đoạn 4), `queries`, `model`. API: `POST /ask {"question": "...", "top_k": 5, "rewrite": true}`.

Thử nhanh:

| Câu hỏi | Kết quả |
|---|---|
| Du học sinh visa 500 được đi làm bao nhiêu giờ một tuần? | 48 giờ / 2 tuần khi khoá học đang diễn ra, không giới hạn khi nghỉ, không giới hạn với thạc sĩ nghiên cứu / tiến sĩ [1–4] |
| Lương tối thiểu ở Úc là bao nhiêu? | $26.44/giờ, $1004.90/tuần từ 1/7/2026; casual $33.05 [1–3] |
| Khi rời Úc tôi có rút được tiền super không? | DASP cho visa tạm trú, điều kiện, ngoại lệ NZ và PR [1][2][4] |
| Do I need a TFN to start working in Australia? | Không bắt buộc nhưng bị khấu trừ thuế cao nhất nếu sau 28 ngày chưa nộp [1][2][4] |
| Giá vé máy bay từ Hà Nội sang Sydney là bao nhiêu? | "Tôi không tìm thấy thông tin này…" ✅ |
| What is the capital gains tax rate in New Zealand? | "I don't know…" ✅ |
| Bố mẹ tôi muốn sang Úc thăm tôi thì xin visa gì? | Trước: "không tìm thấy" ❌. Sau khi thêm bước viết lại câu hỏi: Visitor visa (600) Sponsored Family stream (cần người bảo lãnh, Form 1149) hoặc Tourist stream ✅ |

## Chạy thử

```bash
cp .env.example .env        # rồi điền API key
docker compose up --build
# API:  http://localhost:8000/docs
# UI:   http://localhost:8501
```

Hoặc chạy local:

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn src.api.main:app --reload
streamlit run app/streamlit_app.py
```

## Kết quả đánh giá

Bộ test: 50 câu ([eval/questions.csv](eval/questions.csv)): 30 tiếng Việt, 20 tiếng Anh; 42 câu có đáp án trong tài liệu (kèm đáp án chuẩn và trang nguồn), 8 câu ngoài phạm vi (vé máy bay, tỷ giá, visa Mỹ/Canada…). Chi tiết từng câu: [eval/results.md](eval/results.md). Các lỗi tìm thấy: [KNOWN_ISSUES.md](KNOWN_ISSUES.md).

Baseline (Giai đoạn 3: tìm theo vector + viết lại câu hỏi, top 5):

| Chỉ số | Kết quả |
|---|---|
| Trả lời được (câu có trong tài liệu) | 39/42 (93%) |
| Nói "không biết" đúng (câu ngoài tài liệu) | 8/8 (100%) |
| Retrieval hit@5 (trang nguồn đúng nằm trong 5 đoạn lấy về) | 41/42 (98%) |
| Trích dẫn đúng trang nguồn | 38/42 (90%) |
| Trả lời đúng ngôn ngữ câu hỏi | 36/50 (72%): lỗi, xem KNOWN_ISSUES mục A |
| RAGAS faithfulness / answer relevancy | 0.96 / 0.84 |
| RAGAS context precision / context recall | 0.86 / 0.93 |
| Thời gian trả lời (trung vị) | 2.8 giây |

Gemini Flash hết lượt miễn phí sau 4 câu nên 40/50 câu do `gemini-3.5-flash-lite` trả lời (5 câu Flash, 5 câu Groq). Model chấm RAGAS đi qua cùng chuỗi dự phòng (chủ yếu Flash-Lite, một phần Groq `gpt-oss-120b`), cùng họ với model trả lời nên điểm có thể hơi cao.

Chạy lại:

```bash
python -X utf8 -m src.evaluation.run_answers --fresh   # trả lời 50 câu -> eval/runs/answers.jsonl
python -X utf8 -m src.evaluation.ragas_eval            # chấm RAGAS -> eval/runs/ragas_scores.csv
python -X utf8 -m src.evaluation.report                # -> eval/results.md
```

Giai đoạn 5 sẽ so sánh: vector vs hybrid (BM25 + RRF) vs hybrid + rerank trên cùng bộ câu hỏi.

## Hạn chế đã biết

- Các trang visa lặp lại nhiều đoạn chung (nộp giấy tờ, dịch thuật, người đại diện…): 43% số mục của Home Affairs trùng y hệt mục ở trang khác (ATO: 5%). Cần lọc trùng ở bước chunking để không làm loãng kết quả tìm kiếm.
- Câu ngắn có mã visa ("Visa 482 cần bao nhiêu năm kinh nghiệm?") vẫn tìm sai, kể cả khi viết lại câu hỏi: tìm theo vector không bám con số → cần BM25 (giai đoạn 5).
- Các model Gemini Flash hay bị quá tải (503/504) vào giờ cao điểm; nên thêm ít nhất một key dự phòng (Groq/OpenRouter có gói miễn phí).
- Bảng trong PDF (ví dụ bảng tóm tắt quyền lợi casual) bị tách thành nhiều mục nhỏ.
- Phí visa trên trang Home Affairs được tính bằng JavaScript nên không có trong dữ liệu.
