import os, streamlit as st
from dotenv import load_dotenv
from core import run_council, run_mega_scan, build_html_report, parse_ticker_list
import signals

load_dotenv(".env")
st.set_page_config(page_title="Supergod IHSG Council", page_icon="🚀", layout="wide")
st.title("🚀 Supergod IHSG Council Dashboard")
st.caption("Qwen 3.8 Max + Gigantum MCP (57 Tools) + Supabase Archive + Session Memory + Progressive Mega Scan v5")

def build_html_export(messages):
    rows = ""
    for m in messages:
        role = "🧑 User" if m["role"] == "user" else "🤖 Council"
        content = m["content"].replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
        rows += f"<div style='margin:10px 0;padding:10px;border:1px solid #ccc;border-radius:8px;'><b>{role}</b><pre style='white-space:pre-wrap;'>{content}</pre></div>"
    return f"<html><head><meta charset='utf-8'></head><body style='font-family:sans-serif;'><h1>🚀 Council Chat Export</h1>{rows}</body></html>"

def render_mega(tickers):
    all_res = []
    total = len(tickers)
    bar = st.progress(0.0)
    status = st.empty()
    done = 0
    for b in range(0, total, 10):
        batch = tickers[b:b+10]
        hi = min(b+10, total)
        st.markdown(f"### 📦 Batch {b+1}–{hi} of {total}")
        slot = st.container()
        def cb(i, n, t, done=done):
            bar.progress((done + i) / total)
            status.write(f"⚙️ Scanning {done+i}/{total}: {t}")
        res = run_mega_scan(batch, progress=cb)
        done += len(batch)
        all_res.extend(res)
        html = build_html_report(res)
        with slot:
            st.code(html, language="html")
            st.download_button(f"⬇ Download batch {b+1}-{hi}", html, file_name=f"megascan_{b+1}-{hi}.html", mime="text/html")
    bar.progress(1.0)
    status.write("✅ All batches complete.")
    return all_res

if "messages" not in st.session_state: st.session_state.messages = []

with st.sidebar:
    st.header("🧠 Council Memory")
    st.write(f"Session turns: {len(st.session_state.messages)//2}")
    if st.button("🗑 New Chat (clear memory)"):
        st.session_state.messages = []
        st.rerun()
    if st.session_state.messages:
        st.download_button("⬇ Download chat as HTML", build_html_export(st.session_state.messages), file_name="supergod_council_export.html", mime="text/html")

with st.expander("🛰 MEGA SCAN — paste up to 60 emitens, get progressive batch boxes + ONE final HTML"):
    raw_list = st.text_area("Paste your numbered ticker list here", height=160)
    if st.button("🚀 RUN MEGA SCAN"):
        tickers = parse_ticker_list(raw_list)
        if not tickers:
            st.warning("No 4-letter tickers detected. Use one ticker per line (numbering like '1. BMHS' is fine).")
        else:
            try:
                all_res = render_mega(tickers)
                st.session_state["mega_html"] = build_html_report(all_res)
                st.success(f"Mega Scan complete: {len(all_res)} emitens analyzed.")
            except Exception as e:
                st.error(f"Mega Scan error: {type(e).__name__}: {e}")
    if st.session_state.get("mega_html"):
        st.markdown("**📋 FINAL COMBINED HTML (one box, copy button on right):**")
        st.code(st.session_state["mega_html"], language="html")
        st.download_button("⬇ Download FULL Mega Scan HTML", st.session_state["mega_html"], file_name="supergod_megascan_full.html", mime="text/html")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Chat normally, or paste 4+ tickers to auto-trigger Mega Scan"):
    history = list(st.session_state.messages)
    st.session_state.messages.append({"role":"user","content":prompt})
    with st.chat_message("user"): st.markdown(prompt)
    tickers = parse_ticker_list(prompt)
    if len(tickers) >= 4:
        with st.chat_message("assistant"):
            st.markdown(f"🛰 Detected {len(tickers)} tickers → AUTO MEGA SCAN (batches of 10, progressive):")
            try:
                all_res = render_mega(tickers)
                full = build_html_report(all_res)
                st.session_state["mega_html"] = full
                st.markdown("\n".join(f"**{r['TICKER']}**: {r['VERDICT']}" for r in all_res))
                st.code(full, language="html")
                st.session_state.messages.append({"role":"assistant","content":f"Mega Scan {len(all_res)} emitens complete. Full HTML delivered in box + Download button."})
            except Exception as e:
                st.error(f"Council error: {type(e).__name__}: {e}")
    else:
        with st.chat_message("assistant"):
            with st.spinner("🧠 Council reading memory + debating + calling Gigantum tools..."):
                try:
                    hit = signals.handle(prompt, history)
                    if hit:
                        response, png = hit
                        if png: st.image(png, caption="📊 Supergod Quant Chart", use_container_width=True)
                    else:
                        response = run_council("web_user", prompt, history=history)
                except Exception as e:
                    response = f"⚠️ Council error: {type(e).__name__}: {str(e)[:300]}"
            st.markdown(response)
            st.session_state.messages.append({"role":"assistant","content":response})
# force streamlit rebuild Sun Sep 13 17:14:06 WIB 2026
# cloud sync Sun Sep 13 20:53:00 WIB 2026
