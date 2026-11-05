import os
import pandas as pd
import requests
import yfinance as yf

TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

SYMBOL = "GC=F"
PERIODS = 5
THRESHOLD = 0.0


def send(msg):
    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": msg},
        timeout=10,
    )


def main():
    df = yf.download(SYMBOL, period="1d", interval="5m", progress=False)
    if df.empty:
        print("No data (market closed?)")
        return
    if hasattr(df.columns, "levels"):
        df.columns = df.columns.get_level_values(0)
    df = df.iloc[:-1]
    if len(df) < PERIODS + 1:
        return

    stamp = df.index[-1]
    closed_at = stamp + pd.Timedelta(minutes=5)
    age_min = (pd.Timestamp.now(tz=stamp.tz) - closed_at).total_seconds() / 60
    if age_min > 6:
        print("Latest candle is old, skipping.")
        return

    ob = df.iloc[-(PERIODS + 1)]
    run = df.iloc[-PERIODS:]
    move = (run["Close"].iloc[-1] - ob["Close"]) / ob["Close"] * 100

    kind = None
    if ob["Close"] < ob["Open"] and (run["Close"] > run["Open"]).all() and move > THRESHOLD:
        kind = "BULLISH"
    elif ob["Close"] > ob["Open"] and (run["Close"] < run["Open"]).all() and -move > THRESHOLD:
        kind = "BEARISH"

    if kind:
        send(
            f"{kind} order block on gold 5m\n"
            f"Zone: {ob['Low']:.2f} - {ob['High']:.2f}\n"
            f"Candle closed: {closed_at}"
        )
        print("Alert sent:", kind)
    else:
        print("No order block.")


if __name__ == "__main__":
    main()
