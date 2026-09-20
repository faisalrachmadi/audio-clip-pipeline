---
name: insert-radio
description: "Pipeline otomatis YouTube -> transcript -> analisis AI -> potong clip audio/video untuk insert radio. 3 tahap: cek transcript, analisis via OpenCode Go deepseek-v4.1-flash, potong FFmpeg parallel. Flag --audio untuk output MP3 (audio-only). Jumlah clip otomatis menyesuaikan durasi & kualitas konten."
version: 1.31.0
# Changelog lengkap: references/changelog.md
# 1.31.0 - GUARD REPARASI (opsi b): boundary diperbaiki, bukan dibuang. Overlap digeser, clip pendek
#          dipanjangkan/digabung, clip kepanjangan dipecah ke batas kalimat transcript. Nama pecahan diberi
#          sufiks bagian-N + strip prefix bertingkat (02_02a_). Hasil uji: 3 clip -> 5 clip.
# 1.30.0 - KONSEP durasi: durasi MENGIKUTI KONTEKS (panjang topik), bukan target. Rentang --min/--max = lazim,
#          bukan pagar keras. Batas keras HARD_MIN/HARD_MAX (default 2.5-10 mnt) untuk buang yang ekstrem saja.
#          Guard overlap beri toleransi 1s (boundary bersinggungan bukan overlap). Hapus aturan "WAJIB BERAGAM".
# 1.29.0 - FIX durasi seragam 5:00: prompt + pesan re-ask kini larang durasi seragam/angka bulat,
#          validasi deteksi durasi seragam (>=3 clip sama) -> re-ask. Root cause: re-ask menyebut rentang
#          dalam detik membuat AI mengunci ke 300s. Hasil uji: 281/308/280/332/287s (5 nilai unik).
# 1.28.0 - FIX deteksi ustadz: judul dengan tulisan Arab (doa spt حفظه الله) / emoji / [LIVE] gagal match
#          karena kelas regex [A-Za-z] -> normalisasi judul dulu (_normalisasi_judul). Juga fix "Hudzaifah"->"udzaifah".
# 1.27.0 - OPTIMASI: probe durasi via ffprobe (baca header ~0.03s) ganti ffmpeg decode penuh (~3s) di 3 tempat;
#          tag album buang separator menggantung; hapus dead code (_durs).
# 1.26.0 - REKONSILIASI dari branch main: prompt KONTEKS UTUH (SUB-TOPIK + TES AKHIR + prioritas keutuhan),
#          --clips default 5 (fixed), bersihkan_gelar() hapus gelar akademik, pitfall video DUO. Mesin tetap versi server-linux.
# 1.25.0 - Tambah "Checklist Progres (per Tahap)" — panduan pelaporan progres rinci per tahap + verifikasi.
# 1.24.0 - Model Tahap 2 kembali ke OpenCode Go `deepseek-v4.1-flash` (saldo pulih 2026-09-19). Ganti provider: `AI_PROVIDER=opencode|openrouter`.
# 1.23.0 - SKILL.md dirampingkan; detail dipindah ke references/ (pitfalls.md, prompt-rules.md, changelog.md, flat-output.md)
# CHANGES:
# 1.22.0 - GUARD OVERLAP: Tahap 2 deteksi clip tumpang tindih -> minta AI perbaiki; Tahap 3 urutkan & buang clip overlap (deterministik).
#       - Catatan kualitas: AI cenderung mengunci durasi ke 300s (5:00) & memaksa batas -> rawan potong konteks/overlap.
# 1.21.0 - PROVIDER SWITCH via env AI_PROVIDER (openrouter | opencode). Default: openrouter (OpenCode Go saldo habis).
---

# Insert Radio

Pipeline 3 tahap dari link YouTube sampai clip MP3 siap pakai sebagai insert radio/kajian.

## Trigger

User kirim link YouTube. **Cukup URL aja** — pipeline otomatis:
1. Cek ketersediaan transcript
2. Hitung jumlah clip dari durasi video (÷4, skip 5 awal + 5 akhir)
3. Proses sampai clip MP4 (talkshow) atau MP3 (kajian) jadi

Override opsional: `--clips N`, `--min M`, `--max M`, `--skip-start M`

## Default

**Sekarang default video (MP4) untuk talkshow radio:**
- **Clip:** auto (÷4 dari durasi efektif)
- **Durasi:** 1-2 menit (talkshow), atau **4-6 menit** kalau explicit `--min 4 --max 6` (kajian)
- **Output:** `.mp4` dengan video stream copy (`-c:v copy`) + audio loudnorm
- **AI Prompt:** talkshow radio — hindari break/iklan, cari segmen engaging

