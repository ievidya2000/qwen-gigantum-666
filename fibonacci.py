from marketdata import fetch_bars, ema, f, volume_stats, wyckoff, bandar_note
from bollingerbands import bb
from alligator import alligator
R = [0.0,23.6,38.2,50.0,61.8,78.6,100.0]
E = [127.2,161.8,200.0,261.8]
TFS = ["20m","30m","1h","4h","D","W"]

def fib_report(tickers, tfs=None):
    md = []
    for sym in tickers:
        md.append(f"## 🌀 FIBONACCI COMPLETE + BB + ALLIGATOR + VOLUME + PHASE — {sym}")
        bn = bandar_note(sym)
        if bn: md.append(f"🕵️ BANDARMOLOGY (Gigantum): {bn}")
        for tf in (tfs or TFS):
            try: bars = fetch_bars(sym, tf, 300)
            except Exception: md.append(f"### {tf}: data unavailable"); continue
            highs=[b[0] for b in bars]; lows=[b[1] for b in bars]; closes=[b[2] for b in bars]; vols=[b[3] for b in bars]; c=closes[-1]
            w = bars[-120:] if len(bars)>=120 else bars
            hh=max(b[0] for b in w); ll=min(b[1] for b in w); rng=(hh-ll) or 1
            up = (c-ll) >= (hh-c)
            md.append(f"### {tf} — latest {f(c)} (swing {f(ll)}–{f(hh)}, {'UP' if up else 'DOWN'} leg)")
            lv = {p: (hh - rng*p/100 if up else ll + rng*p/100) for p in R}
            ex = {p: (hh + rng*(p-100)/100 if up else ll - rng*(p-100)/100) for p in E}
            md.append("Retr: " + " | ".join(f"{p}% {f(v)}" for p,v in lv.items()))
            md.append("Ext: " + " | ".join(f"{p}% {f(v)}" for p,v in ex.items()))
            allv = sorted(list(lv.values())+list(ex.values()))
            below=[v for v in allv if v<=c]; above=[v for v in allv if v>c]
            if below and above: md.append(f"Nearest support {f(below[-1])} | nearest resistance {f(above[0])}")
            es=[f"EMA{n} {f(ema(closes,n)[-1])}" for n in (5,9,20,50,100,200) if len(closes)>=n]
            md.append("EMAs: " + " | ".join(es))
            b = bb(closes)
            if b:
                sq = " ⚡SQUEEZE (breakout pending!)" if b["squeeze"] else ""
                md.append(f"BOLLINGER(20,2): Top {f(b['top'])} | Mid {f(b['mid'])} | Bot {f(b['bot'])} | %B {b['pb']:.2f} | BW {b['bw']:.1f}%{sq}")
            a = alligator(highs, lows)
            if a:
                md.append(f"ALLIGATOR: Lips {f(a['lips'])} | Teeth {f(a['teeth'])} | Jaw {f(a['jaw'])} | {a['state']}")
            vs = volume_stats(vols)
            if vs:
                md.append(f"VOLUME: last {f(vs['last'])} vs avg20 {f(vs['avg'])} = {vs['ratio']:.2f}x → {vs['cls']} | trend {vs['trend']}")
            ph, phd = wyckoff(highs, lows, closes, vols)
            md.append(f"PHASE: {ph} — {phd}")
            e20=ema(closes,20)[-1] if len(closes)>=20 else c
            e50=ema(closes,50)[-1] if len(closes)>=50 else e20
            e200=ema(closes,200)[-1] if len(closes)>=200 else e50
            bull=bear=0
            if c>e20>e50: bull+=1
            elif c<e20<e50: bear+=1
            if b:
                if c>b["mid"]: bull+=1
                else: bear+=1
            if a:
                if a["state"].startswith("HUNTING UP"): bull+=1
                elif a["state"].startswith("HUNTING DOWN"): bear+=1
            tr = "BULLISH 🟢 (direction: UP)" if bull>bear else ("BEARISH 🔴 (direction: DOWN)" if bear>bull else "SIDEWAYS 🟡 (direction: RANGE)")
            conf = f"{max(bull,bear)}/3"
            if bull>bear:
                pred = f"bias up: magnets BB top {f(b['top']) if b else (above[0] if above else hh)} then ext 127.2% {f(ex[127.2])}; buy dips at BB mid {f(b['mid']) if b else f(e20)} / fibo 38.2–50%; trail stop under alligator jaw {f(a['jaw']) if a else f(e50)}"
            elif bear>bull:
                pred = f"bias down: magnets fibo 61.8% {f(lv[61.8])} then BB bot {f(b['bot']) if b else f(ll)}; sell strength into BB mid {f(b['mid']) if b else f(e20)} / alligator jaw {f(a['jaw']) if a else f(e50)}"
            else:
                pred = f"range: buy BB bot {f(b['bot']) if b else f(below[-1] if below else ll)} / sell BB top {f(b['top']) if b else f(above[0] if above else hh)}; wait for alligator to wake (lips crossing teeth) before trend trades"
            md.append(f"VERDICT {tf}: {tr} (confluence {conf}) | phase: {ph} — {pred}")
    return "\n".join(md), None
