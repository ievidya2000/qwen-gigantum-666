import os, re, json, asyncio, httpx
from openai import OpenAI
from dotenv import load_dotenv
from supabase import create_client

load_dotenv(".env")
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
client = OpenAI(base_url=os.getenv("QWEN_BASE_URL"), api_key=os.getenv("QWEN_API_KEY"))

GIGANTUM_URL = os.getenv("GIGANTUM_MCP_URL")
GIGANTUM_TOKEN = os.getenv("GIGANTUM_AUTH_TOKEN")
HEADERS = {"Authorization": f"Bearer {GIGANTUM_TOKEN}", "Content-Type": "application/json", "Accept": "application/json, text/event-stream"}

_CJK = re.compile(r"[\u4e00-\u9fff]")
def _is_bad_lang(text):
    return bool(_CJK.search(text or ""))

SYSTEM_PROMPT = """You are the 'Supergod Financial Council', elite AI hedge-fund manager for IHSG, connected to Gigantum MCP tools.
RULES:
1. ALWAYS read conversation history. Resolve 'above/those' FROM HISTORY. NEVER ask 'which stock?' if tickers appeared.
2. Structure analyses: 1. Expert Macro 2. Gigantum Quant Data 3. Council Debate 4. Final Verdict & Trade Plan.
3. For DETAILED TRADE PLANS PER TICKER: Demand Zone, Supply Zone, Buy B1/B2/B3, Sell/TP 1/2/3, Support S1/S2/S3, Resistance R1/R2/R3, Entry, Stop Loss, Risk:Reward. Base on tool data.
4. If asked to export HTML, produce ONE fenced ```html block.
5. TOOL-CALL DISCIPLINE: when calling tools, always send valid JSON arguments; send {} when a tool needs none.
6. LANGUAGE LOCK: write EVERY output strictly in English or Indonesian (match the user). NEVER output Chinese or any other language.
7. NO-QUESTION RULE: NEVER ask confirmation or clarifying questions. Deliver the full answer directly; for long lists work sequentially without asking permission.
8. NEVER print tool-call JSON (like {"function": ...}) as text; use only the native function-calling channel."""

MEGA_PROMPT = """Analyze IDX ticker {ticker} using Gigantum tools (predict_symbol, tv_indicators, price_bars, orderbook).
Write VERDICT and REASONING in Indonesian or English ONLY. Do not ask questions.
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
        await c.post(GIGANTUM_URL, json={"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"supergod","version":"5.0"}}}, headers=HEADERS)
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
    return [{"role": m["role"], "content": (m.get("content") or "")[:2500]} for m in (history or [])[-6:] if m.get("role") in ("user","assistant")]

def _chat_with_tools(messages, max_turns=4, tool_result_cap=4000, use_tools=True):
    try:
        tools = map_to_openai_tools(asyncio.run(fetch_mcp_tools())) if use_tools else None
    except Exception as e:
        tools = None
        print(f"⚠️ tool fetch failed: {e}")
    for _ in range(max_turns):
        kwargs = {"model": os.getenv("QWEN_MODEL","qwen-max"), "messages": messages}
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        try:
            resp = client.chat.completions.create(**kwargs)
        except Exception as e:
            return f"⚠️ COUNCIL API ERROR: {type(e).__name__}: {str(e)[:300]}"
        msg = resp.choices[0].message
        if msg.tool_calls:
            messages.append(msg)
            for tc in msg.tool_calls:
                print(f"⚙️ Tool: {tc.function.name}")
                try: args = json.loads(tc.function.arguments or "{}")
                except Exception: args = {}
                if not isinstance(args, dict): args = {}
                try:
                    result = asyncio.run(execute_mcp_tool(tc.function.name, args))
                except Exception as e:
                    result = json.dumps({"error": str(e)[:200]})
                messages.append({"role":"tool","tool_call_id":tc.id,"content":result[:tool_result_cap]})
        else:
            return msg.content or ""
    return ""

def _safe_chat(messages, max_turns=4):
    out = _chat_with_tools(messages, max_turns=max_turns)
    if _is_bad_lang(out):
        messages.append({"role":"user","content":"KOREKSI SISTEM: output terakhir tidak valid/salah bahasa. Ulangi sekarang: panggil alat hanya dengan JSON args valid ({} bila kosong), dan tulis SEMUA teks hanya dalam Bahasa Indonesia atau English."})
        out = _chat_with_tools(messages, max_turns=max_turns)
    if _is_bad_lang(out):
        out = _chat_with_tools(messages + [{"role":"user","content":"Answer now in English or Indonesian only. No tool calls."}], max_turns=1, use_tools=False)
    return out or ""

def run_council(user_id: str, prompt: str, history=None) -> str:
    mem = _trim(history)
    print(f"🔍 Council analyzing (memory turns: {len(mem)}): {prompt[:60]}...")
    messages = [{"role":"system","content":SYSTEM_PROMPT}] + mem + [{"role":"user","content":prompt}]
    final = _safe_chat(messages, max_turns=6) or "Council produced no output."
    try:
        supabase.table("trade_plans").insert({"user_id":user_id,"query":prompt,"full_analysis":final}).execute()
    except Exception as e:
        print(f"⚠️ Supabase save error: {e}")
    return final

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
    raw = _safe_chat(messages)
    f = {"TICKER": ticker.upper()}
    for key in _FIELDS:
        m = re.search(rf"^{key}:\s*(.+)$", raw, re.MULTILINE | re.IGNORECASE)
        f[key] = m.group(1).strip() if m else "—"
    f["RAW"] = raw
    return f

def run_mega_scan(tickers, progress=None):
    results = []
    for i, t in enumerate(tickers):
        try:
            results.append(analyze_one(t))
        except Exception as e:
            results.append(dict({"TICKER": t.upper(), "RAW": str(e)}, **{k: ("ERROR" if k=="VERDICT" else "—") for k in _FIELDS}))
        if progress: progress(i+1, len(tickers), t.upper())
    return results

def build_html_report(results):
    rows, cards = "", ""
    for r in results:
        rows += f"<tr><td><b>{r['TICKER']}</b></td><td>{r['VERDICT']}</td><td>{r['B1']} / {r['B2']} / {r['B3']}</td><td>{r['TP1']} / {r['TP2']} / {r['TP3']}</td><td>{r['S1']} / {r['S2']} / {r['S3']}</td><td>{r['R1']} / {r['R2']} / {r['R3']}</td><td>{r['DEMAND_ZONE']}</td><td>{r['SUPPLY_ZONE']}</td></tr>"
        cards += f"<div class='c'><h3>{r['TICKER']} — {r['VERDICT']}</h3><p><b>Council Debate Reasoning:</b> {r['REASONING']}</p></div>"
    return f"""<html><head><meta charset='utf-8'><title>Supergod Mega Scan</title>
<style>body{{font-family:Arial,sans-serif;margin:20px}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #444;padding:6px;font-size:12px}}th{{background:#111;color:#0f0}}.c{{border:1px solid #888;border-radius:8px;padding:10px;margin:10px 0}}</style>
</head><body><h1>🚀 SUPERGOD IHSG MEGA SCAN REPORT</h1>
<table><tr><th>Ticker</th><th>Verdict</th><th>Buy 1/2/3</th><th>TP 1/2/3</th><th>Support 1/2/3</th><th>Resist 1/2/3</th><th>Demand Zone</th><th>Supply Zone</th></tr>{rows}</table>
<h2>Council Reasoning Per Emiten</h2>{cards}</body></html>"""
