# Bot Sinyal XAU/USD (Emas)

Bot ini mengirim sinyal BUY / SELL / HOLD untuk XAU/USD ke Telegram setiap jam, berdasarkan:
- **Analisis teknikal**: SMA20 vs SMA50, dan RSI14, dari data harga harian (Yahoo Finance).
- **Sentimen berita**: headline terbaru soal emas dari Google News RSS, dinilai sederhana lewat kata kunci positif/negatif.

Setiap sinyal disertai alasan singkat kenapa BUY/SELL/HOLD.

## Cara setup

1. **Buat repo GitHub baru**, lalu upload semua isi folder ini (`main.py`, `requirements.txt`, `.github/workflows/signal.yml`).

2. **Tambahkan secrets** di repo:
   - Buka `Settings` → `Secrets and variables` → `Actions` → `New repository secret`
   - Tambahkan:
     - `TELEGRAM_BOT_TOKEN` → token bot Telegram kamu
     - `TELEGRAM_CHAT_ID` → chat ID tujuan pengiriman sinyal

3. **Aktifkan Actions** (biasanya otomatis aktif setelah push).

4. Workflow akan berjalan otomatis **setiap jam** (cron `0 * * * *`, waktu UTC). Kamu juga bisa memicu manual lewat tab **Actions → XAU Signal Bot → Run workflow**.

## Uji coba lokal (opsional)

```bash
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN="isi_token"
export TELEGRAM_CHAT_ID="isi_chat_id"
python main.py
```

## Catatan & batasan

- Ticker harga yang dipakai: `XAUUSD=X` (Yahoo Finance). Jika sewaktu-waktu ticker ini bermasalah/limit, bisa diganti ke `GC=F` (future emas COMEX) di `main.py`.
- Sentimen berita saat ini berbasis kata kunci sederhana (bukan model NLP), jadi masih kasar — cukup untuk sinyal awal, bisa ditingkatkan nanti (misal pakai model sentiment analysis atau API berita berbayar).
- Cron GitHub Actions kadang telat beberapa menit dari jadwal karena antrian di sisi GitHub — ini normal.
- Bot ini murni alat bantu, **bukan nasihat keuangan**. Setiap sinyal yang dikirim juga menyertakan disclaimer ini.

## Ide pengembangan lanjutan

- Tambah indikator lain (MACD, Bollinger Bands).
- Ganti sentimen kata kunci dengan model NLP yang lebih akurat.
- Simpan histori sinyal (misal ke file CSV di repo atau database) untuk evaluasi performa dari waktu ke waktu.
- Kirim chart harga sebagai gambar bersama sinyal.
