import re
import fibonacci, montecarlo, elliott
STOP = {"WITH","THE","AND","FOR","FROM","THAT","THIS","WAVE","FIBO","HTML","CODE","COPY","PASTE","ZONE","SELL","BUY","EACH","ALL","PLEASE","PRICE","COMPLETE","DO","EW","MONTE","CARLO","ANALISA","ANALYZE","STOCK","SAHAM","ABOVE","BELOW","INTO","THEN","WHEN","WHAT","WHICH","FULL","QUANT"}

def _tickers(text):
    out=[]
    for line in text.splitlines():
        m = re.match(r"^(?:\d+[.)\-]?\s*)?([A-Za-z]{4})$", line.strip())
        if m and m.group(1).upper() not in out: out.append(m.group(1).upper())
    for t in re.findall(r"\b([A-Za-z]{4})\b", text):
        u=t.upper()
        if u not in out and u not in STOP: out.append(u)
    return out

def detect(prompt):
    low = prompt.lower()
    return ("full quant" in low) or ("fibonacci price complete" in low) or ("do ew" in low) or ("monte carlo" in low) or ("montecarlo" in low)

def handle(prompt, history=None):
    low = prompt.lower()
    tickers = _tickers(prompt)
    if not tickers and history:
        for m in reversed(history):
            if m.get("role") == "user":
                tickers = _tickers(m.get("content",""))
                if tickers: break
    if not tickers: return None
    try:
        if "full quant" in low:
            parts=[]; png=None
            for t in tickers[:5]:
                m1,_ = fibonacci.fib_report([t])
                m2,p2 = montecarlo.mc_report([t])
                m3,_ = elliott.ew_report([t])
                parts += [m1, m2, m3]; png = png or p2
            return "\n\n".join(parts), png
        if "fibonacci price complete" in low: return fibonacci.fib_report(tickers[:6])
        if "do ew" in low: return elliott.ew_report(tickers[:6])
        if ("monte carlo" in low) or ("montecarlo" in low): return montecarlo.mc_report(tickers[:6])
    except Exception as e:
        return f"⚠️ Quant module error: {type(e).__name__}: {str(e)[:200]}", None
    return None
