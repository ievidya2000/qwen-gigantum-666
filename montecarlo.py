import io
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from marketdata import fetch_bars, f

def _fan(sym, S0, P, h):
    fig, ax = plt.subplots(figsize=(8,4.5), dpi=110)
    x = np.arange(1, h+1)
    ax.fill_between(x, np.percentile(P,5,axis=0), np.percentile(P,95,axis=0), alpha=0.15, color="#4fc3f7")
    ax.fill_between(x, np.percentile(P,25,axis=0), np.percentile(P,75,axis=0), alpha=0.30, color="#4fc3f7")
    ax.plot(x, np.percentile(P,50,axis=0), color="#00e676", lw=2, label="median path")
    ax.axhline(S0, color="#ff5252", ls="--", lw=1, label="latest price")
    ax.set_title(f"Monte Carlo fan (2,000 paths) — {sym}")
    ax.set_xlabel("bars ahead"); ax.legend()
    buf = io.BytesIO(); fig.savefig(buf, format="png", bbox_inches="tight"); plt.close(fig)
    buf.seek(0); return buf.getvalue()

def mc_report(tickers, tf="D", horizon=30, paths=2000):
    md=[]; png=None
    for sym in tickers:
        try: bars = fetch_bars(sym, tf, 300)
        except Exception: md.append(f"## {sym}: MC data unavailable"); continue
        closes = np.array([b[2] for b in bars], float)
        rets = np.diff(np.log(closes)); mu=rets.mean(); sg=rets.std() or 1e-6
        S0 = closes[-1]
        Z = np.random.default_rng(42).standard_normal((paths, horizon))
        P = S0*np.exp(np.cumsum(Z,axis=1)*sg + (mu-0.5*sg*sg)*np.arange(1,horizon+1))
        q = lambda p: float(np.percentile(P[:,-1], p))
        prob = float((P[:,-1]>S0).mean()*100); var5 = (q(5)-S0)/S0*100
        md.append(f"## 🎲 MONTE CARLO — {sym} ({tf}, {horizon} bars ahead, {paths:,} paths)")
        md.append(f"Latest {f(S0)} | P10 {f(q(10))} | P25 {f(q(25))} | P50 {f(q(50))} | P75 {f(q(75))} | P90 {f(q(90))}")
        md.append(f"Upside probability {prob:.0f}% | VaR5 {var5:.1f}% | vol/bar {sg*100:.2f}%")
        md.append(f"NARRATION: with 80% confidence {sym} settles between {f(q(10))} and {f(q(90))} in {horizon} {tf}-bars; median path {f(q(50))}. Use P25 ({f(q(25))}) as conservative stop zone, P75 ({f(q(75))}) as momentum target; worst 5% tail = {var5:.1f}% drawdown. {'Bullish skew — accumulation favors buy-on-dip.' if prob>=55 else 'Bearish skew — rallies are sell-on-strength.' if prob<=45 else 'Neutral skew — size down and trade the range.'}")
        png = png or _fan(sym, S0, P, horizon)
    return "\n".join(md), png
