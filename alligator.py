def smma(vals, n):
    if len(vals) < n: return []
    out = [sum(vals[:n])/n]
    for v in vals[n:]:
        out.append((out[-1]*(n-1)+v)/n)
    return out

def alligator(highs, lows):
    mid = [(h+l)/2 for h,l in zip(highs, lows)]
    jaw_s = smma(mid, 13); teeth_s = smma(mid, 8); lips_s = smma(mid, 5)
    if not jaw_s or not teeth_s or not lips_s: return None
    jaw = jaw_s[-9] if len(jaw_s) >= 9 else jaw_s[-1]
    teeth = teeth_s[-6] if len(teeth_s) >= 6 else teeth_s[-1]
    lips = lips_s[-4] if len(lips_s) >= 4 else lips_s[-1]
    if lips > teeth > jaw: state = "HUNTING UP 🟢 (bullish alignment)"
    elif lips < teeth < jaw: state = "HUNTING DOWN 🔴 (bearish alignment)"
    else: state = "SLEEPING 😴 (intertwined = sideways/chop)"
    return {"lips": lips, "teeth": teeth, "jaw": jaw, "state": state}
