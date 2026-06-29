# Audio Clip Pipeline 🎙️

Pipeline otomatis YouTube → Transcript → Analisis AI → Potong Clip MP3 untuk konten kajian/podcast/talk show.

## Fitur

- **3 Tahap Otomatis:** Download transcript & audio → Analisis AI → Potong clip MP3
- **AI-Powered:** Pilih momen terbaik via OpenRouter (DeepSeek V4 Flash)
- **Parallel FFmpeg:** Potong semua clip bersamaan (kencang!)
- **Deteksi Ustadz:** Otomatis deteksi & rename nama ustadz dari judul video
- **Metadata ID3:** Setiap clip dikasih title, artist, album, date
- **Cache Transcript:** Skip ulang download kalau transcript udah ada

## Cara Pakai

### 1. Clone & Setup

```bash
git clone https://github.com/faisalrachmadi/audio-clip-pipeline.git
cd audio-clip-pipeline/pipeline

# Setup venv
python -m venv venv
source venv/Scripts/activate  # Windows
# source venv/bin/activate    # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Copy & isi .env
cp .env.example .env
# Edit .env: isi APIFY_TOKEN & OPENROUTER_API_KEY
```

### 2. Jalankan

```bash
python pipeline.py <URL_YOUTUBE> [--clips N] [--min M] [--max M] [--skip-start M]
```

Contoh:
```bash
# Default (5 clip, 4-6 menit)
python pipeline.py "https://youtu.be/abc123"

# 3 clip, 5-7 menit per clip
python pipeline.py "https://youtu.be/abc123" --clips 3 --min 5 --max 7

# Skip 10 menit awal (kajian mulai setelah pembukaan)
python pipeline.py "https://youtu.be/abc123" --clips 4 --min 4 --max 6 --skip-start 10
```

### 3. Output

```
output/YYYY-MM-DD_judul/
├── 1_apify/
│   ├── transcript.json
│   └── audio_full.mp3  (dihapus otomatis setelah selesai)
├── 2_analisa/
│   ├── potong.bat
│   └── potong_log_alasan.md
└── 3_hasil_potong/
    ├── Judul Clip 1 - Ustadz Nama.mp3
    ├── Judul Clip 2 - Ustadz Nama.mp3
    └── ...
```

## Prerequisites

| Tool | Lokasi | Catatan |
|------|--------|---------|
| **Python 3.10+** | `python` | Script utama |
| **yt-dlp** | `C:\yt-dlp_win\yt-dlp.exe` | Download audio YouTube |
| **FFmpeg** | `C:\ffmpeg...\bin\ffmpeg.exe` | Potong audio |
| **Apify API Key** | `.env` | Ambil transcript YouTube |
| **OpenRouter API Key** | `.env` | Analisis AI |

## Skill (Hermes Agent)

Folder `skill/` berisi file skill untuk **Hermes Agent** — LLM agent yang bisa otomatis
menjalankan pipeline via chat/Telegram.

Cara pakai di Hermes Agent:
```bash
hermes skill add insert-radio ./skill/SKILL.md
```

## Parameter

| Arg | Default | Deskripsi |
|-----|---------|-----------|
| `URL` | (wajib) | Link YouTube |
| `--clips N` | 0 (auto) | Jumlah clip (0=otomatis dari durasi) |
| `--min M` | 4 | Durasi minimal per clip (menit) |
| `--max M` | 6 | Durasi maksimal per clip (menit) |
| `--skip-start N` | 0 | Skip N menit awal (untuk opening panjang) |

## Panduan AI (Prompt Rules)

AI di-prompt untuk:
1. Cari **transisi topik**, bukan potong per menit
2. **HINDARI opening** (salam, basmalah, perkenalan)
3. **HINDARI adzan** (jeda adzan di tengah)
4. **HINDARI closing** (doa penutup, wassalam, pengumuman)
5. Durasi clip WAJIB dalam rentang yang ditentukan
6. Clip dari topik berbeda, tersebar di seluruh video
7. No overlap antar clip

## Lisensi

MIT — bebas pakai, modifikasi, dan share.
