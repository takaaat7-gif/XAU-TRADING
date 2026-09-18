"""
Bot Sinyal XAU/USD (Gold) untuk Telegram
=========================================
Mengambil harga emas real-time, menghitung sinyal BUY/SELL/HOLD
beserta Stop Loss (SL) dan Take Profit (TP) berbasis volatilitas 24 jam,
lalu mengirim hasilnya ke Telegram.

Cocok dijalankan via GitHub Actions (cron per jam).

ENV VARIABLES yang dibutuhkan (isi lewat GitHub Secrets):
  TELEGRAM_BOT_TOKEN   -> token bot Telegram
  TELEGRAM_CHAT_ID     -> chat id tujuan
  TWELVEDATA_API_KEY   -> (opsional) API key Twelve Data, jika tidak diisi
                          script otomatis fallback ke Yahoo Finance (yfinance)

Install dependency:
  pip install requests yfinance --break-system-packages
"""

import os
import sys
import requests
from datetime import datetime, timezone

# ============ KONFIGURASI ============
SYMBOL_TWELVEDATA = "XAU/USD"
SYMBOL_YFINANCE = "GC=F"  # Gold futures sebagai proxy XAU/USD di Yahoo Finance

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
TWELVEDATA_KEY = os.environ.get("TWELVEDATA_API_KEY")

# Rasio SL/TP terhadap range volatilitas 24 jam (bisa disesuaikan)
SL_RATIO = 0.25
TP_RATIO = 0.5


# ============ AMBIL DATA HARGA ============
def get_price_data():
    """
    Mengembalikan dict: {
        'price': float,
        'avg24h': float,
        'high24h': float,
        'low24h': float
    }
    Coba Twelve Data dulu (jika API key ada), fallback ke Yahoo Finance.
    """
    if TWELVEDATA_KEY:
        data = _get_from_twelvedata()
        if data:
            return data
        print("Twelve Data gagal/limit, fallback ke Yahoo Finance...", file=sys.stderr)

    return _get_from_yfinance()


def _get_from_twelvedata():
    try:
        url = "https://api.twelvedata.com/time_series"
        params = {
            "symbol": SYMBOL_TWELVEDATA,
            "interval": "1h",
            "outputsize": 24,
            "apikey": TWELVEDATA_KEY,
        }
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        payload = resp.json()

        if "values" not in payload:
            print(f"Twelve Data error: {payload}", file=sys.stderr)
            return None

        candles = payload["values"]
        closes = [float(c["close"]) for c in candles]
        highs = [float(c["high"]) for c in candles]
        lows = [float(c["low"]) for c in candles]

        current_price = closes[0]  # candle terbaru ada di index 0
        avg24h = sum(closes) / len(closes)
        high24h = max(highs)
        low24h = min(lows)

        return {
            "price": current_price,
            "avg24h": avg24h,
            "high24h": high24h,
            "low24h": low24h,
        }
    except Exception as e:
        print(f"Error Twelve Data: {e}", file=sys.stderr)
        return None


def _get_from_yfinance():
    try:
        import yfinance as yf

        ticker = yf.Ticker(SYMBOL_YFINANCE)
        hist = ticker.history(period="2d", interval="1h")

        if hist.empty:
            raise ValueError("Data yfinance kosong")

        last_24 = hist.tail(24)
        current_price = float(last_24["Close"].iloc[-1])
        avg24h = float(last_24["Close"].mean())
        high24h = float(last_24["High"].max())
        low24h = float(last_24["Low"].min())

        return {
            "price": current_price,
            "avg24h": avg24h,
            "high24h": high24h,
            "low24h": low24h,
        }
    except Exception as e:
        print(f"Error yfinance: {e}", file=sys.stderr)
        return None


# ============ LOGIKA SINYAL ============
def build_signal(data):
    price = data["price"]
    avg24h = data["avg24h"]
    high24h = data["high24h"]
    low24h = data["low24h"]
    range24h = max(high24h - low24h, 0.01)  # hindari pembagian/rasio 0

    deviasi_persen = ((price - avg24h) / avg24h) * 100

    # Tentukan arah sinyal berdasarkan posisi harga vs rata-rata 24 jam
    if deviasi_persen > 0.15:
        arah = "BUY"
        emoji = "🟢"
        sl = price - (SL_RATIO * range24h)
        tp = price + (TP_RATIO * range24h)
        alasan = (
            f"Harga saat ini (${price:,.2f}) berada {deviasi_persen:.2f}% di atas "
            f"rata-rata 24 jam terakhir (${avg24h:,.2f}), menunjukkan momentum naik."
        )
    elif deviasi_persen < -0.15:
        arah = "SELL"
        emoji = "🔴"
        sl = price + (SL_RATIO * range24h)
        tp = price - (TP_RATIO * range24h)
        alasan = (
            f"Harga saat ini (${price:,.2f}) berada {abs(deviasi_persen):.2f}% di bawah "
            f"rata-rata 24 jam terakhir (${avg24h:,.2f}), menunjukkan momentum turun."
        )
    else:
        arah = "HOLD"
        emoji = "⚪"
        sl = price - (SL_RATIO * range24h)
        tp = price + (TP_RATIO * range24h)
        alasan = (
            f"Harga saat ini (${price:,.2f}) masih berada dekat rata-rata 24 jam "
            f"(${avg24h:,.2f}), belum ada momentum yang jelas."
        )

    waktu = datetime.now(timezone.utc).strftime("%d-%m-%Y %H:%M UTC")

    pesan = (
        f"{emoji} Sinyal XAU/USD: {arah}\n\n"
        f"💰 Harga: ${price:,.2f}\n"
        f"🕒 Waktu: {waktu}\n\n"
        f"📊 Alasan:\n{alasan}\n\n"
        f"🛑 Stop Loss: ${sl:,.2f}\n"
        f"🎯 Take Profit: ${tp:,.2f}\n\n"
        f"⚠️ Ini bukan nasihat keuangan. Gunakan manajemen risiko sendiri."
    )
    return pesan


# ============ KIRIM KE TELEGRAM ============
def send_telegram_message(text):
    if not BOT_TOKEN or not CHAT_ID:
        print("TELEGRAM_BOT_TOKEN atau TELEGRAM_CHAT_ID belum diset.", file=sys.stderr)
        sys.exit(1)

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    resp = requests.post(url, data={"chat_id": CHAT_ID, "text": text}, timeout=15)
    resp.raise_for_status()
    print("Pesan berhasil dikirim ke Telegram.")


# ============ MAIN ============
def main():
    data = get_price_data()
    if not data:
        print("Gagal mengambil data harga dari semua sumber. Sinyal tidak dikirim.", file=sys.stderr)
        sys.exit(1)

    pesan = build_signal(data)
    print(pesan)  # tampil di log GitHub Actions juga
    send_telegram_message(pesan)


if __name__ == "__main__":
    main()
