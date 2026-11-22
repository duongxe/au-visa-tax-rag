import os

import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(page_title="Hỏi đáp Visa & Thuế Úc", page_icon="🇦🇺")
st.title("Hỏi đáp Visa & Thuế Úc")
st.caption("Không phải tư vấn di trú/thuế. Luôn kiểm tra lại trên trang chính thức.")

question = st.text_input("Câu hỏi (tiếng Việt hoặc tiếng Anh)")
if st.button("Hỏi") and question.strip():
    with st.spinner("Đang tìm..."):
        r = requests.post(f"{API_URL}/ask", json={"question": question}, timeout=120)
    r.raise_for_status()
    data = r.json()
    st.markdown(data["answer"])
    for s in data["sources"]:
        with st.expander(f"[{s['id']}] {s['title']}" + (f" — trang {s['page']}" if s.get("page") else "")):
            st.markdown(f"[{s['url']}]({s['url']})")
            st.write(s["snippet"])
