---
name: insert-radio
description: "Pipeline otomatis YouTube -> transcript -> analisis AI -> potong clip MP3 untuk insert radio. 3 tahap: cek transcript, analisis via OpenRouter, potong FFmpeg parallel. Fitur: auto hitung clip dari durasi video (÷10), max 6 menit per clip, durasi tiap clip ditampilkan."
version: 1.2.0
# CHANGES:
# 1.1.0 - Added AI prompt rules to avoid OPENING, ADZAN, and CLOSING segments
#       - Updated Prompt Rules section to match actual pipeline.py (10 rules)
#       - Added pitfall: AI may override requested clip count
#       - Added pitfall: YouTube Live detection via yt-dlp --list-subs
---

# Insert Radio

Pipeline 3 tahap dari link YouTube sampai clip MP3 siap pakai sebagai insert radio/kajian.

## Trigger

User kirim link YouTube. **Cukup URL aja** — pipeline otomatis:
1. Cek ketersediaan transcript
2. Hitung jumlah clip dari durasi video (÷10, skip 5 awal + 5 akhir)
3. Proses sampai clip MP3 jadi

Override opsional: `--clips N`, `--min M`, `--max M`, `--skip-start M`

## Default

Kalau user kirim link YouTube **tanpa deskripsi parameter**, default:
- **Clip:** 5
- **Durasi:** 4-6 menit

## Execution via Sub-Agent

Semua proses insert-radio WAJIB dijalankan via **delegate_task** (sub-agen), bukan langsung.

- Max **3 sub-agen paralel** (sesuai batas concurrent user)
- Kirim beritahu dulu ke user: "Mulai proses X video..."
- Setelah semua selesai, kumpulkan hasil dan laporkan ke user
- Masing-masing sub-agen jalankan terminal command pipeline.py untuk 1 video

## Tooling

- **Apify API** -> ambil transcript YouTube
- **yt-dlp** -> download audio MP3
- **OpenRouter** (deepseek/deepseek-v4-flash) -> analisis transcript -> generate perintah potong
- **FFmpeg** -> potong clip

## Parameters

| Arg | Default | Deskripsi |
|-----|---------|-----------|
| `URL` | (required) | Link YouTube |
| `--clips N` | 0 (auto) | Jumlah clip (0=otomatis dari durasi video) |
| `--min M` | 4 | Durasi minimal per clip (menit) |
| `--max M` | 6 | Durasi maksimal per clip (menit) |
| `--skip-start N` | 0 | Skip N menit awal video (berguna kalau intro panjang/sebelum kajian dimulai) |

## Step-by-step

### Tahap 1: Cek Transcript → Audio → Hitung Clip
1. Cek cache transcript.json — kalau ada dan valid, skip Apify (optimasi C)
2. Jika tidak ada cache: fetch transcript via Apify API dulu
3. Validasi seg_count > 0 — **kalau 0, hentikan pipeline sekarang juga. JANGAN fallback ke faster-whisper.** Cukup lapor kegagalan ke user.
4. Jika transcript valid, download audio MP3 via yt-dlp
5. Hitung otomatis jumlah clip dari durasi audio (efektif -10 menit, ÷10 konservatif)

### Tahap 2: Analisis AI
1. Baca transcript.json, extract ke format `[start - dur:dur] text`
2. Jika `--skip-start` > 0, filter out semua segmen sebelum `skip_start * 60` detik (log: "⏭️ N segmen awal di-skip")
3. Kirim ke OpenRouter (model: deepseek/deepseek-v4-flash) dengan system prompt
4. Params: jumlah_clip, durasi_min, durasi_max
5. Simpan log analisis (potong_log_alasan.md)
6. Ekstrak .BAT dari response AI (potong.bat)

### Tahap 3: Potong Audio (Parallel FFmpeg)
1. Parse .bat → daftar perintah ffmpeg
2. Ganti input → audio_full.mp3, output → 3_hasil_potong/
3. Eksekusi parallel via ThreadPoolExecutor (MAX_WORKERS = CPU count)

## Output Structure
```
output/YYYY-MM-DD_judul/
├── 1_apify/
│   ├── transcript.json
│   └── audio_full.mp3
├── 2_analisa/
│   ├── potong.bat
│   └── potong_log_alasan.md
└── 3_hasil_potong/
    ├── Metode Menghafal Al Quran - Khalid Basalamah.mp3
    └── ...
```

## Post-Processing (Rename & Metadata)

Setelah clip terpotong, pipeline otomatis:
1. **Deteksi nama ustadz** dari judul video:
   - Cari prefix: `Ustadz`, `Ustad`, `Ust.`/`Ust`, `KH.`, `Kyai`, `Syekh`/`Syaikh` (support apostrophe: `Rofi'i`, `Atho'illah`)
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
   - **Album** → judul video **tanpa nama ustadz** (dibersihkan otomatis: "Ustadz X - Judul" → "Judul", atau "Judul | Ustadz X" → "Judul")
   - **Date** → tahun berjalan (2026, dst)
