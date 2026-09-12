import os, json, asyncio, httpx

TF_ALIASES = {"20m":["20","20m"],"30m":["30","30m"],"1h":["60","1h","1H","60m"],"4h":["240","4h","4H","240m"],"D":["1D","D","1d","daily"],"W":["1W","W","1w","weekly"]}

def _headers():
    return {"Authorization": f"Bearer {os.getenv('GIGANTUM_AUTH_TOKEN')}", "Content-Type": "application/json", "Accept": "application/json, text/event-stream"}

_tools_cache = None
def _tools():
    global _tools_cache
    if _tools_cache is None:
        async def g():
            async with httpx.AsyncClient(timeout=30) as c:
                await c.post(os.getenv("GIGANTUM_MCP_URL"), json={"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"quant","version":"2.0"}}}, headers=_headers())
                r = await c.post(os.getenv("GIGANTUM_MCP_URL"), json={"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}, headers=_headers())
                return r.json().get("result",{}).get("tools",[])
        _tools_cache = asyncio.run(g())
    return _tools_cache

def _call_tool(name, args):
    async def g():
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.post(os.getenv("GIGANTUM_MCP_URL"), json={"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":name,"arguments":args}}, headers=_headers())
            if "text/event-stream" in r.headers.get("content-type",""):
                for line in r.text.split("\n"):
                    if line.startswith("data:"):
                        d = json.loads(line[5:].strip())
                        if "result" in d: return d["result"]
            return r.json().get("result", {})
    return asyncio.run(g())

def _extract_bars(result):
    txt = ""
    if isinstance(result, dict):
        cont = result.get("content")
        txt = "".join(x.get("text","") for x in cont if isinstance(x,dict)) if isinstance(cont,list) else json.dumps(result)
    else: txt = str(result)
    try: data = json.loads(txt)
    except Exception: return []
    def find_list(o):
        if isinstance(o, list) and o and isinstance(o[0], dict):
            if any("close" in k.lower() for k in o[0]): return o
        if isinstance(o, dict):
            for v in o.values():
                q = find_list(v)
                if q: return q
        return None
    bars = find_list(data) or []
    out = []
    for b in bars:
        lm = {k.lower(): v for k,v in b.items()}
        close = next((v for k,v in lm.items() if "close" in k), None)
        if close is None: continue
        high = next((v for k,v in lm.items() if "high" in k), close)
        low = next((v for k,v in lm.items() if "low" in k), close)
        vol = next((v for k,v in lm.items() if "vol" in k), 0.0)
        try: out.append((float(high), float(low), float(close), float(vol or 0)))
        except Exception: continue
    return out

def fetch_bars(symbol, tf="D", limit=300):
    tools = _tools()
    cand = [t for t in tools if any(s in t["name"].lower() for s in ("price_bar","bars","kline","candle","ohlcv"))] or [t for t in tools if "indicator" in t["name"].lower()]
    last = None
    for t in cand:
        schema = t.get("inputSchema",{}).get("properties",{})
        for alias in TF_ALIASES.get(tf,[tf]):
            args = {}
            for pname in schema:
                pl = pname.lower()
                if pl in ("symbol","ticker","stock","stock_code","symbol_code","code"): args[pname] = symbol
                elif pl in ("timeframe","interval","resolution","period","tf","granularity"): args[pname] = alias
                elif pl in ("limit","count","bars","length","n","num"): args[pname] = limit
            try:
                bars = _extract_bars(_call_tool(t["name"], args))
                if len(bars) >= 30: return bars
            except Exception as e: last = e
    raise RuntimeError(f"no bars {symbol}/{tf}: {last}")

def bandar_note(symbol):
    try:
        tools = [t for t in _tools() if "bandar" in t["name"].lower()]
        if not tools: return None
        t = tools[0]; schema = t.get("inputSchema",{}).get("properties",{})
        args = {}
        for pname in schema:
            pl = pname.lower()
            if pl in ("symbol","ticker","stock","stock_code","symbol_code","code"): args[pname] = symbol
            elif pl in ("limit","count","n"): args[pname] = 10
        res = _call_tool(t["name"], args)
        txt = ""
        if isinstance(res, dict):
            cont = res.get("content")
            txt = "".join(x.get("text","") for x in cont if isinstance(x,dict)) if isinstance(cont,list) else json.dumps(res)
        else: txt = str(res)
        return txt[:300].replace("\n"," ")
    except Exception:
        return None

def ema(vals, n):
    if not vals or n < 1: return [0.0]
    k = 2/(n+1); out = [vals[0]]
    for v in vals[1:]: out.append(v*k + out[-1]*(1-k))
    return out

def zigzag(highs, lows, pct=0.08):
    pivots=[]; trend=0; ext_i=0; ext_p=lows[0] if lows else 0
    for i in range(len(highs)):
        h,l = highs[i], lows[i]
        if trend==1:
            if h>ext_p: ext_p,ext_i=h,i
            elif l<ext_p*(1-pct): pivots.append((ext_i,ext_p,"H")); trend=-1; ext_p,ext_i=l,i
        elif trend==-1:
            if l<ext_p: ext_p,ext_i=l,i
            elif h>ext_p*(1+pct): pivots.append((ext_i,ext_p,"L")); trend=1; ext_p,ext_i=h,i
        else:
            if h>ext_p*(1+pct): pivots.append((ext_i,ext_p,"L")); trend=1; ext_p,ext_i=h,i
            elif l<ext_p*(1-pct): pivots.append((ext_i,ext_p,"H")); trend=-1; ext_p,ext_i=l,i
            else:
                if h>ext_p: ext_p,ext_i=h,i
                if l<ext_p: ext_p,ext_i=l,i
    if highs: pivots.append((ext_i,ext_p,"H" if trend==1 else "L"))
    return pivots

def volume_stats(vols):
    if not vols or max(vols) <= 0: return None
    avg = sum(vols[-20:])/min(20,len(vols))
    if avg <= 0: return None
    ratio = vols[-1]/avg
    cls = "HUGE 🌋" if ratio>=2.5 else ("BIG 🔊" if ratio>=1.5 else ("NORMAL ➖" if ratio>=0.75 else "SMALL 🤫"))
    t5 = sum(vols[-5:])/5; t20 = avg
    trend = "rising" if t5>t20*1.15 else ("fading" if t5<t20*0.85 else "flat")
    return {"last": vols[-1], "avg": avg, "ratio": ratio, "cls": cls, "trend": trend}

def wyckoff(highs, lows, closes, vols):
    if len(closes) < 60: return ("DATA TOO SHORT", "need 60+ bars")
    w = closes[-120:] if len(closes)>=120 else closes
    hh=max(highs[-120:]) if len(highs)>=120 else max(highs); ll=min(lows[-120:]) if len(lows)>=120 else min(lows)
    c0=closes[-1]; c60=closes[-60]; rng=(hh-ll) or 1; pos=(c0-ll)/rng
    chg=(c0-c60)/c60
    has_vol = bool(vols) and max(vols)>0
    if has_vol:
        upv=sum(vols[i] for i in range(len(closes)-30,len(closes)) if closes[i]>closes[i-1])
        dnv=sum(vols[i] for i in range(len(closes)-30,len(closes)) if closes[i]<closes[i-1])
    else:
        upv=dnv=1
    if chg>0.05:
        if upv>dnv*1.2: return ("MARKUP 🚀", "price up WITH volume confirmation = real trend, ride it")
        return ("MARKUP ON THIN VOLUME 🎈", "price up but volume weak = trap risk, take profits into strength")
    if chg<-0.05:
        if dnv>upv*1.2: return ("MARKDOWN 😱", "heavy-volume selling = shakeout of retail hands; watch for volume dry-up = accumulation start")
        return ("MARKDOWN w/ FADING VOLUME 🌘", "selling exhausting = smart money may be absorbing; watch reversal signals")
    if pos<0.35:
        return ("ACCUMULATION 🤫", "sideways near range LOW = bandar quietly collecting; buy zones here have best R:R")
    if pos>0.65:
        return ("DISTRIBUTION ⚠️", "sideways near range HIGH = bandar unloading to retail; sell strength, do not chase")
    return ("CONSOLIDATION ⏸", "mid-range chop = wait for volume breakout direction")

def f(x): return f"{x:,.2f}" if abs(x)<100 else f"{x:,.0f}"
