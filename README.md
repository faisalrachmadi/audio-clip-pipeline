# Audio Clip Pipeline 🎙️

Pipeline otomatis YouTube → Transcript → Analisis AI → Potong Clip MP3/MP4 untuk konten kajian/podcast/talk show.

## Fitur

- **3 Tahap Otomatis:** Download transcript & audio → Analisis AI → Potong clip
- **AI-Powered:** Pilih momen terbaik via OpenCode Go (deepseek-v4.1-flash)
- **Parallel FFmpeg:** Potong semua clip bersamaan (kencang!)
- **Mode Audio/Video:** `--audio` untuk MP3 (kajian), default MP4 (talkshow)
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
# Edit .env: isi APIFY_TOKEN & OPENCODE_GO_API_KEY
```

### 2. Jalankan

```bash
python pipeline.py <URL_YOUTUBE> [--clips N] [--min M] [--max M] [--skip-start M] [--audio]
```

Contoh:
```bash
# Default MP4 talkshow (auto clip, 1-2 menit)
python pipeline.py "https://youtu.be/abc123"

# Audio-only kajian (2 clip, 4-6 menit)
python pipeline.py "https://youtu.be/abc123" --audio --clips 2 --min 4 --max 6

# Skip 10 menit awal (kajian mulai setelah pembukaan)
python pipeline.py "https://youtu.be/abc123" --audio --clips 4 --min 4 --max 6 --skip-start 10
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
| **yt-dlp** | `C:\yt-dlp_win\yt-dlp.exe` | Download audio/video YouTube |
| **FFmpeg** | `C:\ffmpeg...\bin\ffmpeg.exe` | Potong clip |
| **Apify API Key** | `.env` | Ambil transcript YouTube |
| **OpenCode Go API Key** | `.env` | Analisis AI (OPENCODE_GO_API_KEY) |

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
| `--clips N` | 5 | Jumlah clip (default **5**; isi `0` kalau mau mode auto dari durasi) |
| `--min M` | 4 | Durasi minimal per clip (menit) |
| `--max M` | 6 | Durasi maksimal per clip (menit) |
| `--skip-start N` | 0 | Skip N menit awal (untuk opening panjang) |
| `--audio` | false | Audio-only mode (MP3 output) |

## Kebijakan Clip (penting)

- **Default 5 clip** (`--clips` default = 5), bukan auto.
- **Keutuhan konteks > jumlah.** Tiap clip WAJIB satu topik **utuh** — mulai saat topik dibuka, berakhir setelah topik tuntas. Tidak boleh potong di tengah kalimat/cerita/alur.
- Kalau transcript tidak punya cukup topik utuh yang bermutu, **lebih baik hasilnya kurang dari 5** — jangan mengejar jumlah dengan memotong konteks.
- Kalau satu topik lebih panjang dari `--max`, cari **sub-topik** yang utuh di dalamnya (punya pembuka & penutup sendiri) atau pilih topik lain yang muat.
- AI diminta menuliskan kutipan **"Awal topik"** & **"Akhir topik"** per clip di `2_analisa/potong_log_alasan.md` — pakai itu untuk memverifikasi boundary-nya benar-benar utuh.

## Panduan AI (Prompt Rules)

AI di-prompt untuk:
1. Cari **transisi topik**, bukan potong per menit
2. **HINDARI opening** (salam, basmalah, perkenalan)
3. **HINDARI adzan** (jeda adzan di tengah)
4. **HINDARI closing** (doa penutup, wassalam, pengumuman)
5. Durasi clip WAJIB dalam rentang yang ditentukan
6. Clip dari topik berbeda, tersebar di seluruh video
7. No overlap antar clip
8. Jumlah clip bisa kurang dari yang diminta jika konten tidak mendukung (kualitas > kuantitas)

## Catatan Penting (OpenCode Go)

1. **Header `x-opencode-session` WAJIB.** Sejak 2026-09-05 OpenCode Go menolak request tanpa header ini (HTTP 400 `MissingSessionID`). Pipeline mengirim `str(uuid.uuid4())` per run. Kalau muncul error itu, pastikan header-nya terkirim.
2. **Request API harus SEQUENTIAL.** Jangan jalankan beberapa video bersamaan — beberapa request serentak bikin OpenCode Go balas HTTP 500 `Internal server error`. Untuk batch, pakai `run_sequential.py` (menjalankan URL satu per satu). Yang boleh paralel hanya proses potong FFmpeg di dalam satu video.
3. **HTTP 500 bisa transient.** Kalau kena HTTP 500, retry biasanya berhasil. Transcript sudah di-cache, jadi retry langsung masuk Tahap 2 tanpa download ulang.
4. **Transcript besar:** 40–60K chars aman dengan timeout 1200s. Di atas ~70K chars rawan gagal — pakai `--clips 7` supaya prompt lebih ringan.
5. **Video tanpa auto-caption YouTube akan gagal** di Tahap 1 (`Transcript kosong`). Itu bukan bug pipeline — YouTube-nya memang belum punya subtitle.

## Lisensi

MIT — bebas pakai, modifikasi, dan share.
