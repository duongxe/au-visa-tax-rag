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
| 5 | Hybrid BM25 + RRF + reranker | ✅ |
| 6 | FastAPI + Streamlit + Docker | ✅ (chưa build thử image) |
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

Điểm yếu thấy được: câu ngắn chứa mã visa ("Visa 482 cần bao nhiêu năm kinh nghiệm?") bị kéo sang visa khác vì tìm theo vector không bám chặt con số. Hỏi đầy đủ hơn ("Skills in Demand 482 diện Core Skills…") thì đúng. Đã sửa ở Giai đoạn 5 (BM25 + reranker).

## Trả lời có trích nguồn (Giai đoạn 3)

```bash
python -X utf8 -m src.generation.answer "Bố mẹ tôi muốn sang Úc thăm tôi thì xin visa gì?"
python -X utf8 -m src.generation.answer --show-context "Do I need a TFN to start working?"
python -X utf8 -m src.generation.answer --no-rewrite "..."     # không viết lại câu hỏi
```

Luồng xử lý: **viết lại câu hỏi → tìm kiếm nhiều truy vấn (vector + BM25, RRF) → rerank → prompt → LLM (có dự phòng) → trả lời kèm `[n]`**.

**1. Viết lại câu hỏi** ([query.py](src/retrieval/query.py)). Một LLM nhanh đổi câu hỏi thành 1–3 truy vấn tiếng Anh dùng thuật ngữ chính thức. Câu gốc và từng câu viết lại được tìm riêng (top 20), rồi gộp bằng Reciprocal Rank Fusion. Bước này chỉ để tìm đúng tài liệu; câu trả lời vẫn chỉ dựa trên tài liệu. Nếu mọi LLM lỗi thì tìm bằng câu gốc như cũ.

> Ví dụ lỗi đã sửa: "Bố mẹ tôi muốn sang Úc thăm tôi thì xin visa gì?". Chỉ tìm theo vector thì chữ "bố mẹ" kéo kết quả về các trang **Parent visa** (103, 143, 804: visa định cư), còn trang đúng là **Visitor visa (600) – Sponsored Family stream** nằm ở hạng 14. Reranker bge-reranker-v2-m3 cũng không cứu được, vì trang đúng không có trong top 30 để xếp lại. Sau khi viết lại thành "Visitor visa subclass 600 Tourist stream" / "Sponsored Family visitor visa 600", trang đúng lên hạng 1 và câu trả lời đúng.

**2. Prompt** ([prompt.py](src/generation/prompt.py)). Chỉ dùng nguồn được đưa vào, ghi `[n]` sau mỗi ý, trả lời bằng ngôn ngữ của câu hỏi (tiếng Việt thì giữ tên chính thức tiếng Anh như "visa Student (subclass 500)"). Không có trong nguồn thì trả lời đúng một câu "Tôi không tìm thấy thông tin này trong tài liệu hiện có." / "I don't know…".

**3. Nhiều nhà cung cấp AI, tự chuyển khi lỗi** ([llm.py](src/generation/llm.py)). `LLM_CHAIN` là danh sách `provider:model`, thử lần lượt:

```
gemini:gemini-3.5-flash → gemini:gemini-3.5-flash-lite → gemini:gemini-3.8-flash
→ groq:openai/gpt-oss-120b → mistral:mistral-medium-latest
→ openrouter:google/gemma-4-31b-it:free → openrouter:nvidia/nemotron-3-ultra-550b-a55b:free
→ mistral:mistral-small-latest → deepseek:deepseek-chat → openai:gpt-5-mini → anthropic:claude-haiku-5-5
```

Chuỗi nhanh (viết lại câu hỏi): Gemini 3.5-flash-lite → 3.5-flash → `groq:qwen/qwen3.8-27b` → `groq:openai/gpt-oss-20b` → `mistral:mistral-small-latest` → `openrouter:google/gemma-4-26b-a4b-it:free` → …

- Nhà cung cấp nào chưa có key trong `.env` thì bỏ qua. Hỗ trợ: Gemini, Groq, Mistral, OpenRouter, DeepSeek, OpenAI, Anthropic. Bốn nhà cung cấp đầu đều có gói miễn phí; OpenRouter chỉ dùng model đuôi `:free` (khoảng 20 lượt/phút, 50 lượt/ngày nếu chưa nạp tiền).
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

## Chạy thử (Giai đoạn 6)

Gồm hai phần: **API** FastAPI ([src/api/main.py](src/api/main.py)) giữ model và chỉ mục, và **giao diện** Streamlit ([app/streamlit_app.py](app/streamlit_app.py)) chỉ gọi API.

