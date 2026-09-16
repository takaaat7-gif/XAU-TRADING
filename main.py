import os
import sys
import requests
import yfinance as yf
import pandas as pd
import feedparser

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

GOLD_TICKER = "XAUUSD=X"  # Harga spot emas vs USD via Yahoo Finance
NEWS_RSS_URL = (
    "https://news.google.com/rss/search?q=gold+price+OR+XAU+OR+harga+emas"
    "&hl=en-US&gl=US&ceid=US:en"
)

POSITIVE_WORDS = [
    "surge", "rally", "rise", "rises", "rising", "gain", "gains", "bullish",
    "jump", "jumps", "record high", "safe haven demand", "soar", "soars",
    "climb", "climbs", "strong demand", "buy", "upside", "boost",
]
NEGATIVE_WORDS = [
    "fall", "falls", "falling", "drop", "drops", "decline", "declines",
    "bearish", "slump", "slumps", "plunge", "plunges", "sell-off", "selloff",
    "weak demand", "downside", "pressure", "lower", "retreat", "retreats",
]


def fetch_price_data():
    """Ambil data harga harian XAU/USD 3 bulan terakhir untuk analisis teknikal."""
    data = yf.download(GOLD_TICKER, period="3mo", interval="1d", progress=False)
    if data.empty:
        raise RuntimeError("Gagal mengambil data harga XAU/USD dari Yahoo Finance.")
    return data


def compute_technical_signal(data: pd.DataFrame):
    """Hitung SMA20, SMA50, dan RSI14, lalu tentukan bias teknikal beserta alasannya."""
    close = data["Close"]

    sma20 = close.rolling(window=20).mean()
    sma50 = close.rolling(window=50).mean()

    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    last_close = float(close.iloc[-1])
    last_sma20 = sma20.iloc[-1]
    last_sma50 = sma50.iloc[-1]
    last_rsi = rsi.iloc[-1]

    reasons = []
    score = 0

    if pd.notna(last_sma20) and pd.notna(last_sma50):
        if last_sma20 > last_sma50:
            score += 1
            reasons.append(
                f"SMA20 ({last_sma20:.2f}) di atas SMA50 ({last_sma50:.2f}) "
                "→ tren jangka pendek naik"
            )
        else:
            score -= 1
            reasons.append(
                f"SMA20 ({last_sma20:.2f}) di bawah SMA50 ({last_sma50:.2f}) "
                "→ tren jangka pendek turun"
            )

    if pd.notna(last_rsi):
        if last_rsi < 30:
            score += 1
            reasons.append(f"RSI14 = {last_rsi:.1f} → oversold, potensi rebound")
        elif last_rsi > 70:
            score -= 1
            reasons.append(f"RSI14 = {last_rsi:.1f} → overbought, potensi koreksi")
        else:
            reasons.append(f"RSI14 = {last_rsi:.1f} → netral")

    return {
        "score": score,
        "reasons": reasons,
        "last_close": last_close,
    }


def fetch_news_sentiment():
    """Ambil headline berita emas terbaru dan hitung skor sentimen sederhana berbasis kata kunci."""
    feed = feedparser.parse(NEWS_RSS_URL)
    entries = feed.entries[:10]

    score = 0
    headlines_used = []

    for entry in entries:
        title = entry.title.lower()
        pos_hits = sum(word in title for word in POSITIVE_WORDS)
        neg_hits = sum(word in title for word in NEGATIVE_WORDS)
        if pos_hits or neg_hits:
            score += pos_hits - neg_hits
            headlines_used.append(entry.title)

    return {
        "score": score,
        "headlines": headlines_used[:5],
    }


def build_signal_message(tech, news):
    total_score = tech["score"] + news["score"]

    if total_score >= 2:
        action = "BUY"
    elif total_score <= -2:
        action = "SELL"
    else:
        action = "HOLD / WAIT"

    lines = []
    lines.append(f"📊 <b>Sinyal XAU/USD — {action}</b>")
    lines.append(f"Harga terakhir: {tech['last_close']:.2f}")
    lines.append("")
    lines.append("<b>Analisis Teknikal:</b>")
    for r in tech["reasons"]:
        lines.append(f"• {r}")
    lines.append("")
    lines.append(f"<b>Sentimen Berita</b> (skor: {news['score']}):")
    if news["headlines"]:
        for h in news["headlines"]:
            lines.append(f"• {h}")
    else:
        lines.append("• Tidak ada headline relevan yang terdeteksi saat ini")
    lines.append("")
    lines.append(f"<i>Skor gabungan: {total_score} → {action}</i>")
    lines.append("⚠️ Ini bukan nasihat keuangan. Selalu lakukan riset & manajemen risiko sendiri.")

    return "\n".join(lines)


def send_telegram_message(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        raise RuntimeError("TELEGRAM_BOT_TOKEN atau TELEGRAM_CHAT_ID belum diset di environment.")

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
    }
    response = requests.post(url, data=payload, timeout=20)
    response.raise_for_status()
    return response.json()


def main():
    try:
        price_data = fetch_price_data()
        tech_signal = compute_technical_signal(price_data)
        news_signal = fetch_news_sentiment()
        message = build_signal_message(tech_signal, news_signal)
        send_telegram_message(message)
        print("Sinyal berhasil dikirim.")
        print(message)
    except Exception as e:
        error_message = f"⚠️ Bot sinyal XAU gagal berjalan: {e}"
        print(error_message, file=sys.stderr)
        try:
            send_telegram_message(error_message)
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
