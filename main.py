import asyncio
import requests
import os
import mplfinance as mpf
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from datetime import datetime
from scipy.signal import argrelextrema
from telegram import Bot

TOKEN = "7264977373:AAEZcqW5XL2LqLoQKbLUOKW1N0pdiGE2kFs"
CHAT_ID = "510189896"
bot = Bot(token=TOKEN)

COINS = [
    "BTC", "ETH", "BNB", "SOL", "XRP", "DOGE", "ADA", "AVAX", "LINK", "DOT",
    "MATIC", "SHIB", "TON", "LTC", "BCH", "UNI", "NEAR", "ICP", "INJ", "APT",
    "ARB", "OP", "XLM", "FIL", "SUI", "MKR", "GRT", "RUNE", "IMX", "AAVE"
]
TIMEFRAMES = ["1h", "4h", "1d"]

def get_historical_data(symbol, interval):
    url = f"https://min-api.cryptocompare.com/data/v2/histohour" if interval != "1d" else "https://min-api.cryptocompare.com/data/v2/histoday"
    limit = 200
    params = {
        "fsym": symbol,
        "tsym": "USDT",
        "limit": limit,
        "api_key": "ea48cbea161a3944bd7957a6a1e56255afdca0152f6c68641b9d52f99de23537"
    }
    if interval == "4h":
        params["aggregate"] = 4
    elif interval == "1h":
        params["aggregate"] = 1
    response = requests.get(url, params=params)
    data = response.json()["Data"]["Data"]
    df = pd.DataFrame(data)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df.set_index("time", inplace=True)
    df = df[["open", "high", "low", "close", "volumeto"]]
    df.columns = ["Open", "High", "Low", "Close", "Volume"]
    return df

def detect_wedge(df):
    close = df['Close'].values
    local_max = argrelextrema(close, np.greater, order=5)[0]
    local_min = argrelextrema(close, np.less, order=5)[0]

    if len(local_max) < 2 or len(local_min) < 2:
        return None

    max1, max2 = local_max[-2], local_max[-1]
    min1, min2 = local_min[-2], local_min[-1]

    upper_trend = (close[max2] - close[max1]) / (max2 - max1)
    lower_trend = (close[min2] - close[min1]) / (min2 - min1)

    latest_close = close[-1]
    upper_line = close[max1] + upper_trend * (len(close) - 1 - max1)
    lower_line = close[min1] + lower_trend * (len(close) - 1 - min1)

    if lower_line < latest_close < upper_line:
        return None

    if latest_close > upper_line:
        return "Breakout Up"
    elif latest_close < lower_line:
        return "Breakout Down"
    return None

def calculate_indicators(df):
    df["EMA12"] = df["Close"].ewm(span=12).mean()
    df["EMA26"] = df["Close"].ewm(span=26).mean()
    df["MACD"] = df["EMA12"] - df["EMA26"]
    df["Signal"] = df["MACD"].ewm(span=9).mean()
    df["RSI"] = compute_rsi(df["Close"])
    return df

def compute_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def check_rsi_alert(df):
    rsi = df["RSI"].iloc[-1]
    if rsi > 80:
        return "RSI Overbought"
    elif rsi < 20:
        return "RSI Oversold"
    return None

def check_macd_alert(df):
    if df["MACD"].iloc[-2] < df["Signal"].iloc[-2] and df["MACD"].iloc[-1] > df["Signal"].iloc[-1]:
        return "MACD Bullish Crossover"
    elif df["MACD"].iloc[-2] > df["Signal"].iloc[-2] and df["MACD"].iloc[-1] < df["Signal"].iloc[-1]:
        return "MACD Bearish Crossover"
    return None

def draw_chart(df, symbol, interval, alert_text):
    df_last = df[-60:]
    mc = mpf.make_marketcolors(up='g', down='r')
    s = mpf.make_mpf_style(marketcolors=mc)

    image_path = f"{symbol}_{interval}.png"
    apds = []

    if "MACD" in df.columns:
        apds.append(mpf.make_addplot(df["MACD"], panel=1, color='fuchsia'))
        apds.append(mpf.make_addplot(df["Signal"], panel=1, color='b'))

    fig, ax = mpf.plot(
        df_last,
        type='candle',
        style=s,
        volume=True,
        addplot=apds,
        returnfig=True,
        title=f"{symbol}/{interval} - {alert_text}",
        figsize=(12, 8)
    )
    fig.savefig(image_path)
    plt.close(fig)
    return image_path

async def analyze():
    for symbol in COINS:
        for tf in TIMEFRAMES:
            try:
                df = get_historical_data(symbol, tf)
                df = calculate_indicators(df)
                wedge_alert = detect_wedge(df)
                rsi_alert = check_rsi_alert(df)
                macd_alert = check_macd_alert(df)

                alerts = [a for a in [wedge_alert, rsi_alert, macd_alert] if a]
                if alerts:
                    alert_text = ", ".join(alerts)
                    image_path = draw_chart(df, symbol, tf, alert_text)
                    with open(image_path, 'rb') as photo:
                        await bot.send_photo(chat_id=CHAT_ID, photo=photo, caption=f"{symbol}/USDT Alert ({tf}): {alert_text}")
            except Exception as e:
                print(f"{symbol} {tf} error:", e)

async def main_loop():
    while True:
        await analyze()
        await asyncio.sleep(900)  # 15 minutes

if __name__ == "__main__":
    asyncio.run(main_loop())
