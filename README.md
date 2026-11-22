# au-visa-tax-rag

Trợ lý hỏi đáp (RAG) về **visa, thuế và quyền lợi lao động tại Úc**, hỏi được bằng tiếng Việt lẫn tiếng Anh, trả lời có trích nguồn từ tài liệu chính phủ (homeaffairs.gov.au, ato.gov.au, fairwork.gov.au).

> ⚠️ **Không phải tư vấn di trú, thuế hay pháp lý.** Thông tin có thể đã cũ. Hãy kiểm tra lại trên trang chính thức hoặc hỏi registered migration agent / tax agent.

> 📅 Dữ liệu tính đến ngày: **22/11/2026** (ngày tải từng tài liệu ghi trong `sources.csv`)

## Trạng thái

| Giai đoạn | Nội dung | Trạng thái |
|---|---|---|
| 0 | Repo, cấu trúc, nguồn tài liệu | ✅ |
| 1 | Thu thập + làm sạch dữ liệu | ✅ |
| 2 | Chunking, embedding (bge-m3), FAISS | ⬜ |
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
src/generation/    # prompt + gọi LLM
src/api/           # FastAPI (/ask)
app/               # Streamlit UI
eval/              # câu hỏi test + script RAGAS, results.md
sources.csv        # danh sách nguồn: url, tiêu đề, ngày tải
```

## Dữ liệu

40 tài liệu (~770k ký tự) từ 3 trang chính phủ:

| Nguồn | Số tài liệu | Nội dung |
|---|---|---|
| immi.homeaffairs.gov.au | 17 | Visa 500, 485, 417, 462, 189, 190, 491, 482, 600, 820, bảng điểm skilled |
| ato.gov.au | 12 | TFN, cư trú thuế, working holiday maker, khai thuế, Medicare levy, thuế suất, super, DASP |
| fairwork.gov.au | 11 | Lương tối thiểu, quyền của người có visa, PALM & chương trình lao động Việt Nam, casual, payslip, nghỉ phép (gồm 4 PDF) |

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
python -m src.ingest.fetch           # tải file còn thiếu vào data/raw/ (--force để tải lại hết)
python -m src.ingest.clean           # làm sạch -> data/processed/, in thống kê từng tài liệu
```

Ghi chú kỹ thuật:
- Trang visa của Home Affairs là ứng dụng Angular: nội dung không nằm trong HTML mà trong JSON ẩn (`PageSchemaHiddenField`) hoặc trong `div` `RichHtmlField`. `clean.py` đọc thẳng các nguồn này.
- ATO và Fair Work dùng `trafilatura` (chế độ `favor_recall` để giữ heading). PDF dùng `pymupdf`, tách mục theo cỡ chữ và giữ số trang.

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

- Các trang visa lặp lại nhiều đoạn chung (nộp giấy tờ, dịch thuật, người đại diện…). Cần lọc trùng ở bước chunking để không làm loãng kết quả tìm kiếm.
- Bảng trong PDF (ví dụ bảng tóm tắt quyền lợi casual) bị tách thành nhiều mục nhỏ.
- Phí visa trên trang Home Affairs được tính bằng JavaScript nên không có trong dữ liệu.
