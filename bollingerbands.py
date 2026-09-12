def bb(closes, n=20, k=2.0):
    if len(closes) < n: return None
    win = closes[-n:]
    mid = sum(win)/n
    sd = (sum((x-mid)**2 for x in win)/n)**0.5
    top = mid + k*sd; bot = mid - k*sd
    c = closes[-1]
    pb = (c-bot)/(top-bot) if top > bot else 0.5
    bw = (top-bot)/mid*100 if mid else 0.0
    bws = []
    for i in range(max(0, len(closes)-60), len(closes)-n+1):
        w = closes[i:i+n]
        m = sum(w)/n
        s = (sum((x-m)**2 for x in w)/n)**0.5
        if m: bws.append(((m+k*s)-(m-k*s))/m*100)
    squeeze = bool(bws) and bw <= sorted(bws)[max(0, int(0.25*len(bws)))]
    return {"top": top, "mid": mid, "bot": bot, "pb": pb, "bw": bw, "squeeze": squeeze}
