import os, re, json, asyncio, httpx
from openai import OpenAI, APIError
from dotenv import load_dotenv
from supabase import create_client

load_dotenv(".env")
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
client = OpenAI(base_url=os.getenv("QWEN_BASE_URL"), api_key=os.getenv("QWEN_API_KEY"))

GIGANTUM_URL = os.getenv("GIGANTUM_MCP_URL")
GIGANTUM_TOKEN = os.getenv("GIGANTUM_AUTH_TOKEN")
HEADERS = {"Authorization": f"Bearer {GIGANTUM_TOKEN}", "Content-Type": "application/json", "Accept": "application/json, text/event-stream"}

_CJK = re.compile(r"[\u4e00-\u9fff]")
def _is_bad_lang(text): return bool(_CJK.search(text or ""))

SYSTEM_PROMPT = """You are the 'Supergod Financial Council', elite AI hedge-fund manager for IHSG.
RULES:
1. ALWAYS read history. Resolve 'above' FROM HISTORY. NEVER ask 'which stock?'.
2. Structure: 1. Macro 2. Gigantum Data 3. Debate 4. Verdict.
3. Detailed Plans: Demand/Supply Zones, B1-3, TP1-3, S1-3, R1-3, Entry, SL, RR.
4. HTML export: ONE fenced ```html block.
5. TOOL DISCIPLINE: Valid JSON args; {} if empty.
6. LANGUAGE LOCK: English or Indonesian ONLY. NEVER Chinese.
7. NO-QUESTION RULE: Deliver directly; never ask for permission."""

MEGA_PROMPT = """Analyze IDX ticker {ticker} using Gigantum tools.
Write VERDICT and REASONING in Indonesian or English ONLY.
Output ONLY this strict block, one item per line, prices as plain numbers:
VERDICT: <BUY/SELL/HOLD + one line>
B1: <price>
B2: <price>
B3: <price>
TP1: <price>
TP2: <price>
TP3: <price>
S1: <price>
S2: <price>
S3: <price>
R1: <price>
R2: <price>
R3: <price>
DEMAND_ZONE: <low>-<high>
SUPPLY_ZONE: <low>-<high>
REASONING: <3-5 sentences council debate summary>"""

