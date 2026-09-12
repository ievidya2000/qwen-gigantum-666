from marketdata import fetch_bars, zigzag, f

def ew_report(tickers, tf="D"):
    md=[]
    for sym in tickers:
        try: bars = fetch_bars(sym, tf, 400)
        except Exception: md.append(f"## {sym}: EW data unavailable"); continue
        highs=[b[0] for b in bars]; lows=[b[1] for b in bars]; closes=[b[2] for b in bars]; c=closes[-1]
        piv = zigzag(highs, lows, 0.08)[-8:]
        md.append(f"## 🌊 ELLIOTT WAVE — {sym} ({tf}) latest {f(c)}")
        md.append("Swing map: " + " → ".join(f"{t}{f(p)}" for _,p,t in piv))
        if len(piv) < 4:
            md.append("Not enough swings for a wave count — market too flat. Retry on higher TF."); continue
        leg = piv[-1][1] - piv[-2][1]; up = leg > 0
        base = piv[-1][1]
        t127 = base + 1.272*abs(leg) if up else base - 1.272*abs(leg)
        t161 = base + 1.618*abs(leg) if up else base - 1.618*abs(leg)
        r38 = base - 0.382*abs(leg) if up else base + 0.382*abs(leg)
        r50 = base - 0.500*abs(leg) if up else base + 0.500*abs(leg)
        if up:
            pos = "riding wave 5 (or extended wave 3) ABOVE last swing high" if c >= piv[-1][1] else "in wave 4 pullback BELOW last swing high"
            md.append(f"PRIMARY COUNT: impulse UP (waves 1-5). Current price {pos}.")
            md.append(f"Targets while impulse holds: wave ext 1.272 = {f(t127)}, 1.618 = {f(t161)}.")
            md.append(f"Wave-4/2 support zone (buy dips): {f(r38)}–{f(r50)}. Invalidation: close below {f(r50)} → recount as ABC correction.")
            md.append(f"ALTERNATIVE COUNT: if {f(r50)} breaks, current structure = wave C of ABC down toward {f(base - 1.0*abs(leg))}.")
        else:
            pos = "riding wave C / wave 5 down BELOW last swing low" if c <= piv[-1][1] else "in wave B bounce ABOVE last swing low"
            md.append(f"PRIMARY COUNT: impulse DOWN / ABC correction. Current price {pos}.")
            md.append(f"Downside targets: ext 1.272 = {f(t127)}, 1.618 = {f(t161)}.")
            md.append(f"Resistance (sell-on-strength zone): {f(r38)}–{f(r50)}. Invalidation of bearish count: close above {f(r50)}.")
            md.append(f"ALTERNATIVE COUNT: reclaim of {f(r50)} flips structure to new impulse UP wave 1-2 with target {f(base + 1.618*abs(leg))}.")
    return "\n".join(md), None
