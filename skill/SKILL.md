---
name: insert-radio
description: "Pipeline otomatis YouTube -> transcript -> analisis AI -> potong clip audio/video untuk insert radio. 3 tahap: cek transcript, analisis via OpenCode Go (deepseek-v4.1-flash), potong FFmpeg parallel. Flag --audio untuk output MP3 (audio-only). Jumlah clip otomatis menyesuaikan durasi & kualitas konten."
version: 1.20.0
# CHANGES:
# 1.20.0 - Kebijakan clip: default 5 (fixed, BUKAN auto); boleh < 5 kalau materi tak cukup
#       - Prompt: wajib konteks utuh (topik dari awal sampai tuntas) + tes akhir per clip
#       - Diterapkan ke KEDUA pipeline.py (automate insert & automate insert-video)
# 1.19.0 - Model Tahap 2: OpenCode Go mimo-v2.5 -> deepseek-v4.1-flash
#       - WAJIB header `x-opencode-session` (OpenCode Go menolak tanpa ini sejak 2026-09-05, HTTP 400 MissingSessionID)
#       - Request API harus SEQUENTIAL (paralel -> HTTP 500 Internal server error)
# 1.18.0 - Switched AI model: DeepSeek V4 Flash -> OpenCode Go mimo-v2.5
#       - Added --audio flag for audio-only mode (MP3 output)
#       - Output folder changed to D:\Insert Automation\Insert maker\automate insert\output
# 1.17.0 - Updated OpenRouter refs -> DeepSeek Direct (api.deepseek.com, deepseek-v4-flash)
#       - deepseek-chat deprecated (HTTP 400), only deepseek-v4-pro/flash accepted
# 1.16.0 - Added terminal-corrupted workaround (execute_code + subprocess.Popen)
#       - Added yt-dlp .part file lock recovery (kill yt-dlp + delete .part)
#       - Added user preference: "Ustadz" not "Ust"
#       - Added ustadz-detection-failures.md Kasus 7 (Ust → Ustadz) & Kasus 8
# 1.14.0 - Added ustadz-detection-failures.md Kasus 6: prefix "Ustadz" diikuti teks deskriptif (bukan nama orang)
#       - Updated pitfall "Deteksi ustadz bisa gagal" untuk mencakup varian prefix match palsu
# 1.13.0 - Default berubah ke Talkshow MP4 mode
#       - Added pitfall: yt-dlp sometimes saves audio as .m4a instead of .mp3
# 1.11.0 - Corrected pty=true MSYS workaround (tidak selalu bisa reset corrupted session)
#       - Added medium-video timing reference (~45 min video) to total runtime pitfall
# 1.10.0 - Added 3 pitfalls: YouTube 429 rate limit, --cookies-from-browser fails when browser running, ended live streams need cookies
#       - New reference: yt-dlp-cookies-auth.md (troubleshooting auth failures, oEmbed fallback)
# 1.9.0 - Updated script path to include `automate insert-video` variant
#       - Added convert_subs.py, script.pyw, and Analisa json/ to Tooling section
#       - New reference: transcript-format.md (Apify JSON format, YouTube JSON3 conversion)
#       - Updated "Audio only" pitfall to mention video extension path
# 1.8.0 - Added pitfall: total runtime for very long videos (90-180min)
#       - Covers tool-call iteration limit impact when running via Hermes agent
# 1.7.0 - Added 3 pitfalls for pipeline monitoring:
#       - yt-dlp \r progress invisible in logs
#       - seg_count as video-length signal
#       - progress monitoring via output directories
# 1.6.0 - Extended sub-agent verification pitfall to cover direct runs
#       - Added OpenRouter API hang/timeout pitfall with retry pattern
# 1.4.0 - Relaxed "WAJIB via sub-agent" → single-video can run directly
#       - Added Windows MSYS terminal foreground pitfall + background workaround
#       - Cara Run section now recommends background mode
# 1.3.0 - Added GitHub repo link + github-info.md reference
#       - Added pitfalls: flat output danger, ustadz detection failure, sub-agent verify, &pp URL param
# 1.2.0 - Updated Prompt Rules to match actual pipeline.py (initial opening/adzan/closing rules)
---

# Insert Radio

Pipeline 3 tahap dari link YouTube sampai clip MP3 siap pakai sebagai insert radio/kajian.

## Trigger

User kirim link YouTube. **Cukup URL aja** — pipeline otomatis:
1. Cek ketersediaan transcript
2. Ambil **5 clip** (default tetap — bukan auto)
3. Proses sampai clip MP3 (kajian/insert radio) atau MP4 (talkshow) jadi

