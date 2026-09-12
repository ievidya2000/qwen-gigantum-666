import os, streamlit as st
from dotenv import load_dotenv
from core import run_council, run_mega_scan, build_html_report, parse_ticker_list

load_dotenv(".env")
st.set_page_config(page_title="Supergod IHSG Council", page_icon="🚀", layout="wide")
st.title("🚀 Supergod IHSG Council Dashboard")
st.caption("Qwen 3.8 Max + Gigantum MCP (57 Tools) + Supabase Archive + Session Memory + Mega Scan v3")

def build_html_export(messages):
    rows = ""
    for m in messages:
        role = "🧑 User" if m["role"] == "user" else "🤖 Council"
        content = m["content"].replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
        rows += f"<div style='margin:10px 0;padding:10px;border:1px solid #ccc;border-radius:8px;'><b>{role}</b><pre style='white-space:pre-wrap;'>{content}</pre></div>"
    return f"<html><head><meta charset='utf-8'></head><body style='font-family:sans-serif;'><h1>🚀 Council Chat Export</h1>{rows}</body></html>"

if "messages" not in st.session_state: st.session_state.messages = []

with st.sidebar:
    st.header("🧠 Council Memory")
    st.write(f"Session turns: {len(st.session_state.messages)//2}")
    if st.button("🗑 New Chat (clear memory)"):
        st.session_state.messages = []
        st.rerun()
    if st.session_state.messages:
        st.download_button("⬇ Download chat as HTML", build_html_export(st.session_state.messages), file_name="supergod_council_export.html", mime="text/html")

with st.expander("🛰 MEGA SCAN — paste up to 60 emitens, get ONE professional HTML report"):
    raw_list = st.text_area("Paste your numbered ticker list here", height=160)
    if st.button("🚀 RUN MEGA SCAN"):
        tickers = parse_ticker_list(raw_list)
        if not tickers:
            st.warning("No 4-letter tickers detected. Use one ticker per line (numbering like '1. BMHS' is fine).")
        else:
            bar = st.progress(0.0)
            status = st.empty()
            def cb(i, n, t):
                bar.progress(i / n)
                status.write(f"⚙️ Scanning {i}/{n}: {t}")
            results = run_mega_scan(tickers, progress=cb)
            st.session_state["mega_html"] = build_html_report(results)
            st.success(f"Mega Scan complete: {len(results)} emitens analyzed.")
    if st.session_state.get("mega_html"):
        st.markdown("**📋 THE ONE-BOX HTML (copy button on the right):**")
        st.code(st.session_state["mega_html"], language="html")
        st.download_button("⬇ Download Mega Scan HTML", st.session_state["mega_html"], file_name="supergod_megascan.html", mime="text/html")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Follow-ups work: 'detail trade plan for all emitens above'"):
    history = list(st.session_state.messages)
    st.session_state.messages.append({"role":"user","content":prompt})
    with st.chat_message("user"): st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("🧠 Council reading memory + debating + calling Gigantum tools..."):
            response = run_council("web_user", prompt, history=history)
        st.markdown(response)
        st.session_state.messages.append({"role":"assistant","content":response})