async def fetch_mcp_tools():
    async with httpx.AsyncClient(timeout=30.0) as c:
        await c.post(GIGANTUM_URL, json={"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"supergod","version":"6.0"}}}, headers=HEADERS)
        r = await c.post(GIGANTUM_URL, json={"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}, headers=HEADERS)
        return r.json().get("result", {}).get("tools", [])

def map_to_openai_tools(mcp_tools):
    return [{"type":"function","function":{"name":t["name"],"description":t.get("description","")[:500],"parameters":t.get("inputSchema",{"type":"object","properties":{}})}} for t in mcp_tools]

async def execute_mcp_tool(name, args):
    async with httpx.AsyncClient(timeout=60.0) as c:
        r = await c.post(GIGANTUM_URL, json={"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":name,"arguments":args}}, headers=HEADERS)
        if "text/event-stream" in r.headers.get("content-type",""):
            for line in r.text.split("\n"):
                if line.startswith("data:"):
                    d = json.loads(line[5:].strip())
                    if "result" in d: return json.dumps(d["result"])
        return json.dumps(r.json().get("result", r.text))

def _trim(history):
    return [{"role": m["role"], "content": (m.get("content") or "")[:1500]} for m in (history or [])[-4:] if m.get("role") in ("user","assistant")]

def _chat_with_tools(messages, max_turns=4, tool_result_cap=2500, use_tools=True, model_name=None):
    try:
        tools = map_to_openai_tools(asyncio.run(fetch_mcp_tools())) if use_tools else None
    except Exception: tools = None
    
    model = model_name or os.getenv("QWEN_MODEL", "qwen-max")
    for _ in range(max_turns):
        kwargs = {"model": model, "messages": messages}
        if tools: kwargs["tools"] = tools; kwargs["tool_choice"] = "auto"
        try:
            resp = client.chat.completions.create(**kwargs)
        except APIError as e:
            if "quota" in str(e).lower() or "billing" in str(e).lower() or "429" in str(e):
                return "⚠️ QUOTA_EXHAUSTED"
            return f"⚠️ API ERROR: {str(e)[:200]}"
        msg = resp.choices[0].message
        if msg.tool_calls:
            messages.append(msg)
            for tc in msg.tool_calls:
                try: args = json.loads(tc.function.arguments or "{}")
                except Exception: args = {}
                if not isinstance(args, dict): args = {}
                result = asyncio.run(execute_mcp_tool(tc.function.name, args))
                messages.append({"role":"tool","tool_call_id":tc.id,"content":result[:tool_result_cap]})
        else:
            return msg.content or ""
    return ""

def _safe_chat(messages, max_turns=4, model_name=None):
    out = _chat_with_tools(messages, max_turns=max_turns, model_name=model_name)
    if out == "⚠️ QUOTA_EXHAUSTED": return out
    if _is_bad_lang(out):
        messages.append({"role":"user","content":"KOREKSI: Ulangi. JSON args valid. Bahasa Indonesia/English ONLY."})
        out = _chat_with_tools(messages, max_turns=max_turns, model_name=model_name)
    return out or ""

def run_council(user_id: str, prompt: str, history=None) -> str:
    mem = _trim(history)
    messages = [{"role":"system","content":SYSTEM_PROMPT}] + mem + [{"role":"user","content":prompt}]
    final = _safe_chat(messages, max_turns=6, model_name=os.getenv("QWEN_MODEL"))
    if final == "⚠️ QUOTA_EXHAUSTED":
        return "⚠️ *QUOTA HABIS* (qwen-max). Silakan tunggu reset billing cycle atau gunakan mode Mega Scan (qwen-plus) yang lebih hemat."
    try: supabase.table("trade_plans").insert({"user_id":user_id,"query":prompt,"full_analysis":final}).execute()
    except Exception: pass
    return final or "Council produced no output."

def parse_ticker_list(text):
    out = []
    for line in text.splitlines():
        m = re.match(r"^(?:\d+[.)\-]?\s*)?([A-Za-z]{4})$", line.strip())
        if m:
            t = m.group(1).upper()
            if t not in out: out.append(t)
    return out

_FIELDS = ["VERDICT","B1","B2","B3","TP1","TP2","TP3","S1","S2","S3","R1","R2","R3","DEMAND_ZONE","SUPPLY_ZONE","REASONING"]

def analyze_one(ticker):
    messages = [{"role":"system","content":SYSTEM_PROMPT},{"role":"user","content":MEGA_PROMPT.format(ticker=ticker.upper())}]
    # USE THE CHEAPER MODEL FOR MEGA SCANS!
    mega_model = os.getenv("QWEN_MEGA_MODEL", "qwen-plus")
    raw = _safe_chat(messages, model_name=mega_model)
    if raw == "⚠️ QUOTA_EXHAUSTED":
        return {"TICKER": ticker.upper(), "VERDICT": "QUOTA EXHAUSTED", "RAW": raw, **{k: "—" for k in _FIELDS if k != "VERDICT"}}
    f = {"TICKER": ticker.upper()}
    for key in _FIELDS:
        m = re.search(rf"^{key}:\s*(.+)$", raw, re.MULTILINE | re.IGNORECASE)
        f[key] = m.group(1).strip() if m else "—"
    f["RAW"] = raw
    return f

def run_mega_scan(tickers, progress=None):
    results = []
    for i, t in enumerate(tickers):
        try: results.append(analyze_one(t))
        except Exception as e: results.append(dict({"TICKER": t.upper(), "RAW": str(e)}, **{k: ("ERROR" if k=="VERDICT" else "—") for k in _FIELDS}))
        if progress: progress(i+1, len(tickers), t.upper())
    return results

def build_html_report(results):
    rows, cards = "", ""
    for r in results:
        rows += f"<tr><td><b>{r['TICKER']}</b></td><td>{r['VERDICT']}</td><td>{r['B1']} / {r['B2']} / {r['B3']}</td><td>{r['TP1']} / {r['TP2']} / {r['TP3']}</td><td>{r['S1']} / {r['S2']} / {r['S3']}</td><td>{r['R1']} / {r['R2']} / {r['R3']}</td><td>{r['DEMAND_ZONE']}</td><td>{r['SUPPLY_ZONE']}</td></tr>"
        cards += f"<div class='c'><h3>{r['TICKER']} — {r['VERDICT']}</h3><p><b>Reasoning:</b> {r['REASONING']}</p></div>"
    return f"""<html><head><meta charset='utf-8'><title>Supergod Mega Scan</title>
<style>body{{font-family:Arial,sans-serif;margin:20px}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #444;padding:6px;font-size:12px}}th{{background:#111;color:#0f0}}.c{{border:1px solid #888;border-radius:8px;padding:10px;margin:10px 0}}</style>
</head><body><h1>🚀 SUPERGOD IHSG MEGA SCAN REPORT</h1>
<table><tr><th>Ticker</th><th>Verdict</th><th>Buy 1/2/3</th><th>TP 1/2/3</th><th>Support 1/2/3</th><th>Resist 1/2/3</th><th>Demand Zone</th><th>Supply Zone</th></tr>{rows}</table>
<h2>Council Reasoning</h2>{cards}</body></html>"""