Override opsional: `--clips N`, `--min M`, `--max M`, `--skip-start M`

## Default

**KEBIJAKAN CLIP (berlaku untuk insert radio/kajian — sudah default di pipeline):**
- **Clip: 5 (fixed, bukan auto).** `--clips` default = 5. Jangan pakai mode auto lagi.
- **Kualitas & keutuhan dulu, bukan jumlah.** Kalau transcript tidak punya cukup topik utuh yang bermutu, **LEBIH BAIK hasil < 5 clip**. Jangan paksa 5 dengan memotong konteks.
- **Durasi:** **4-6 menit** (`--min 4 --max 6`), output MP3 (`--audio`).
- **KONTEKS WAJIB UTUH (prioritas tertinggi):** tiap clip = SATU topik dari awal sampai tuntas — mulai saat topik dibuka, berakhir setelah topik selesai. Jangan potong di tengah kalimat/cerita/alur. Kalau satu topik > `--max`, cari SUB-TOPIK yang utuh di dalamnya atau pilih topik lain — jangan potong asal di tengah.
- **AI Prompt** sudah memuat aturan ini (section "ATURAN KONTEKS (WAJIB)" + tes akhir per clip) — hindari opening/adzan/iklan/closing.
- **Verifikasi hasil:** tiap clip wajib punya kutipan "Awal topik" & "Akhir topik" di `2_analisa/potong_log_alasan.md` — itu tanda boundary-nya topik utuh, bukan potongan waktu asal.

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

Perintah **standar insert radio/kajian** (clip sudah default 5):
```bash
python pipeline.py <URL> --audio --min 4 --max 6
```

