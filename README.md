# au-visa-tax-rag

Trợ lý hỏi đáp (RAG) về **visa, thuế và quyền lợi lao động tại Úc**, hỏi được bằng tiếng Việt lẫn tiếng Anh, trả lời có trích nguồn từ tài liệu chính phủ (homeaffairs.gov.au, ato.gov.au, fairwork.gov.au).

> ⚠️ **Không phải tư vấn di trú, thuế hay pháp lý.** Thông tin có thể đã cũ. Hãy kiểm tra lại trên trang chính thức hoặc hỏi registered migration agent / tax agent.

> 📅 Dữ liệu tính đến ngày: **_(cập nhật sau khi tải dữ liệu, xem `sources.csv`)_**

## Trạng thái

Đang ở giai đoạn 0 (khung dự án). Kế hoạch:

| Giai đoạn | Nội dung | Trạng thái |
|---|---|---|
| 0 | Repo, cấu trúc, nguồn tài liệu | 🟡 |
| 1 | Thu thập + làm sạch dữ liệu | ⬜ |
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

_(Sẽ điền.)_