### Perubahan dari versi MP3 sebelumnya

| Aspek | MP3 (kajian, old default) | MP4 (talkshow, new default) |
|-------|--------------------------|----------------------------|
| Download | `yt-dlp -x` → MP3 | `yt-dlp` → MP4 |
| Durasi clip | 4-6 menit | 1-2 menit |
| FFmpeg output | `-vn` (audio only) | `-c:v copy` + audio filter |
| Auto clip hitung | ÷10 (konservatif) | ÷4 (lebih banyak clip) |
| AI fokus | Kajian Islam (hindari opening/adzan/closing) | Talkshow radio (hindari break/iklan) |
| Metadata | ID3 (mp3) | MP4 metadata + `-movflags +faststart` |
| Bug fix | `download_audio()` undefined! | Pakai `download_video()` yg sudah ada |

Untuk konten KAJIAN (ceramah), gunakan parameter eksplisit:
```bash
python pipeline.py <URL> --min 4 --max 6 --clips 5
```

> **⚠️ Catatan server Linux ini (2026-09-14, diperbarui 2026-09-19):** Pipeline yang terpasang di `/home/faisal/.openclaw/workspace/insert-radio/` adalah **varian AUDIO/MP3 (kajian)** — download `yt-dlp -x` → MP3, output `.mp3`, tanpa flag `--audio`, default `--min 4 --max 6`. Varian MP4/talkshow yang dijelaskan di bagian "Default" di atas TIDAK ada di server ini (hanya di mesin Windows).
>
> **Perubahan v1.26.0 (rekonsiliasi dari branch `main`):** `--clips` default **5 (fixed, bukan auto)**; prompt wajib **KONTEKS UTUH** (topik dari awal sampai tuntas, cari sub-topik kalau > max, **TES AKHIR** per clip, prioritas: keutuhan konteks > jumlah clip > durasi); `bersihkan_gelar()` otomatis hapus gelar akademik dari nama ustadz.
>
> **Perubahan v1.31.0 (guard reparasi):** Tahap 3 tidak lagi sekadar membuang clip bermasalah, tapi **memperbaiki**: overlap → start digeser ke akhir clip sebelumnya (snap batas kalimat); terlalu pendek → dipanjangkan atau digabung ke clip sebelumnya; terlalu panjang → **dipecah** jadi beberapa bagian di batas kalimat transcript (nama diberi sufiks `-bagian-N`).
>
> **Perubahan v1.30.0 (durasi mengikuti konteks):** `--min/--max` = panjang **lazim**, bukan pagar keras. Durasi tiap clip = jarak dari topik DIBUKA sampai TUNTAS; boleh keluar dari 4–6 menit kalau topiknya memang begitu. Yang dibuang hanya durasi **ekstrem**: `HARD_MIN_SEC`/`HARD_MAX_SEC` (env `HARD_MIN_MINUTES=2.5`, `HARD_MAX_MINUTES=10`). Guard overlap bertoleransi 1 detik (boundary bersinggungan ≠ overlap).

## Execution

### Single Video → Terminal Langsung

Untuk **1 URL**, jalankan langsung via terminal command (sub-agent tidak diperlukan — hanya tambah overhead). Cukup cd ke working directory + activate venv + run pipeline.py.

### Multi Video / Batch → Sequential untuk API, Paralel untuk FFmpeg

Untuk **2+ URL**, jalankan **sequential** untuk hindari API rate limit (HTTP 500/timeout):

**JANGAN** jalankan 4+ pipeline barengan — OpenCode Go API akan overwhelmed.
**IDEAL:** Max 2 paralel untuk video pendek (<30 menit), 1 per satu untuk video panjang (>30 menit / transcript >30K chars).

Setelah tahap 2 (AI) selesai, tahap 3 (FFmpeg) tetap paralel per clip — ini aman karena lokal CPU.

## Tooling