Untuk talkshow (MP4):
```bash
python pipeline.py <URL>
```

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
- **OpenCode Go API** (opencode.ai/zen/go/v1, model deepseek-v4.1-flash) -> analisis transcript -> generate perintah potong
- **FFmpeg** -> potong clip (video: `-c:v copy`, audio: loudnorm + afade)
- **convert_subs.py** (di `1. apify + audio/`) -> konversi YouTube JSON3 auto-captions → format Apify transcript. Gunakan saat transcript gagal via Apify (`python convert_subs.py input.json3 output.json`)
- **script.pyw** (di `3. aplikasi potong kajian/`) -> GUI Tkinter untuk FFmpeg batch processing manual dari .bat file. Alternatif saat pipeline otomatis tidak bisa dipakai.
- **Analisa json/** (di `2. Analisa json/`) -> folder untuk data analisis (output AI), biasanya berisi `potong.bat` + `potong_log_alasan.md` setelah Tahap 2 selesai.

## Parameters

| Arg | Default | Deskripsi |
|-----|---------|-----------|
| `URL` | (required) | Link YouTube |
| `--clips N` | 5 | Jumlah clip (default 5; isi 0 kalau mau mode auto berdasarkan durasi) |
| `--min M` | 1 | Durasi minimal per clip menit (default: 1 utk talkshow) |
| `--max M` | 2 | Durasi maksimal per clip menit (default: 2 utk talkshow) |
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
3. Kirim ke DeepSeek direct (api.deepseek.com, model: deepseek-v4-flash) dengan system prompt
4. Params: jumlah_clip, durasi_min, durasi_max
5. Simpan log analisis (potong_log_alasan.md)
6. Ekstrak .BAT dari response AI (potong.bat)

### Tahap 3: Potong Audio (Parallel FFmpeg)
1. Parse .bat → daftar perintah ffmpeg
2. Ganti input → audio_full.mp3, output → 3_hasil_potong/
3. Eksekusi parallel via ThreadPoolExecutor (MAX_WORKERS = CPU count)

## Output Structure

```output/YYYY-MM-DD_judul/
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

## Post-Run: Copy ke Flat Output

User sering minta semua clip dipindah ke `output/` (flat) setelah pipeline selesai, tanpa subfolder per-video. Lakukan ini setelah tiap batch selesai:

```bash
# Copy semua clip dari folder batch tertentu ke output/
for dir in "D:/Insert Automation/Insert maker/automate insert/output/YYYY-MM-DD"*; do
  sub="$dir/3_hasil_potong"
  if [ -d "$sub" ]; then
    cp -n "$sub"/*.mp3 "D:/Insert Automation/Insert maker/automate insert/output/"
  fi
done
```

Atau via Python (saat terminal broken):
```python
import os, shutil, glob
base = r"D:\Insert Automation\Insert maker\automate insert\output"
for folder in os.listdir(base):
    hasil = os.path.join(base, folder, "3_hasil_potong")
    if os.path.isdir(hasil):
        for f in glob.glob(os.path.join(hasil, "*.mp3")):
            dest = os.path.join(base, os.path.basename(f))
            if not os.path.exists(dest):
                shutil.copy2(f, dest)
```

Jangan pindahkan/move — gunakan **copy** (`cp -n` / `shutil.copy2`) agar struktur folder per-video tetap utuh sebagai backup.

## ⚠️ Aturan Delivery
**JANGAN kirim file audio (.mp3) ke user.** Cukup laporkan hasil pipeline: jumlah clip, durasi, dan path output-nya. Audio hanya untuk disimpan lokal, bukan untuk dikirim ke Telegram.

## Script Path

Pipeline ada di salah satu path berikut (tergantung folder mana yang ada di sistem):

| Prioritas | Path | Keterangan |
|-----------|------|------------|
| #1 | `D:\\Insert Automation\\Insert maker\\automate insert-video\\pipeline.py` | Path utama (dengan `-video`) |
| #2 | `D:\\Insert Automation\\Insert maker\\automate insert\\pipeline.py` | Path lama (tanpa `-video`) |

Cek dengan `ls` atau `dir` untuk menentukan mana yang tersedia.

## Cara Run

Gunakan **background mode** (bukan foreground) karena terminal foreground sering gagal di Windows MSYS dengan error quote parsing:

```bash
cd "D:/Insert Automation/Insert maker/automate insert-video/1. apify + audio"
source venv/Scripts/activate
python ../pipeline.py <URL> [--clips N] [--min M] [--max M] [--skip-start M]
```

> **⚠️ MSYS Workaround:** Jika foreground command gagal dengan error `unexpected EOF while looking for matching '"'`, gunakan `terminal(background=true, notify_on_complete=true)` — shell baru untuk background process tidak mengalami masalah quote parsing yang menginfeksi foreground shell state.

Cukup kirim link — clip otomatis dihitung:
```bash
python ../pipeline.py "https://youtube.com/watch?v=..."
```

Audio-only (MP3):
```bash
python ../pipeline.py "https://youtube.com/watch?v=..." --audio
```

Kajian (4-6 menit, audio-only):
```bash
python ../pipeline.py "https://youtube.com/watch?v=..." --audio --min 4 --max 6
```

Override jumlah clip manual:
```bash
python ../pipeline.py "https://youtube.com/watch?v=..." --clips 10
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

- `references/trim-to-duration.md` — Langkah detail trim video ke N menit pertama
- `references/pipeline-modifications.md` — Riwayat modifikasi pipeline.py (model, rename, metadata, dll)
- `references/github-info.md` — Info repo GitHub untuk sharing
- `references/ustadz-detection-failures.md` — Kasus deteksi nama ustadz gagal + cara fix manual
- `references/yt-dlp-cookies-auth.md` — Troubleshooting YouTube 429 rate limit, cookies export, oEmbed fallback untuk judul
- `references/transcript-format.md` — Format JSON transcript Apify, YouTube JSON3, convert_subs.py utility
- `references/talkshow-video-variant.md` — Perubahan MP3 → MP4, AI prompt talkshow, cara revert ke MP3

## Pitfalls

- **yt-dlp progress tidak terlihat di log background process:** yt-dlp menampilkan progress download dengan `\r` (carriage return), bukan `\n` (newline). Akibatnya log background process di `process(action='log')` hanya menunjukkan baris yang sama — kelihatan stuck padahal download berjalan normal. **Jangan判断 stuck dari log saja.** Cara monitor yang akurat: jalankan `ls` terpisah (via background) untuk lihat ukuran file di `1_apify/` — kalau `audio_full.mp3` atau `audio_full.webm.part` membesar, download masih jalan.
- **Transcript seg_count sebagai sinyal durasi video:** Transcript dengan ribuan segmen (misal 3160) menandakan video LIVE panjang (~1-2 jam+). Ini berarti download audio via yt-dlp akan makan waktu beberapa menit. **Manage ekspektasi:** kabari user kalau video panjang, download audio perlu waktu. Jangan panik kalau output tidak berubah selama 2-5 menit.
- **Monitor progress pipeline via direktori:** Cara paling handal cek progres tanpa lihat log:
  - **Tahap 1** (Download): `ls 1_apify/` — cek ukuran `audio_full.mp3` atau `.part`
  - **Tahap 2** (AI Analysis): cek apakah `2_analisa/` sudah terbuat (ada `potong.bat`?)
  - **Tahap 3** (FFmpeg potong): cek apakah `3_hasil_potong/` sudah terbuat dan ada file `.mp3`
- **Windows MSYS terminal foreground gagal dengan error quote parsing:** Semua foreground command (`terminal()` tanpa `background=true`) gagal dengan `/bin/bash: -c: line 1: unexpected EOF while looking for matching '"'` — bahkan `echo test`. Penyebab: corrupted bash session state. **Fix:** Gunakan `terminal(background=true, notify_on_complete=true)` — background process mendapat shell baru dan tidak terinfeksi. ⚠️ **Catatan:** `pty=true` TIDAK selalu bisa reset corrupted session — foreground command pakai `pty=true` pun bisa tetap gagal dengan error yang sama. Hanya background mode yang reliable.

- **execute_code + subprocess.Popen sebagai alternatif ketika terminal corrupted total:** Jika `terminal()` (foreground & background) gagal dengan error shell yang sama (corrupted bash state), gunakan `execute_code` dengan `subprocess.Popen` langsung via Python stdlib:
  ```python
  import subprocess
  result = subprocess.run(cmd, cwd=workdir, capture_output=True, text=True, timeout=300, errors="replace")
  if result.stdout:
      print(result.stdout[-2000:])
  ```
  Atau untuk multi-video parallel:
  ```python
  proc = subprocess.Popen(cmd, cwd=workdir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
  out, err = proc.communicate(timeout=480)
  ```
  **Catatan:** `execute_code` punya limit 300s total — tapi `subprocess.run` + `timeout=480` dalam script beberapa video bisa lebih panjang asal total waktu script < 300s. Untuk video yang butuh >300s, jalankan per video dalam script terpisah.

- **yt-dlp .part file lock setelah download terputus:** Jika yt-dlp di-kill tengah download, file `.part` tetap ada dan terkunci. Pipeline retry gagal dengan `HTTP Error 416: Requested range not satisfiable` karena yt-dlp minta range byte dari .part yang corrupted. **Fix:** Hapus .part file dulu, baru retry:
  ```bash
  # Kill yt-dlp proses
  taskkill /F /IM yt-dlp.exe
  # Hapus file .part
  rm -f "path/to/audio_full.webm.part"
  ```
  Atau via Python:
  ```python
  import subprocess
  subprocess.run(["taskkill", "/F", "/IM", "yt-dlp.exe"])
  os.remove(part_file)
  ```

- **User prefer "Ustadz" bukan "Ust":** Setelah pipeline rename (yang ubah "Ust."/"Ust" → "Ustadz"), masih ada kasus deteksi yang menghasilkan "Ust" tanpa titik (contoh: "Ust Badru Salam, Lc"). User selalu ingin full "Ustadz". **Fix manual:** rename file + update metadata artist setelah pipeline selesai. Jangan kirim file dengan nama "Ust" ke user tanpa fix dulu.
- **Path absolut semua:** Script menggunakan path absolut (jangan pakai ../../).
- **yt-dlp butuh JS runtime:** Bisa warning soal deno/node — aman diabaikan, tidak mempengaruhi hasil.
- **YouTube 429 Too Many Requests (Rate Limited):** yt-dlp error `HTTP Error 429: Too Many Requests` berarti YouTube memblokir request tanpa cookies autentikasi. **Ini blocking error, bukan warning.** Pipeline berhenti di Tahap 1 (gagal ambil judul/download audio). Penyebab & solusi lengkap ada di `references/yt-dlp-cookies-auth.md`.
- **`--cookies-from-browser` gagal karena browser berjalan:** yt-dlp `--cookies-from-browser chrome` error `Could not copy Chrome cookie database` karena Chrome/Edge sedang berjalan dan database cookie terkunci. **Solusi:** Tutup semua window browser dulu, atau export cookies.txt manual via extension (Get cookies.txt), atau gunakan `--cookies-from-browser chrome --cookies-from-browser-args "new-env"`. Lihat `references/yt-dlp-cookies-auth.md` untuk detail.
- **YouTube Live stream ended — butuh cookies:** Video yang sudah selesai live streaming tetap butuh cookies untuk diakses via yt-dlp. Tanpa cookies, error `Sign in to confirm you're not a bot`. Bahkan `player_client=android` tidak cukup — butuh PO Token tambahan untuk SABR-only streams. **Solusi:** Sediakan cookies valid dari browser yang sudah login YouTube.
- **Ghost bin:** Hasil potong ada di `3_hasil_potong/` — jangan cari di folder lain.
- **.env:** Tahap 1 butuh APIFY_TOKEN, Tahap 2 butuh OPENCODE_GO_API_KEY.
- **Header x-opencode-session (WAJIB sejak 2026-09-05):** OpenCode Go 400 `MissingSessionID` kalau request tidak kirim header `x-opencode-session`. Tambahkan `"x-opencode-session": str(uuid.uuid4())` di headers (import `uuid`). Tanpa ini semua retry gagal; dengan header ini jalan.
- **ADA DUA SALINAN pipeline.py — WAJIB sync keduanya:** (A) `D:\Insert Automation\Insert maker\automate insert\pipeline.py` (dipakai `run_sequential.py`, path-nya hardcoded ke sini) dan (B) `D:\Insert Automation\Insert maker\automate insert-video\pipeline.py`. Setiap kali ubah konfigurasi (model, timeout, header), terapkan ke KEDUANYA — kalau cuma satu, run yang lewat jalur lain akan pakai setelan lama. Cek cepat: `grep -n "MODEL_ID\s*=\|x-opencode-session\|timeout=1200" <file>`.
- **Audio/video output:** Pipeline default download MP4 dan output MP4 clip. Untuk output MP3 (kajian), dibutuhkan modifikasi: ganti `download_video()` balik ke `yt-dlp -x`, tambah `-vn` di ffmpeg, ganti `.mp4` ke `.mp3` di output. Atau maintain pipeline.py terpisah untuk masing-masing mode. Lihat `references/talkshow-video-variant.md` untuk detail migrasi.
- **Character spesial di judul video:** Judul dengan `#`, `&`, atau karakter spesial lainnya bikin path folder output sulit diproses pas delivery file (timeout di Telegram API). **Workaround:** copy file ke `/tmp/` dulu sebelum deliver.
- **Trailing punctuation di judul video bikin mkdir gagal:** Judul seperti "... Zaen, Lc., M.A." bikin `sanitize()` motong pas di koma/spasi karena `[:100]`. **Fix:** `sanitize()` di `pipeline.py` pakai `.rstrip(" .-,()")` setelah `[:100]`.
- **Folder lama dari run gagal:** Kalau run pertama gagal (misal karena error path), folder output tetap terbuat dengan nama salah. Run ulang dengan `exist_ok=True` akan pakai folder lama dan gagal lagi. **Fix:** `rm -rf` folder output hasil run gagal sebelum run ulang.
- **Cache .pyc usang:** Setelah edit `pipeline.py`, hapus `__pycache__/pipeline.cpython-311.pyc` atau seluruh `__pycache__/` biar Python pake kode baru.
- **Sequential transcript -> audio:** Pipeline sekarang cek transcript dulu sebelum download audio. Kalau transcript kosong, pipeline berhenti cepat tanpa download audio (hemat bandwidth & waktu).
- **Fail fast:** kalau Apify gagal -> stop total, jangan lanjut.
- **yt-dlp kadang simpan audio sebagai .m4a bukan .mp3:** Meskipun `--audio-format mp3`, yt-dlp terkadang menyimpan sebagai `audio_full.m4a` (tergantung codec source + ketersediaan ffmpeg di PATH untuk konversi). Pipeline Tahap 3 parse `.bat` mengganti `-i` ke `audio_full.mp3` — kalau file asli `.m4a`, pipeline error. **Fix:** Cek ekstensi file di `1_apify/` sebelum jalankan Tahap 3, atau pastikan ffmpeg terinstall dan terdeteksi yt-dlp di PATH sistem.
- **Auto-cleanup audio_full.mp3/m4a:** Setelah Tahap 3 selesai, pipeline otomatis hapus `audio_full.mp3` (bisa 80-140MB) — clip sudah aman di `3_hasil_potong/`. Jangan kaget kalau file gak ada di folder 1_apify/ setelah pipeline selesai. Catatan: jika audio berupa `.m4a`, file tersebut juga akan dihapus di cleanup yang sama.
- **Re-download audio otomatis:** Kalau transcript di-cache tapi `audio_full.mp3` gak ada (misal kedel eats auto-cleanup dari run sebelumnya), pipeline akan download ulang audio aja tanpa re-fetch transcript.
- **AI salah konversi timestamp MM:SS -> HH:MM:SS:** Kadang AI generate `-ss 05:00:00` (5 jam) padahal maksudnya `00:05:00` (5 menit). **Fix:** Pipeline otomatis deteksi ini — kalo total detik timestamp > 2x durasi video, dikoreksi jadi `00:05:00`. Tapi lebih baik cegah dengan prompt yang jelas (lihat Prompt Rules di bawah).
- **Presisi timestamp:** AI WAJIB pakai timestamp presisi dari transcript (desimal, contoh: `00:05:05.500`), jangan dibulatkan ke menit bulet. Aturan ini sudah di prompt Aturan #7.
- **Karakter non-UTF8 di judul video:** Beberapa judul YouTube mengandung byte non-UTF8 yang bikin `subprocess.run` error. **Fix:** pipeline sudah pakai `errors="replace"` di subprocess call.
- **`--skip-start` hanya untuk kasus tertentu:** User tidak ingin `--skip-start` dipakai default. Hanya gunakan kalau user explicitly bilang kajian dimulai menit sekian.
- **YouTube Live / video tanpa caption:** Apify return `{"data": []}` -> pipeline gagal di "Transcript kosong". **STOP — jangan fallback ke faster-whisper atau transkripsi alternatif.** User tidak ingin transcripsi manual. Ikuti protokol diagnostik berikut:

  **Protokol "Transcript Kosong" (wajib):**
  1. **Konfirmasi** dengan `yt-dlp --list-subs <URL>` — output akan menampilkan salah satu/both:
     - `"has no automatic captions"`
     - `"has no subtitles"`
  2. **Laporkan ke user** dengan pesan standar:
     > 🎬 **Judul:** `{judul}`
     > ❌ **Pipeline dihentikan** — video tidak memiliki teks takarir (automatic captions/subtitles) sama sekali.
     > Pipeline membutuhkan transcript (dari takarir YouTube) untuk memproses video ini. Tidak ada alternatif transkripsi manual.
  3. **JANGAN download audio** untuk transkripsi alternatif
  4. **JANGAN coba fallback** via convert_subs.py / faster-whisper / API STT eksternal
  5. **Simpan URL** untuk dicoba lagi nanti (auto-captions kadang muncul beberapa jam setelah upload, terutama untuk video LIVE) — bisa dijadwalkan via cron job retry

  **Contoh output diagnostik:**
  ```bash
  # yt-dlp --list-subs <URL>
  # Output:
  #   jdjMoa84Zs0 has no automatic captions
  #   jdjMoa84Zs0 has no subtitles
  ```

- **Auto clip count:** Pipeline hitung otomatis dari durasi audio: `max(3, min(12, round((durasi_detik-600)/600)))`. Skip 5 menit awal + 5 menit akhir. Override manual dengan `--clips N`.
- **AI bisa kurangi jumlah clip:** AI (OpenCode Go deepseek-v4.1-flash) bisa menghasilkan clip lebih sedikit dari `--clips N` kalau tidak ada cukup segmen bagus untuk durasi yang diminta. **Ini normal dan diinginkan** — kualitas konten lebih penting dari jumlah clip. Jangan paksa AI generate clip kualitas rendah.
- **Durasi clip ditampilkan:** Setiap clip hasil potong menampilkan durasi (MM:SS), ukuran (KB), dan waktu proses (detik) — ambil dari arg `-t` di ffmpeg.
- **Beban CPU bukan token:** Pipeline ini lebih berat ke CPU laptop (FFmpeg paralel di Tahap 3) daripada konsumsi token AI. Token cuma dipakai di Tahap 2 (~20K/run). Sisanya murni lokal.
- **Apostrophe dalam nama ustadz:** Nama seperti "Rofi'i" atau "Atho'illah" putuskan regex prefix `[A-Za-z\s.]+`. **Fix:** Regex tambah `'` dan `’` ke character class: `[A-Za-z\s.'’]+`.
- **Hyphen biasa di judul:** Fallback deteksi ustadz cuma cari `|`, `–`, `—`. Kalau judul pakai hypen biasa `-` sebagai separator (contoh: "Ustadz X - Judul"), ustadz di awal gak kedeteksi karena separator `-` bukan `|`/`–`/`—`. **Fix:** Pastikan prefix regex handle nama dengan prefix "Ustadz" di awal judul.
- **Gelar akademik di nama:** Semua gelar setelah koma (Lc., M.A., M.Sc., S.Pd.I., dll) harus dipotong. **Fix:** `re.sub(r',\\s*.*$', '', raw_name)` — potong semua setelah koma, bukan daftar gelar satu-satu.
- **Nama dengan inisial "H." (Haji) potong huruf pertama nama yang mulai huruf H:** Regex hapus gelar di depan (`Dr., H., Hj., Prof., dll`) terlalu greedy — `H.` juga match huruf `H` pertama dari nama seperti "Hudzaifah". Contoh: "Ustadz Dr. Hudzaifah M. Maricar" → setelah Dr. dihapus, `H.` regex potong `H` dari "Hudzaifah" → "udzaifah M. Maricar". **Fix:** Pastikan regex gelar hanya match `H.` (dengan titik) sebagai kata utuh, bukan `H` sebagai huruf pertama dari token berikutnya. Di pipeline.py, gunakan negative lookahead atau batasi ke token yg memang singkatan (`\bH\.\b` bukan `H\.?`).
- **Jangan ubah `hasil_dir` ke folder bersama (flat output):** Pipeline rename section (`main()`) memproses SEMUA file `.mp3` di `hasil_dir`, bukan cuma file baru. Kalau `hasil_dir` diubah ke `BASE_DIR / "output"` (flat), rename akan merusak nama file clip dari run sebelumnya. **Fix:** `hasil_dir` HARUS `output_dir / "3_hasil_potong"` (per-video folder), jangan flat.
- **Deteksi ustadz bisa gagal:** Kalau judul video tidak pakai prefix "Ustadz"/"Ust."/dll, pipeline fallback ambil segmen terakhir setelah separator. Akibatnya nama ustadz bisa salah (contoh: "Maell Lee" terdeteksi padahal isinya Ustadz Khalid Basalamah). **Varian tambahan:** Judul yang dimulai dengan "Ustadz" tapi diikuti kata kerja/kalimat tanya (bukan nama orang), misal "Ustadz dibayar Ngisi Kajian, Dosa atau Boleh" → prefix match tetap fires, pipeline potong setelah "Ustadz " dan hasilkan nama palsu "Ustadz dibayar Ngisi Kajian". **Fix:** Manual rename & update metadata setelah pipeline selesai. Lihat references/ustadz-detection-failures.md Kasus 6.
- **Sub-agent bisa lapor sukses padahal file gak beneran tersimpan:** Sub-agent summary adalah self-report — bisa melaporkan sukses padahal file mp3 tidak ada di disk (berlaku untuk direct run juga). **Verifikasi:** Selalu `ls` folder output setelah pipeline selesai untuk memastikan file .mp3 beneran ada di `3_hasil_potong/`.
- **Hapus parameter `&pp=` dari URL YouTube:** Parameter `&pp=...` adalah search context, bukan bagian dari video ID. Pipeline bisa gagal atau berperilaku aneh. **Fix:** strip `&pp` dan parameter tracking lainnya dari URL sebelum kirim ke pipeline.
- **AI override `--clips N`:** AI (OpenCode Go deepseek-v4.1-flash) kadang menghasilkan clip lebih banyak dari `--clips N` yang diminta karena nemu topik bagus tambahan, atau lebih sedikit karena tidak ada cukup segmen berkualitas. Pipeline tetap proses apa yang AI hasilkan — tidak ada filter ketat. Kalau mau strict, naikkan `temperature=0` di payload API.
- **YouTube Live tanpa captions:** yt-dlp `--list-subs` berguna untuk cek cepat apakah video punya caption sebelum jalankan pipeline penuh. `yt-dlp --list-subs <URL>` akan bilang "has no automatic captions" / "has no subtitles" kalau kosong.
- **Cron job retry untuk video gagal:** Video yang gagal karena transcript kosong (YouTube Live) bisa dijadwalkan ulang via cron job untuk besok/hari berikutnya — kadang caption auto-generated baru muncul beberapa jam setelah upload. Buat cronjob 1x dengan action='create', schedule='YYYY-MM-DDT08:00:00' (besok pagi).
- **OpenCode Go API timeout di Tahap 2:** Kadang API call ke OpenCode Go bisa timeout (HTTP 404/400). Model aktif: `deepseek-v4.1-flash` (opsi lain di OpenCode Go: `mimo-v2.5`, `longcat-2.0`, `kimi-k2.6`, `glm-5.3` — cek `GET /zen/go/v1/models`). Pipeline stuck di "Mengirim ke OpenCode Go..." tanpa error. **Fix:** Kill proses dan restart. Retry biasanya berhasil di percobaan kedua (response datang dalam 1-2 menit). Ini transient API issue, tidak perlu ubah kode. **Penting:** URL harus lengkap dengan `/chat/completions` di akhir.
- **Total runtime per durasi video:** Pipeline selesai dalam skala menit tergantung panjang video dan transcript. Data dari real runs:
  - **Video 40-50 min (~1000 segmen, 57K chars):** ~5 menit total — transcript fetch (10s), audio download (2-3 min), AI analysis (1-2 min), FFmpeg potong (20s). Contoh: 46 min video menghasilkan 3 clip (4-6 min) dalam 5 menit 20 detik.
  - **Video LIVE 90-180 min (100K-200K chars):** Total 5-15 menit — transcript fetch (10-30s), audio download (1-5 min untuk 132 min video), AI analysis (1-5 min + kemungkinan retry jika hang), FFmpeg potong (30s-2 min).
  - Saat dijalankan via Hermes agent, pipeline dapat terpotong oleh tool-call iteration limit sebelum selesai. **Mitigasi:** Gunakan background mode dengan notify_on_complete=true. Jika tool-call limit tercapai sebelum pipeline selesai, proses tetap berjalan di background — poll/log di turn berikutnya. Jangan delete output folder di tengah jalan kalau cache masih berguna untuk retry nanti.
## Prompt Rules (WAJIB dipatuhi AI)

Aturan ini sudah tertanam di `pipeline.py` system prompt. Jika ada modifikasi prompt, edit langsung di file pipeline.py, lalu update referensi di sini.

### Mode KAJIAN (default lama, MP3, --min 4 --max 6)

- **Aturan K1:** CARI TRANSISI TOPIK DULU. Clip boundary = batas antar topik, bukan batas waktu.
- **Aturan K2:** DURASI WAJIB antara min-max menit. JANGAN PERNAH melebihi max. Jika topik panjang, potong bagian terbaik saja.
- **Aturan K3:** HINDARI clip di bawah 3 menit — gabungkan atau skip.
- **Aturan K4:** JANGAN potong per menit bulet. Boundary di akhir kalimat/paragraf transcript.
- **Aturan K5:** "Target ~N clip, jangan maksain" — prioritas selesainya satu pembahasan utuh.
- **Aturan K6:** HINDARI bagian OPENING. Jangan pilih clip yang mengandung salam pembuka, basmalah, hamdalah, atau perkenalan pembicara.
- **Aturan K7:** HINDARI bagian ADZAN. Jika transcript mengandung lafadz adzan atau jeda adzan, jangan pilih segmen itu.
- **Aturan K8:** HINDARI bagian CLOSING. Jangan pilih clip yang mencakup doa penutup, wassalam, pengumuman kajian berikutnya, atau Q&A akhir.
- **Aturan K9:** Clip harus dari topik berbeda, jangan berurutan, sebar di seluruh video.
- **Aturan K10:** NO OVERLAP. Clip WAJIB diurutkan berdasarkan waktu. Start berikutnya > end sebelumnya.

### Mode TALKSHOW RADIO (default baru, MP4, --min 1 --max 2)

- **Aturan T1:** **WAJIB hindari BREAK IKLAN** — segmen di mana host bilang "kita akan break", "setelah break", "kembali setelah ini", musik jeda iklan, dll.
- **Aturan T2:** **WAJIB hindari IKLAN RADIO** — segmen promosi produk/sponsor, call to action iklan, tagline sponsor.
- **Aturan T3:** **WAJIB hindari OPENING** — salam pembuka, perkenalan host/narasumber, jingle pembuka.
- **Aturan T4:** **WAJIB hindari CLOSING** — salam penutup, pengumuman acara mendatang, kredit penutup.
- **Aturan T5:** DURASI WAJIB antara min-max menit. JANGAN PERNAH melebihi max. Clip <45 detik juga tidak boleh.
- **Aturan T6:** SEBAR di seluruh durasi — jangan ambil semua clip dari 10 menit pertama saja.
- **Aturan T7:** Pilih segmen paling engaging: debat menarik, curhat inspiratif, opini kontroversial, data/fakta mengejutkan, humor cerdas, cerita personal yang kuat.
- **Aturan T8:** Clip = satu sesi tanya-jawab atau satu topik mini. No overlap, urut berdasarkan waktu.

> **Perubahan penting di v1.1.0:** Aturan #6-#8 lama = hindari opening/adzan/closing. Sebelumnya aturan #6 hard-code skip 5 menit pertama. Sekarang AI deteksi dari teks transcript, lebih akurat.

> **Perubahan penting di v1.13.0:** Default berubah ke mode Talkshow Radio (MP4, 1-2 min). Mode Kajian (MP3, 4-6 min) tersedia via parameter eksplisit `--min 4 --max 6`. Lihat `references/talkshow-video-variant.md` untuk detail perubahan pipeline.