| Endpoint | Mô tả |
|---|---|
| `GET /health` | Số đoạn tài liệu, ngày tải, chế độ tìm kiếm, các model AI đang có key (không trả về key) |
| `POST /ask` | `{"question": "...", "top_k": 5, "rewrite": true, "mode": "hybrid_rerank"}` → câu trả lời, `found`, nguồn `[n]`, các câu tìm kiếm, model đã trả lời, thời gian |

Hành vi của API:
- Câu hỏi được kiểm tra trước khi xử lý: dài 3–1000 ký tự, `top_k` từ 1 đến 10.
- Khi mọi model AI đều lỗi, API trả 503 kèm một thông báo chung. Chi tiết lỗi của nhà cung cấp, có thể chứa mã tài khoản, chỉ ghi vào log.
- Model và chỉ mục được nạp lúc khởi động. Bước dùng GPU/CPU chạy lần lượt từng yêu cầu, còn lúc chờ LLM thì các yêu cầu chạy song song.

Giao diện là dạng chat:
- Lưu lịch sử hội thoại và có các câu hỏi mẫu.
- Các số `[n]` trong câu trả lời bấm được để mở trang nguồn; mỗi nguồn có đoạn trích.
- Thanh bên cho chọn cách tìm kiếm, số đoạn tài liệu, và bật/tắt bước viết lại câu hỏi.

**Docker** (cần `data/index/` đã build):

```bash
cp .env.example .env        # rồi điền API key (không bị đóng vào image)
docker compose up --build
# API:  http://localhost:8000/docs
# UI:   http://localhost:8501
```

- [Dockerfile](Dockerfile) (API) dùng torch bản CPU. bge-m3 và bge-reranker-v2-m3 được tải sẵn lúc build (chỉ file safetensors), nên khi chạy không cần mạng tới Hugging Face. Chỉ mục `data/index/` được đóng vào image; container chạy bằng user thường và có healthcheck. Image khoảng 6 GB, chủ yếu là model.
- [Dockerfile.ui](Dockerfile.ui) chỉ có Streamlit + requests.
- Thư viện tách ra: [requirements-api.txt](requirements-api.txt) và [requirements-ui.txt](requirements-ui.txt) đã ghim phiên bản; [requirements.txt](requirements.txt) gồm cả hai cộng thêm phần tải dữ liệu và đánh giá.

