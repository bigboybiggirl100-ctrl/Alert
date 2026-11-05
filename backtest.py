import os
import numpy as np
import pandas as pd
import requests

PERIODS = 5
THRESHOLD = 0.0
BUFFER = 1.0
RR = 2.0
COST = 0.5
WAIT = 24
HOLD = 48


def load():
    import yfinance as yf
    df = yf.download("GC=F", period="60d", interval="5m", progress=False)
    if hasattr(df.columns, "levels"):
        df.columns = df.columns.get_level_values(0)
    return df.dropna()


def find_signals(df):
    o, c = df["Open"].values, df["Close"].values
    sigs = []
    for i in range(PERIODS, len(df)):
        ob = i - PERIODS
        run = slice(i - PERIODS + 1, i + 1)
        move = (c[i] - c[ob]) / c[ob] * 100
        if c[ob] < o[ob] and (c[run] > o[run]).all() and move > THRESHOLD:
            sigs.append((i, "BULL", ob))
        elif c[ob] > o[ob] and (c[run] < o[run]).all() and -move > THRESHOLD:
            sigs.append((i, "BEAR", ob))
    return sigs


def follow_through(df, sigs, horizon):
    c = df["Close"].values
    n = len(df)
    moves = []
    for i, kind, _ in sigs:
        if i + horizon < n:
            d = 1 if kind == "BULL" else -1
            moves.append((c[i + horizon] - c[i]) * d)
    return np.array(moves)


def simulate(df, sigs):
    o, h, l, c = (df[k].values for k in ["Open", "High", "Low", "Close"])
    n = len(df)
    results, unfilled = [], 0
    for i, kind, ob in sigs:
        bull = kind == "BULL"
        entry = h[ob] if bull else l[ob]
        stop = (l[ob] - BUFFER) if bull else (h[ob] + BUFFER)
        risk = abs(entry - stop)
        if risk <= 0:
            continue
        target = entry + RR * risk if bull else entry - RR * risk

        fill = None
        for j in range(i + 1, min(i + 1 + WAIT, n)):
            if (bull and l[j] <= entry) or ((not bull) and h[j] >= entry):
                fill = j
                break
        if fill is None:
            unfilled += 1
            continue

        r = None
        last = min(fill + HOLD, n - 1)
        for j in range(fill, last + 1):
            if bull:
                if l[j] <= stop:
                    r = -1.0
                    break
                if j > fill and h[j] >= target:
                    r = RR
                    break
            else:
                if h[j] >= stop:
                    r = -1.0
                    break
                if j > fill and l[j] <= target:
                    r = RR
                    break
        if r is None:
            d = 1 if bull else -1
            r = (c[last] - entry) * d / risk
        results.append((r - COST / risk, risk))
    return np.array(results), unfilled


def summary(df, sigs):
    lines = []
    days = df.index[-1] - df.index[0]
    lines.append(f"Gold 5m backtest, {days.days} days, {len(df)} candles")
    lines.append(f"Signals found: {len(sigs)} "
                 f"({sum(1 for s in sigs if s[1]=='BULL')} bull, "
                 f"{sum(1 for s in sigs if s[1]=='BEAR')} bear)")
    lines.append("")
    lines.append("TEST 1: follow-through after signal")
    for hz in (6, 12):
        m = follow_through(df, sigs, hz)
        if len(m):
            lines.append(f"  {hz*5} min: moved the signal's way "
                         f"{(m > 0).mean()*100:.0f}% of the time, "
                         f"avg {m.mean():+.2f} dollars")
    lines.append("")
    lines.append(f"TEST 2: retest trade ({RR:.0f}R target, cost {COST} dollars)")
    res, unfilled = simulate(df, sigs)
    if len(res) == 0:
        lines.append("  No trades filled.")
    else:
        r = res[:, 0]
        wins = r[r > 0]
        losses = r[r <= 0]
        pf = wins.sum() / abs(losses.sum()) if len(losses) and losses.sum() != 0 else float("inf")
        equity = np.cumsum(r)
        dd = (np.maximum.accumulate(equity) - equity).max()
        lines.append(f"  Trades filled: {len(r)} (never retested: {unfilled})")
        lines.append(f"  Win rate: {(r > 0).mean()*100:.0f}%")
        lines.append(f"  Avg result per trade: {r.mean():+.2f}R")
        lines.append(f"  Total: {r.sum():+.1f}R, profit factor {pf:.2f}")
        lines.append(f"  Worst drawdown: {dd:.1f}R")
        lines.append(f"  Avg risk per trade: {res[:, 1].mean():.2f} dollars")
    lines.append("")
    lines.append("Small sample, one 60-day period. Not proof of an edge.")
    return "\n".join(lines)


def main():
    df = load()
    sigs = find_signals(df)
    text = summary(df, sigs)
    print(text)
    token, chat = os.environ.get("TELEGRAM_TOKEN"), os.environ.get("CHAT_ID")
    if token and chat:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": chat, "text": text},
            timeout=10,
        )


if __name__ == "__main__":
    main()