```

## ⚠️ Aturan Delivery
**JANGAN kirim file audio (.mp3) ke user.** Cukup laporkan hasil pipeline: jumlah clip, durasi, dan path output-nya. Audio hanya untuk disimpan lokal, bukan untuk dikirim ke Telegram.

## Script Path
`D:\Insert Automation\Insert maker\automate insert\pipeline.py`

## Cara Run
```bash
cd "D:/Insert Automation/Insert maker/automate insert/1. apify + audio"
source venv/Scripts/activate
python ../pipeline.py <URL> [--clips N] [--min M] [--max M] [--skip-start M]
```

Cukup kirim link — clip otomatis dihitung:
```bash
python ../pipeline.py "https://youtube.com/watch?v=..."
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

## Referensi Internal

- `references/trim-to-duration.md` — Langkah detail trim video ke N menit pertama
- `references/pipeline-modifications.md` — Riwayat modifikasi pipeline.py (model, rename, metadata, dll)

## Pitfalls

- **Path absolut semua:** Script menggunakan path absolut (jangan pakai ../../).
- **yt-dlp butuh JS runtime:** Bisa warning soal deno/node — aman diabaikan, tidak mempengaruhi hasil.
- **Ghost bin:** Hasil potong ada di `3_hasil_potong/` — jangan cari di folder lain.
- **.env:** Tahap 1 butuh APIFY_TOKEN, Tahap 2 butuh OPENROUTER_API_KEY.
- **Audio only:** Pipeline download MP3, bukan video.
- **Karakter spesial di judul video:** Judul dengan `#`, `&`, atau karakter spesial lainnya bikin path folder output sulit diproses pas delivery file (timeout di Telegram API). **Workaround:** copy file ke `/tmp/` dulu sebelum deliver.
- **Trailing punctuation di judul video bikin mkdir gagal:** Judul seperti "... Zaen, Lc., M.A." bikin `sanitize()` motong pas di koma/spasi karena `[:100]`. **Fix:** `sanitize()` di `pipeline.py` pakai `.rstrip(" .-,()")` setelah `[:100]`.
- **Folder lama dari run gagal:** Kalau run pertama gagal (misal karena error path), folder output tetap terbuat dengan nama salah. Run ulang dengan `exist_ok=True` akan pakai folder lama dan gagal lagi. **Fix:** `rm -rf` folder output hasil run gagal sebelum run ulang.
- **Cache .pyc usang:** Setelah edit `pipeline.py`, hapus `__pycache__/pipeline.cpython-311.pyc` atau seluruh `__pycache__/` biar Python pake kode baru.
- **Sequential transcript -> audio:** Pipeline sekarang cek transcript dulu sebelum download audio. Kalau transcript kosong, pipeline berhenti cepat tanpa download audio (hemat bandwidth & waktu).
- **Fail fast:** kalau Apify gagal -> stop total, jangan lanjut.
- **Auto-cleanup audio_full.mp3:** Setelah Tahap 3 selesai, pipeline otomatis hapus `audio_full.mp3` (bisa 80-140MB) — clip sudah aman di `3_hasil_potong/`. Jangan kaget kalau file gak ada di folder 1_apify/ setelah pipeline selesai.
- **Re-download audio otomatis:** Kalau transcript di-cache tapi `audio_full.mp3` gak ada (misal kedel eats auto-cleanup dari run sebelumnya), pipeline akan download ulang audio aja tanpa re-fetch transcript.
- **AI salah konversi timestamp MM:SS -> HH:MM:SS:** Kadang AI generate `-ss 05:00:00` (5 jam) padahal maksudnya `00:05:00` (5 menit). **Fix:** Pipeline otomatis deteksi ini — kalo total detik timestamp > 2x durasi video, dikoreksi jadi `00:05:00`. Tapi lebih baik cegah dengan prompt yang jelas (lihat Prompt Rules di bawah).
- **Presisi timestamp:** AI WAJIB pakai timestamp presisi dari transcript (desimal, contoh: `00:05:05.500`), jangan dibulatkan ke menit bulet. Aturan ini sudah di prompt Aturan #7.
- **Karakter non-UTF8 di judul video:** Beberapa judul YouTube mengandung byte non-UTF8 yang bikin `subprocess.run` error. **Fix:** pipeline sudah pakai `errors="replace"` di subprocess call.
- **`--skip-start` hanya untuk kasus tertentu:** User tidak ingin `--skip-start` dipakai default. Hanya gunakan kalau user explicitly bilang kajian dimulai menit sekian.
- **YouTube Live / video tanpa caption:** Apify return `{"data": []}` -> pipeline gagal di "Transcript kosong". **STOP — jangan fallback ke faster-whisper.** User tidak ingin transcripsi manual. Cukup lapor ke user: "Video tidak memiliki caption, pipeline dihentikan."
- **Auto clip count:** Pipeline hitung otomatis dari durasi audio: `max(3, min(12, round((durasi_detik-600)/600)))`. Skip 5 menit awal + 5 menit akhir. Override manual dengan `--clips N`.
- **Durasi clip ditampilkan:** Setiap clip hasil potong menampilkan durasi (MM:SS), ukuran (KB), dan waktu proses (detik) — ambil dari arg `-t` di ffmpeg.
- **Beban CPU bukan token:** Pipeline ini lebih berat ke CPU laptop (FFmpeg paralel di Tahap 3) daripada konsumsi token AI. Token cuma dipakai di Tahap 2 (~20K/run). Sisanya murni lokal.
- **Apostrophe dalam nama ustadz:** Nama seperti "Rofi'i" atau "Atho'illah" putuskan regex prefix `[A-Za-z\s.]+`. **Fix:** Regex tambah `'` dan `’` ke character class: `[A-Za-z\s.'’]+`.
- **Hyphen biasa di judul:** Fallback deteksi ustadz cuma cari `|`, `–`, `—`. Kalau judul pakai hypen biasa `-` sebagai separator (contoh: "Ustadz X - Judul"), ustadz di awal gak kedeteksi karena separator `-` bukan `|`/`–`/`—`. **Fix:** Pastikan prefix regex handle nama dengan prefix "Ustadz" di awal judul.
- **Gelar akademik di nama:** Semua gelar setelah koma (Lc., M.A., M.Sc., S.Pd.I., dll) harus dipotong. **Fix:** `re.sub(r',\s*.*$', '', raw_name)` — potong semua setelah koma, bukan daftar gelar satu-satu.
- **Selalu cek pipeline.py langsung:** User sering edit pipeline.py langsung. Jangan pernah lapor model/config dari isi skill — selalu `read_file` atau `grep` pipeline.py dulu.
- **AI override `--clips N`:** AI (DeepSeek V4 Flash) kadang menghasilkan clip lebih banyak dari `--clips N` yang diminta karena nemu topik bagus tambahan. Pipeline tetap proses apa yang AI hasilkan — tidak ada filter ketat. Kalau mau strict, naikkan `temperature=0` di payload OpenRouter.
- **YouTube Live tanpa captions:** yt-dlp `--list-subs` berguna untuk cek cepat apakah video punya caption sebelum jalankan pipeline penuh. `yt-dlp --list-subs <URL>` akan bilang "has no automatic captions" / "has no subtitles" kalau kosong.
- **Cron job retry untuk video gagal:** Video yang gagal karena transcript kosong (YouTube Live) bisa dijadwalkan ulang via cron job untuk besok/hari berikutnya — kadang caption auto-generated baru muncul beberapa jam setelah upload. Buat cronjob 1x dengan action='create', schedule='YYYY-MM-DDT08:00:00' (besok pagi).

