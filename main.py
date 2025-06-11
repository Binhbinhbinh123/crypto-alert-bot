
import os
import requests
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import mplfinance as mpf
from ta.momentum import RSIIndicator
from ta.trend import MACD
from datetime import datetime, timedelta
from scipy.signal import argrelextrema
import telegram
from telegram import Bot
from flask import Flask
import threading
import time

# ====== CONFIG ======
TELEGRAM_TOKEN = "7264977373:AAEZcqW5XL2LqLoQKbLUOKW1N0pdiGE2kFs"
CHAT_ID = "510189896"
API_KEY = "ea48cbea161a3944bd7957a6a1e56255afdca0152f6c68641b9d52f99de23537"
COINS = ['BTC', 'ETH', 'BNB', 'SOL', 'XRP', 'ADA', 'DOGE', 'AVAX', 'DOT', 'LINK',
         'MATIC', 'LTC', 'BCH', 'UNI', 'FIL', 'ICP', 'ETC', 'APT', 'HBAR', 'VET',
         'RNDR', 'AR', 'TIA', 'SUI', 'MKR', 'XLM', 'NEAR', 'INJ', 'STX', 'ATOM']
INTERVAL = "1h"
LIMIT = 100
ALERT_INTERVAL = 15 * 60  # every 15 minutes

bot = Bot(token=TELEGRAM_TOKEN)

# ====== CHART ANALYSIS ======

def fetch_data(symbol):
    url = f"https://min-api.cryptocompare.com/data/v2/histohour?fsym={symbol}&tsym=USDT&limit={LIMIT}&api_key={API_KEY}"
    res = requests.get(url)
    data = res.json()['Data']['Data']
    df = pd.DataFrame(data)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df.set_index('time', inplace=True)
    return df

def find_wedge(df):
    highs = df['high']
    lows = df['low']
    max_idx = argrelextrema(highs.values, np.greater, order=3)[0]
    min_idx = argrelextrema(lows.values, np.less, order=3)[0]

    if len(max_idx) >= 2 and len(min_idx) >= 2:
        high_line = np.polyfit(max_idx, highs.iloc[max_idx], 1)
        low_line = np.polyfit(min_idx, lows.iloc[min_idx], 1)
        return high_line, low_line, max_idx, min_idx
    return None, None, [], []

def check_breakout(df, high_line, low_line):
    x = np.arange(len(df))
    upper = high_line[0] * x + high_line[1]
    lower = low_line[0] * x + low_line[1]
    close = df['close'].values

    if close[-1] > upper[-1]:
        return "breakout_up"
    elif close[-1] < lower[-1]:
        return "breakout_down"
    return None

def check_rsi(df):
    rsi = RSIIndicator(df['close']).rsi()
    if rsi.iloc[-1] > 80:
        return "RSI Overbought"
    elif rsi.iloc[-1] < 20:
        return "RSI Oversold"
    return None

def check_macd(df):
    macd = MACD(df['close'])
    macd_line = macd.macd()
    signal = macd.macd_signal()
    if macd_line.iloc[-2] < signal.iloc[-2] and macd_line.iloc[-1] > signal.iloc[-1]:
        return "MACD Bullish Crossover"
    elif macd_line.iloc[-2] > signal.iloc[-2] and macd_line.iloc[-1] < signal.iloc[-1]:
        return "MACD Bearish Crossover"
    return None

def plot_chart(df, symbol, high_line, low_line, alert_text):
    x = np.arange(len(df))
    upper = high_line[0] * x + high_line[1]
    lower = low_line[0] * x + low_line[1]

    df_plot = df[-60:]

    fig, ax = plt.subplots(figsize=(10,6))
    mpf.plot(df_plot, type='candle', ax=ax, style='charles')
    ax.plot(df_plot.index, upper[-60:], label='Upper Trend', color='green')
    ax.plot(df_plot.index, lower[-60:], label='Lower Trend', color='red')
    ax.legend()
    ax.set_title(f"{symbol}/USDT - {alert_text}")
    image_path = f"{symbol}_chart.png"
    plt.savefig(image_path)
    plt.close()
    return image_path

def analyze(symbol):
    df = fetch_data(symbol)
    if df is None or len(df) < 60:
        return
    high_line, low_line, max_idx, min_idx = find_wedge(df)
    if high_line is None:
        return

    alerts = []
    breakout = check_breakout(df, high_line, low_line)
    if breakout:
        alerts.append(breakout)
    rsi = check_rsi(df)
    if rsi:
        alerts.append(rsi)
    macd = check_macd(df)
    if macd:
        alerts.append(macd)

    if alerts:
        alert_text = ', '.join(alerts)
        image_path = plot_chart(df, symbol, high_line, low_line, alert_text)
        bot.send_photo(chat_id=CHAT_ID, photo=open(image_path, 'rb'), caption=f"{symbol}/USDT Alert: {alert_text}")

# ====== MAIN LOOP ======

def run_bot():
    while True:
        for coin in COINS:
            try:
                analyze(coin)
            except Exception as e:
                print(f"Error analyzing {coin}: {e}")
        time.sleep(ALERT_INTERVAL)

# ====== FLASK SERVER FOR UPTIMEROBOT ======

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

threading.Thread(target=run_bot).start()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
