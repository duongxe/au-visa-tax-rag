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
| 3 | Sinh câu trả lời có trích nguồn (baseline) | ⬜ |
| 4 | Bộ 50 câu hỏi + RAGAS | ⬜ |
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
src/generation/    # prompt + gọi LLM
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

_(Sẽ điền ở giai đoạn 4–5: vector-only vs hybrid vs hybrid + rerank.)_

## Hạn chế đã biết

- Các trang visa lặp lại nhiều đoạn chung (nộp giấy tờ, dịch thuật, người đại diện…): 43% số mục của Home Affairs trùng y hệt mục ở trang khác (ATO: 5%). Cần lọc trùng ở bước chunking để không làm loãng kết quả tìm kiếm.
- Bảng trong PDF (ví dụ bảng tóm tắt quyền lợi casual) bị tách thành nhiều mục nhỏ.
- Phí visa trên trang Home Affairs được tính bằng JavaScript nên không có trong dữ liệu.
