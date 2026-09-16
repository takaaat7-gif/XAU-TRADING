import os
import sys
import time
import requests
import pandas as pd
import yfinance as yf
from datetime import datetime, timezone

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# PENTING: "XAUUSD=X" TIDAK ADA di Yahoo Finance (itu format broker forex).
# Simbol yang benar untuk emas di Yahoo Finance adalah Gold Futures: "GC=F"
SYMBOL = "GC=F"

MAX_RETRY = 3
RETRY_DELAY = 5  # detik antar percobaan


def kirim_telegram(pesan: str):
    """Kirim pesan ke Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("TELEGRAM_BOT_TOKEN atau TELEGRAM_CHAT_ID belum diset di secrets.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": pesan,
        "parse_mode": "HTML",
    }
    try:
        resp = requests.post(url, data=payload, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"Gagal mengirim pesan Telegram: {e}")


def ambil_data_harga(symbol: str):
    """
    Ambil data harga XAU (emas) dari Yahoo Finance.
    Ada retry karena Yahoo Finance kadang gagal/limit saat diakses dari GitHub Actions.
    """
    for percobaan in range(1, MAX_RETRY + 1):
        try:
            data = yf.download(
                symbol,
                period="5d",
                interval="1h",
                progress=False,
                auto_adjust=True,
            )
            if data is not None and not data.empty:
                # PENTING (fix bug):
                # Versi yfinance terbaru kadang mengembalikan kolom
                # dalam bentuk MultiIndex, misalnya ("Close", "GC=F"),
                # walau hanya download 1 simbol. Ini menyebabkan
                # data["Close"] jadi DataFrame (bukan Series), sehingga
                # float(data["Close"].iloc[-1]) error:
                # "TypeError: float() argument must be a string or a
                # real number, not 'Series'".
                #
                # Solusi: kalau kolomnya MultiIndex, ratakan (flatten)
                # dulu supaya data["Close"] pasti berupa Series.
                if isinstance(data.columns, pd.MultiIndex):
                    data.columns = data.columns.get_level_values(0)
                return data
            print(f"Percobaan {percobaan}: data kosong, mencoba lagi...")
        except Exception as e:
            print(f"Percobaan {percobaan} gagal: {e}")

        if percobaan < MAX_RETRY:
            time.sleep(RETRY_DELAY)

    return None


def buat_sinyal(data):
    """
    Buat sinyal BUY/SELL/HOLD sederhana berdasarkan pergerakan harga.
    Logika: bandingkan harga terakhir dengan rata-rata 24 jam terakhir.
    """
    close = data["Close"]

    # Pengaman tambahan: kalau karena alasan apa pun close masih
    # berupa DataFrame (bukan Series), ambil kolom pertamanya saja.
    if hasattr(close, "columns"):
        close = close.iloc[:, 0]

    harga_terakhir = float(close.iloc[-1])
    rata_rata = float(close.tail(24).mean())
    selisih = harga_terakhir - rata_rata
    persen = (selisih / rata_rata) * 100

    if persen > 0.3:
        sinyal = "BUY"
        alasan = (
            f"Harga saat ini (${harga_terakhir:.2f}) berada {persen:.2f}% di atas "
            f"rata-rata 24 jam terakhir (${rata_rata:.2f}), menunjukkan momentum naik."
        )
    elif persen < -0.3:
        sinyal = "SELL"
        alasan = (
            f"Harga saat ini (${harga_terakhir:.2f}) berada {abs(persen):.2f}% di bawah "
            f"rata-rata 24 jam terakhir (${rata_rata:.2f}), menunjukkan momentum turun."
        )
    else:
        sinyal = "HOLD"
        alasan = (
            f"Harga saat ini (${harga_terakhir:.2f}) masih berada di sekitar rata-rata "
            f"24 jam terakhir (${rata_rata:.2f}), belum ada momentum yang jelas."
        )

    return sinyal, alasan, harga_terakhir


def main():
    data = ambil_data_harga(SYMBOL)

    if data is None:
        pesan_error = (
            "⚠️ Bot sinyal XAU gagal berjalan: Gagal mengambil data harga "
            "XAU/USD dari Yahoo Finance setelah beberapa kali percobaan."
        )
        print(pesan_error)
        kirim_telegram(pesan_error)
        sys.exit(1)

    sinyal, alasan, harga = buat_sinyal(data)
    waktu = datetime.now(timezone.utc).strftime("%d-%m-%Y %H:%M UTC")

    emoji = {"BUY": "🟢", "SELL": "🔴", "HOLD": "⚪"}.get(sinyal, "")

    pesan = (
        f"{emoji} <b>Sinyal XAU/USD: {sinyal}</b>\n\n"
        f"💰 Harga: ${harga:.2f}\n"
        f"🕒 Waktu: {waktu}\n\n"
        f"📊 Alasan:\n{alasan}"
    )

    print(pesan)
    kirim_telegram(pesan)


if __name__ == "__main__":
    main()
