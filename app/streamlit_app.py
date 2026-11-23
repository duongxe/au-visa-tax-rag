"""Streamlit chat UI over the FastAPI service (API_URL, default http://localhost:8000).

Usage:
    streamlit run app/streamlit_app.py
"""
from __future__ import annotations

import os
import re

import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000").rstrip("/")
TIMEOUT_S = 180  # the API can try several LLM providers in a row

EXAMPLES = [
    "Du học sinh visa 500 được đi làm bao nhiêu giờ?",
    "Bố mẹ tôi muốn sang Úc thăm tôi thì xin visa gì?",
    "Rời Úc rồi thì rút tiền super như thế nào?",
    "Do working holiday makers pay tax?",
    "Nhân viên casual có được nghỉ phép năm có lương không?",
]
MODES = {"hybrid_rerank": "Hybrid + rerank (chính xác nhất)", "hybrid": "Hybrid (BM25 + vector)",
         "vector": "Chỉ vector"}

st.set_page_config(page_title="Hỏi đáp Visa & Thuế Úc", page_icon="🇦🇺", layout="centered")


@st.cache_data(ttl=60, show_spinner=False)
def health() -> dict | None:
    try:
        r = requests.get(f"{API_URL}/health", timeout=5)
        r.raise_for_status()
        return r.json()
    except requests.RequestException:
        return None


def ask(question: str, top_k: int, mode: str, rewrite: bool) -> dict:
    """Returns the API response, or {"error": message}."""
    try:
        r = requests.post(f"{API_URL}/ask", timeout=TIMEOUT_S,
                          json={"question": question, "top_k": top_k, "mode": mode, "rewrite": rewrite})
    except requests.ConnectionError:
        return {"error": f"Không kết nối được API ({API_URL}). Hãy chạy `uvicorn src.api.main:app` trước."}
    except requests.Timeout:
        return {"error": "API trả lời quá lâu, vui lòng thử lại."}
    if r.status_code == 200:
        return r.json()
    try:
        detail = r.json().get("detail")
    except ValueError:
        detail = r.text[:300]
    return {"error": f"Lỗi {r.status_code}: {detail}"}


def link_citations(answer: str, sources: list[dict]) -> str:
    """Turns [n] into a link to source n, so a citation can be opened in one click."""
    urls = {s["id"]: s["url"] for s in sources}
    return re.sub(r"\[(\d+)\]", lambda m: f"[[{m[1]}]]({urls[int(m[1])]})" if int(m[1]) in urls else m[0],
                  answer)


def render(msg: dict) -> None:
    if "error" in msg:
        st.error(msg["error"])
        return
    st.markdown(link_citations(msg["answer"], msg["sources"]))
    if msg["sources"]:
        st.markdown("**Nguồn / Sources**")
        for s in msg["sources"]:
            where = f" › {s['heading']}" if s.get("heading") and s["heading"] != s["title"] else ""
            page = f" (trang {s['page']})" if s.get("page") else ""
            with st.expander(f"[{s['id']}] {s['title']}{where}{page}"):
                st.markdown(f"[{s['url']}]({s['url']})")
                st.caption(s["snippet"])
    meta = f"{msg['model'] or '-'} · {msg['seconds']:.1f}s"
    if msg.get("show_queries") and len(msg["queries"]) > 1:
        meta += " · tìm với: " + " | ".join(msg["queries"][1:])
    st.caption(meta)


# --- sidebar ---------------------------------------------------------------
with st.sidebar:
    st.header("Cài đặt")
    info = health()
    if info:
        idx = info["index"]
        st.success(f"API sẵn sàng · {idx['chunks']:,} đoạn tài liệu (tải ngày {idx['built_at']})")
        if not info["llm_chain"]:
            st.warning("Chưa có API key nào cho LLM trong .env.")
    else:
        st.error(f"Không kết nối được API: {API_URL}")
    default_mode = (info or {}).get("retrieval_mode", "hybrid_rerank")
    mode = st.selectbox("Cách tìm kiếm", list(MODES), format_func=MODES.get,
                        index=list(MODES).index(default_mode) if default_mode in MODES else 0)
    top_k = st.slider("Số đoạn tài liệu đưa cho AI", 3, 10, 5)
    rewrite = st.toggle("Viết lại câu hỏi để tìm tốt hơn", value=True)
    show_queries = st.toggle("Hiện các câu tìm kiếm", value=False)
    if st.button("Xoá hội thoại", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
    st.divider()
    st.caption("Nguồn: immi.homeaffairs.gov.au, ato.gov.au, fairwork.gov.au. "
               "Mã nguồn: github.com/duongxe/au-visa-tax-rag")

# --- chat ------------------------------------------------------------------
st.title("🇦🇺 Hỏi đáp Visa & Thuế Úc")
st.caption("Trả lời từ trang chính phủ Úc, có trích nguồn. Đây **không** phải tư vấn di trú hay thuế; "
           "luôn kiểm tra lại trên trang chính thức. / Not legal or tax advice.")

if "messages" not in st.session_state:
    st.session_state.messages = []

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        # A plain if/else: a bare expression here would be echoed by Streamlit "magic".
        if m["role"] == "assistant":
            render(m)
        else:
            st.markdown(m["content"])

picked = None
examples = st.empty()  # cleared as soon as a question is asked
if not st.session_state.messages:
    with examples.container():
        st.markdown("**Thử hỏi:**")
        for ex in EXAMPLES:
            if st.button(ex, use_container_width=True):
                picked = ex

question = st.chat_input("Hỏi về visa, thuế, super, quyền lợi lao động (tiếng Việt hoặc English)") or picked
if question:
    examples.empty()
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        with st.spinner("Đang tìm trong tài liệu..."):
            res = ask(question, top_k, mode, rewrite)
        msg = {"role": "assistant", "show_queries": show_queries, **res}
        render(msg)
    st.session_state.messages.append(msg)