## Prompt Rules (WAJIB dipatuhi AI)
Aturan ini sudah tertanam di `pipeline.py` system prompt. Jika ada modifikasi prompt, edit langsung di file pipeline.py, lalu update referensi di sini.

- **Aturan #1:** CARI TRANSISI TOPIK DULU. Clip boundary = batas antar topik, bukan batas waktu.
- **Aturan #2:** DURASI WAJIB antara min-max menit. JANGAN PERNAH melebihi max. Jika topik panjang, potong bagian terbaik saja.
- **Aturan #3:** HINDARI clip di bawah 3 menit — gabungkan atau skip.
- **Aturan #4:** JANGAN potong per menit bulet. Boundary di akhir kalimat/paragraf transcript.
- **Aturan #5:** "Target ~N clip, jangan maksain" — prioritas selesainya satu pembahasan utuh.
- **Aturan #6:** HINDARI bagian OPENING. Jangan pilih clip yang mengandung salam pembuka, basmalah, hamdalah, atau perkenalan pembicara.
- **Aturan #7:** HINDARI bagian ADZAN. Jika transcript mengandung lafadz adzan atau jeda adzan, jangan pilih segmen itu.
- **Aturan #8:** HINDARI bagian CLOSING. Jangan pilih clip yang mencakup doa penutup, wassalam, pengumuman kajian berikutnya, atau Q&A akhir.
- **Aturan #9:** Clip harus dari topik berbeda, jangan berurutan, sebar di seluruh video.
- **Aturan #10:** NO OVERLAP. Clip WAJIB diurutkan berdasarkan waktu. Start berikutnya > end sebelumnya.

> **Perubahan penting di v1.1.0:** Aturan #6-#8 baru = hindari opening/adzan/closing. Sebelumnya aturan #6 hard-code skip 5 menit pertama. Sekarang AI deteksi dari teks transcript, lebih akurat.