**Chạy local (không Docker):**

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn src.api.main:app --port 8000
streamlit run app/streamlit_app.py                  # API_URL=http://localhost:8000 (mặc định)
```

## Kết quả đánh giá

Bộ test: 50 câu ([eval/questions.csv](eval/questions.csv)): 30 tiếng Việt, 20 tiếng Anh; 42 câu có đáp án trong tài liệu (kèm đáp án chuẩn và trang nguồn), 8 câu ngoài phạm vi (vé máy bay, tỷ giá, visa Mỹ/Canada…). Chi tiết từng câu: [eval/results.md](eval/results.md). Các lỗi tìm thấy: [KNOWN_ISSUES.md](KNOWN_ISSUES.md).

Giai đoạn 4 (tìm theo vector + viết lại câu hỏi, top 5; kết quả Giai đoạn 5 ở phần dưới):

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

## Tìm kiếm lai + rerank (Giai đoạn 5)

`RETRIEVAL_MODE` trong `.env` chọn một trong ba chế độ (mặc định `hybrid_rerank`), xem [query.py](src/retrieval/query.py):

| Chế độ | Cách làm |
|---|---|
| `vector` | bge-m3 + FAISS cho câu gốc và từng câu viết lại (top 20 mỗi truy vấn), gộp bằng RRF |
| `hybrid` | như trên + BM25 ([bm25.py](src/retrieval/bm25.py)) cho các truy vấn tiếng Anh, tất cả gộp bằng RRF |
| `hybrid_rerank` | lấy 30 đoạn đầu của `hybrid`, chấm bằng cross-encoder bge-reranker-v2-m3 ([rerank.py](src/retrieval/rerank.py)), rồi gộp thứ tự rerank với thứ tự `hybrid` bằng RRF một lần nữa |

Ba lựa chọn rút ra khi thử trên bộ câu hỏi:
- **BM25 chỉ chạy trên truy vấn tiếng Anh.** Tài liệu là tiếng Anh, nên từ tiếng Việt chỉ khớp nhiễu; các câu viết lại tiếng Anh đã mang từ khoá (mã visa, "1 year").
- **Reranker chấm theo điểm cao nhất giữa câu gốc và các câu viết lại.** Câu hỏi tiếng Việt đặt cạnh đoạn tiếng Anh chỉ được chấm khoảng 0.0x, thứ tự gần như ngẫu nhiên.
- **Không dùng riêng điểm reranker.** Gộp hai thứ tự cho kết quả tốt hơn cả hai.

So sánh chỉ phần tìm kiếm, không gọi LLM ([eval/runs/retrieval_compare.md](eval/runs/retrieval_compare.md)): 42 câu có trong tài liệu, tìm bằng cùng các câu viết lại đã lưu, đo hạng của trang nguồn đúng đầu tiên.

| Chế độ | hit@1 | hit@5 | hit@10 | MRR@10 | giây/câu (GPU 4 GB) |
|---|---|---|---|---|---|
| vector | 34 | 41 | 42 | 0.877 | 0.4 |
| hybrid | 31 | 42 | 42 | 0.848 | 0.1 |
| **hybrid_rerank** | 33 | 41 | 42 | **0.880** | 3.0 |
| *(đã thử)* chỉ dùng điểm reranker | 30 | 41 | 41 | 0.822 | 3.0 |

Trên chỉ số tổng, hybrid + rerank chỉ ngang vector. Lý do là phần lớn câu đã tìm đúng từ trước, và mỗi câu chỉ có 1–2 trang được tính là đúng. Khác biệt nằm ở các câu khó:
- **Lên hạng:** #10 "Visa 482 cần bao nhiêu năm kinh nghiệm?" từ hạng 6 lên 1; #19 (visa 444), #33 (Medicare levy), #36 (thuế khi bán nhà) cũng lên.
- **Tụt hạng:** #31 (hạn nộp tờ khai) từ hạng 1 xuống 7, xem [KNOWN_ISSUES.md](KNOWN_ISSUES.md).

Chạy lại toàn bộ 50 câu với `hybrid_rerank` ([eval/results.md](eval/results.md); lần chạy Giai đoạn 4 giữ ở [eval/runs/phase4_vector/](eval/runs/phase4_vector/results.md)):

| Chỉ số | Giai đoạn 4 (vector) | Giai đoạn 5 (hybrid + rerank) |
|---|---|---|
| Trả lời được (câu có trong tài liệu) | 39/42 | **42/42** |
| Nói "không biết" đúng (câu ngoài tài liệu) | 8/8 | 8/8 |
| Trích dẫn đúng trang nguồn | 38/42 | **40/42** |
| Trả lời đúng ngôn ngữ câu hỏi | 36/50 | 34/50 (chưa sửa, KNOWN_ISSUES mục A) |
| Thời gian trả lời (trung vị) | 2.8 giây | 5.5 giây |

Ba câu trước đây không trả lời được (#10 visa 482, #19 visa 444, #39 nghỉ phép casual) giờ trả lời đúng và có trích nguồn.

**Điểm RAGAS chưa so được:** Gemini và Groq hết lượt miễn phí trong ngày khi đang chấm, nên mới có điểm faithfulness cho 6/42 câu và context recall cho 6/42 câu. `eval/results.md` ghi số câu đã chấm cạnh mỗi điểm. Chạy lại `python -X utf8 -m src.evaluation.ragas_eval --workers 1` khi có lượt mới; cache sẽ giữ lại các điểm đã chấm.

```bash
python -X utf8 -m src.evaluation.retrieval_eval      # so sánh 3 chế độ tìm kiếm, không tốn lượt LLM
python -X utf8 -m src.retrieval.bm25 "subclass 482 work experience"   # thử BM25 riêng
```

## Hạn chế đã biết

- Các trang visa lặp lại nhiều đoạn chung (nộp giấy tờ, dịch thuật, người đại diện…): 43% số mục của Home Affairs trùng y hệt mục ở trang khác (ATO: 5%). Cần lọc trùng ở bước chunking để không làm loãng kết quả tìm kiếm.
- Reranker làm thời gian trả lời tăng gấp đôi (trung vị 2,8 → 5,5 giây trên GPU 4 GB).
- Các model Gemini Flash hay bị quá tải (503/504) vào giờ cao điểm; nên thêm ít nhất một key dự phòng (Groq, Mistral, OpenRouter đều có gói miễn phí).
- Bảng trong PDF (ví dụ bảng tóm tắt quyền lợi casual) bị tách thành nhiều mục nhỏ.
- Phí visa trên trang Home Affairs được tính bằng JavaScript nên không có trong dữ liệu.