- **Apify API** -> ambil transcript YouTube (actor: `pintostudio~youtube-transcript-scraper`)
- **yt-dlp** -> download video MP4 (`--merge-output-format mp4`)
- **OpenCode Go API** (opencode.ai/zen/go/v1, model mimo-v2.5) -> analisis transcript -> generate perintah potong
- **FFmpeg** -> potong clip (video: `-c:v copy`, audio: loudnorm + afade)
- **convert_subs.py** (di `1. apify + audio/`) -> konversi YouTube JSON3 auto-captions → format Apify transcript. Gunakan saat transcript gagal via Apify (`python convert_subs.py input.json3 output.json`)
- **script.pyw** (di `3. aplikasi potong kajian/`) -> GUI Tkinter untuk FFmpeg batch processing manual dari .bat file. Alternatif saat pipeline otomatis tidak bisa dipakai.
- **Analisa json/** (di `2. Analisa json/`) -> folder untuk data analisis (output AI), biasanya berisi `potong.bat` + `potong_log_alasan.md` setelah Tahap 2 selesai.

## Parameters

| Arg | Default | Deskripsi |
|-----|---------|-----------|
| `URL` | (required) | Link YouTube |
| `--clips N` | 5 | Jumlah clip (default 5; isi 0 untuk mode auto berdasarkan durasi) |
| `--min M` | 4 | Durasi minimal per clip menit |
| `--max M` | 6 | Durasi maksimal per clip menit |
| `--skip-start N` | 0 | Skip N menit awal video (berguna kalau intro panjang/sebelum konten dimulai) |
| `--audio` | false | Audio-only mode (MP3 output, tanpa video stream) |

## Step-by-step

### Tahap 1: Cek Transcript → Video → Hitung Clip
1. Cek cache transcript.json — kalau ada dan valid, skip Apify (optimasi C)
2. Jika tidak ada cache: fetch transcript via Apify API dulu
3. Validasi seg_count > 0 — **kalau 0, hentikan pipeline sekarang juga. JANGAN fallback ke faster-whisper.** Cukup lapor kegagalan ke user.
4. Jika transcript valid, download video MP4 via `download_video()` (yt-dlp `--merge-output-format mp4`, retry 1x)
5. Hitung otomatis jumlah clip dari durasi video (efektif -10 menit, ÷4 untuk talkshow 1-2 menit)

### Tahap 2: Analisis AI
1. Baca transcript.json, extract ke format `[start - dur:dur] text`
2. Jika `--skip-start` > 0, filter out semua segmen sebelum `skip_start * 60` detik (log: "⏭️ N segmen awal di-skip")
3. Kirim ke provider AI aktif (`AI_PROVIDER`: `openrouter` | `opencode`) dengan system prompt. WAJIB kirim `reasoning_effort=none` (di OpenRouter & OpenCode Go sama-sama penting: tanpa itu Tahap 2 bisa 89-660s+/timeout; dengan itu ~3-30s).
4. Params: jumlah_clip, durasi_min, durasi_max
5. Simpan log analisis (potong_log_alasan.md)
6. Ekstrak .BAT dari response AI (potong.bat)

### Tahap 3: Potong Audio (Parallel FFmpeg)
1. Parse .bat → daftar perintah ffmpeg
2. Ganti input → audio_full.mp3, output → 3_hasil_potong/
3. Eksekusi parallel via ThreadPoolExecutor (MAX_WORKERS = CPU count)

## Checklist Progres (per Tahap)

Gunakan ini untuk melaporkan progres (progress card + pesan singkat) tiap run. Tandai item saat selesai; jangan lompat tahap. Baca detail di `references/pitfalls.md` bila ada item yang gagal.

### T0 — Preflight
- [ ] URL dibersihkan (buang param `&pp=`/tracking) & valid
- [ ] Ambil judul video (yt-dlp)
- [ ] Cek takarir ada (`yt-dlp --list-subs`) → kalau kosong: **STOP + lapor**

### T1 — Transcript & Audio
- [ ] Cek cache `1_apify/transcript.json` (skip Apify kalau valid)
- [ ] Fetch transcript Apify (`targetLanguage=id`)
- [ ] Validasi segmen > 0 (kalau 0 → STOP)
- [ ] Hitung jumlah clip dari durasi (efektif −10 mnt, ÷10 utk kajian 4-6 mnt)
- [ ] Unduh audio (`yt-dlp -x ... --js-runtimes node`)
- [ ] Cek `audio_full.mp3` ada & ukuran wajar

### T2 — Analisis AI
- [ ] Extract transcript → `[start - dur] text`
- [ ] Filter `--skip-start` (bila diisi)
- [ ] Kirim ke provider aktif (`reasoning_effort=none`)
- [ ] Validasi **durasi ekstrem (HARD_MIN/HARD_MAX) + overlap (toleransi 1s)** → re-ask AI 1× bila melanggar
- [ ] Simpan `2_analisa/potong_log_alasan.md`
- [ ] Simpan `2_analisa/potong.bat` (blok ffmpeg)

### T3 — Potong Audio
- [ ] Parse `.bat` → daftar perintah ffmpeg
- [ ] Guard REPARASI: snap boundary ke kalimat, geser overlap, panjangkan/gabung yang pendek, pecah yang panjang
- [ ] Eksekusi paralel (ThreadPoolExecutor)
- [ ] Verifikasi semua file ada & playable (`ffprobe`)

### Post-Processing
- [ ] Deteksi nama ustadz dari judul
- [ ] Rename Title Case → `Judul - Ustadz Nama.mp3`
- [ ] Tulis metadata ID3 (title/artist/album/date)
- [ ] Hapus `audio_full.mp3` (hemat space)

### Publish (skill `publish-kajian-audio`, cron 5 mnt)
- [ ] Mirror `/srv/nextcloud-kajian/<folder>/` (MP3 + `cover.jpg`)
- [ ] Cover per ustadz (`assign_covers.py`)
- [ ] Halaman web `/srv/dakwah/index.html`
- [ ] Nextcloud `occ files:scan`
- [ ] Navidrome `scan`

### Verifikasi Akhir
- [ ] `ls 3_hasil_potong/` → file benar-benar ada (jangan percaya self-report)
- [ ] Cek ghost Navidrome (`missing=0`)
- [ ] Laporkan: jumlah clip, durasi tiap clip, path output, waktu per tahap

## Output Structure

```output/dd-mm-yyyy_judul/
├── 1_apify/
│   ├── transcript.json
│   └── video_full.mp4          # sebelumnya: audio_full.mp3
├── 2_analisa/
│   ├── potong.bat
│   └── potong_log_alasan.md
└── 3_hasil_potong/
    ├── Metode Menghafal Al Quran - Ustadz Khalid Basalamah.mp4
    └── ...
```

## Post-Processing (Rename & Metadata)

Setelah clip terpotong, pipeline otomatis:
1. **Deteksi nama ustadz** dari judul video:
   - Cari prefix: `Ustadz`, `Ustad`, `Ust.`/`Ust`, `KH.`, `Kyai`, `Syekh`/`Syaikh`, `Aa`/`A'a` (prefix Sundanese untuk tokoh agama seperti Aa Gym) (support apostrophe: `Rofi'i`, `Atho'illah`)
   - Fallback: ambil segmen terakhir setelah separator `|` `–` `—`
   - Potong semua setelah koma (gelar), bersihkan `[...]` di akhir
   - Hapus singkatan gelar di depan (Dr., H., Hj., Prof., KH., dll)
   - "Ust." atau "Ust" (tanpa titik) → otomatis jadi "Ustadz"
   - Tambah "Ustadz" di depan jika belum ada prefix (dari fallback: "Khalid Basalamah" → "Ustadz Khalid Basalamah")
   - Ambil max 6 kata
2. **Rename clip** format Title Case dengan spasi:
   - Ada ustadz: `Metode Menghafal Al Quran - Ustadz Abdul Somad.mp3`
   - Tanpa ustadz: `Metode Menghafal Al Quran.mp3`
   - Nomor urut dihapus, kebab-case → Title Case
3. **Tambahkan metadata ID3** (tanpa re-encode via `-c copy`):
   - **Title** → judul clip (Title Case)
   - **Artist** → nama ustadz (atau fallback ambil dari judul)
   - **Album** -> judul video **tanpa nama ustadz** (dibersihkan otomatis: "Ustadz X - Judul" -> "Judul", atau "Judul | Ustadz X" -> "Judul")
   - **Date** -> tahun berjalan (2026, dst)
   - **MP4 streaming:** `-movflags +faststart` untuk web optimization

> **Catatan:** metadata tergantung output format. MP4 pakai `-metadata` ffmpeg, MP3 pakai ID3 (`-write_id3v1 1 -id3v2_version 3`). Pipeline sekarang default MP4.
```

## ⚠️ Aturan Delivery
**JANGAN kirim file audio (.mp3) ke user.** Cukup laporkan hasil pipeline: jumlah clip, durasi, dan path output-nya. Audio hanya untuk disimpan lokal, bukan untuk dikirim ke Telegram.

## Script Path

Pipeline berjalan di **Linux** (server OpenClaw ini):

| Prioritas | Path | Keterangan |
|-----------|------|------------|
| #1 | `/home/faisal/.openclaw/workspace/insert-radio/pipeline.py` | Path utama (Linux) |
| #2 | `D:\Insert Automation\Insert maker\automate insert-video\pipeline.py` | Windows (legacy) |

Cek dengan `ls` untuk menentukan mana yang tersedia.
## Cara Run

Setup Linux sudah lengkap (yt-dlp, ffmpeg, requests, python-dotenv terpasang; yt-dlp binary terbaru di `/usr/local/bin`). Tidak perlu venv:

```bash
cd /home/faisal/.openclaw/workspace/insert-radio
python3 pipeline.py <URL> [--clips N] [--min M] [--max M] [--skip-start M]
```

Gunakan **background mode** untuk video panjang (download audio butuh beberapa menit).

Cukup kirim link — clip otomatis dihitung (default 4-6 menit, MP3 audio):
```bash
python3 pipeline.py "https://youtube.com/watch?v=..."
```

Kajian (4-6 menit, eksplisit):
```bash
python3 pipeline.py "https://youtube.com/watch?v=..." --min 4 --max 6
```

Override jumlah clip manual:
```bash
python3 pipeline.py "https://youtube.com/watch?v=..." --clips 10
```
## Batasi Durasi Video (Hanya N Menit Pertama)

Pipeline tidak punya parameter `--max-duration`. Untuk mengambil clip hanya dari N menit pertama video:

1. **Siapkan folder output & fetch transcript manual** (seperti Tahap 1 tapi terkontrol)
2. **Filter transcript.json** — hanya pertahankan segmen dengan `start < N*60` detik
3. **Download audio** full, lalu trim ke N menit dengan ffmpeg
4. **Jalankan pipeline** — karena transcript.json & audio_full.mp3 sudah ada, pipeline skip Tahap 1 dan langsung Tahap 2 & 3

Detail langkah dan kode ada di `references/trim-to-duration.md`.

**Catatan:** Jumlah clip otomatis tetap dihitung dari durasi hasil trim (bukan durasi video asli). Sesuaikan dengan `--clips N` jika perlu.

## GitHub Repo (Public)

Pipeline ini dishare via repo publik:  
🌐 **https://github.com/faisalrachmadi/audio-clip-pipeline**

Isi repo: `pipeline.py`, `requirements.txt`, `.env.example`, `README.md`, dan folder `skill/`.

## Referensi Internal

Detail besar ada di `references/` (baca hanya yang perlu, jangan semua):

- `references/pitfalls.md` — daftar LENGKAP pitfalls + fix (baca ini saat ada error)
- `references/prompt-rules.md` — aturan prompt AI (K1-K10 kajian, T1-T8 talkshow)
- `references/changelog.md` — riwayat versi lengkap
- `references/flat-output.md` — copy clip ke folder flat (legacy)
- `references/trim-to-duration.md` — trim ke N menit pertama
- `references/pipeline-modifications.md` — riwayat modifikasi pipeline.py
- `references/github-info.md` — info repo GitHub
- `references/ustadz-detection-failures.md` — kasus deteksi ustadz gagal
- `references/yt-dlp-cookies-auth.md` — troubleshooting 429/cookies (auth)
- `references/transcript-format.md` — format JSON transcript Apify
- `references/talkshow-video-variant.md` — perubahan MP3 -> MP4

## Pitfalls Penting (ringkas)

Detail lengkap + cara fix: `references/pitfalls.md`.

- **Video tanpa takarir:** transcript kosong -> STOP, jangan fallback whisper. Konfirmasi `yt-dlp --list-subs <URL>`.
- **Bahasa transcript:** wajib `targetLanguage='id'` (default). Ganti bahasa -> hapus `1_apify/transcript.json` dulu.
- **Kecepatan AI:** kirim `reasoning_effort=none` (OpenRouter & OpenCode). Tanpa itu 89-660s / timeout.
- **CreditsError 401 (saldo habis):** lapor ke user, JANGAN retry beruntun; simpan cache Tahap 1.
- **Guard durasi & overlap:** clip wajib dalam `--min`-`--max` menit & tidak tumpang tindih (Tahap 2 re-ask, Tahap 3 skip).
- **Deteksi ustadz bisa salah:** verifikasi nama & rename manual bila perlu.
- **Cache:** `1_apify/transcript.json` + `audio_full.mp3`; audio dihapus otomatis setelah sukses.
- **Selalu verifikasi:** `ls 3_hasil_potong/` setelah selesai (jangan percaya self-report).