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
- **Video DUO (2 pembicara di judul) — BELUM ada konvensi, tanya user dulu:** Deteksi nama hanya mengambil **nama pertama** (regex berhenti di separator `|`/`&`). Contoh: judul `... | Ustadz Dr. Sufyan Baswedan, M.A. & Ustadz Ammi Nur Baits` → artist jadi `Ustadz Sufyan Baswedan` saja, padahal dua-duanya bicara. Jangan nebak — tanya user mau: (a) dua nama digabung `Ustadz X & Ustadz Y`, (b) satu nama pertama, (c) nama program, atau (d) per-clip sesuai dominasi pembicara. Clip tetap diproses & dilaporkan; koreksi nama dilakukan setelah user putuskan.
- **Gelar akademik di nama ustadz (`bersihkan_gelar()`, di-port dari main 2026-09-19):** `bersihkan_gelar()` di `pipeline.py` menghapus gelar depan & belakang (Dr, Drs, Dra, Lc, MA, M.Ag, M.Sc, M.Pd, M.Si, MM, MBA, Ph.D, Prof, KH, Hj, S.Pd, S.T, S.Kom, BA, ST, SE, SH, dll). Contoh: `Ustadz Dr Syafiq Riza Basalamah MA` → `Ustadz Syafiq Riza Basalamah`. **Pitfall penting:** pola gelar WAJIB dipisah spasi/koma dari nama — tanpa pemisah, "KH" salah makan "Kh" dari "Khalid" (hasilnya jadi "alid Basalamah"). Fungsi ini sudah memakai guard pemisah. Uji cepat sebelum menyalahkan deteksi: `python3 -c "import importlib.util as u; s=u.spec_from_file_location('m','pipeline.py'); m=u.module_from_spec(s); s.loader.exec_module(m); print(m.bersihkan_gelar('Ustadz X MA'))"`.
- **Path absolut semua:** Script menggunakan path absolut (jangan pakai ../../).
- **yt-dlp butuh JS runtime:** Bisa warning soal deno/node — aman diabaikan, tidak mempengaruhi hasil.
- **YouTube 429 Too Many Requests (Rate Limited):** yt-dlp error `HTTP Error 429: Too Many Requests` berarti YouTube memblokir request tanpa cookies autentikasi. **Ini blocking error, bukan warning.** Pipeline berhenti di Tahap 1 (gagal ambil judul/download audio). Penyebab & solusi lengkap ada di `references/yt-dlp-cookies-auth.md`.
- **`--cookies-from-browser` gagal karena browser berjalan:** yt-dlp `--cookies-from-browser chrome` error `Could not copy Chrome cookie database` karena Chrome/Edge sedang berjalan dan database cookie terkunci. **Solusi:** Tutup semua window browser dulu, atau export cookies.txt manual via extension (Get cookies.txt), atau gunakan `--cookies-from-browser chrome --cookies-from-browser-args "new-env"`. Lihat `references/yt-dlp-cookies-auth.md` untuk detail.
- **YouTube Live stream ended — butuh cookies:** Video yang sudah selesai live streaming tetap butuh cookies untuk diakses via yt-dlp. Tanpa cookies, error `Sign in to confirm you're not a bot`. Bahkan `player_client=android` tidak cukup — butuh PO Token tambahan untuk SABR-only streams. **Solusi:** Sediakan cookies valid dari browser yang sudah login YouTube.
- **Ghost bin:** Hasil potong ada di `3_hasil_potong/` — jangan cari di folder lain.
- **.env:** Tahap 1 butuh APIFY_TOKEN, Tahap 2 butuh OPENCODE_GO_API_KEY.
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
- **AI bisa kurangi jumlah clip:** AI (OpenCode Go mimo-v2.5) bisa menghasilkan clip lebih sedikit dari `--clips N` kalau tidak ada cukup segmen bagus untuk durasi yang diminta. **Ini normal dan diinginkan** — kualitas konten lebih penting dari jumlah clip. Jangan paksa AI generate clip kualitas rendah.
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
- **AI override `--clips N`:** AI (OpenCode Go mimo-v2.5) kadang menghasilkan clip lebih banyak dari `--clips N` yang diminta karena nemu topik bagus tambahan, atau lebih sedikit karena tidak ada cukup segmen berkualitas. Pipeline tetap proses apa yang AI hasilkan — tidak ada filter ketat. Kalau mau strict, naikkan `temperature=0` di payload API.
- **YouTube Live tanpa captions:** yt-dlp `--list-subs` berguna untuk cek cepat apakah video punya caption sebelum jalankan pipeline penuh. `yt-dlp --list-subs <URL>` akan bilang "has no automatic captions" / "has no subtitles" kalau kosong.
- **Cron job retry untuk video gagal:** Video yang gagal karena transcript kosong (YouTube Live) bisa dijadwalkan ulang via cron job untuk besok/hari berikutnya — kadang caption auto-generated baru muncul beberapa jam setelah upload. Buat cronjob 1x dengan action='create', schedule='YYYY-MM-DDT08:00:00' (besok pagi).
- **Transcript auto-translate (Inggris) — FIXED v1.20.0:** Apify actor `pintostudio~youtube-transcript-scraper` mendukung field `targetLanguage`. Tanpa field itu, actor mengembalikan caption **auto-translate** (sering Inggris) meski video aslinya Indonesia — akibatnya AI salah menilai topik dan durasi clip ngawur (contoh nyata: video Rofi'i 60 mnt → 4 clip 0:50/1:24/2:10/8:20, ada segmen "penutup" di 43:30). **Fix:** kirim `targetLanguage: "id"` (default; override via env `APIFY_LANG`). Kalau ganti bahasa, hapus `1_apify/transcript.json` dulu agar tidak pakai cache lama.
- **Guard durasi clip — FIXED v1.20.0:** AI kadang menghasilkan clip di luar rentang `--min/--max` meski prompt melarang. **Fix:** Tahap 2 menghitung durasi tiap `-t` di `.bat`; kalau ada yang di luar rentang, kirim pesan koreksi ke AI (1x). Setelah itu Tahap 3 **skip deterministik** clip yang masih di luar rentang dan hanya memotong yang valid. Konsekuensi: jumlah clip bisa lebih sedikit dari `--clips`.
- **Guard OVERLAP clip — FIXED v1.22.0:** AI kadang menghasilkan clip yang saling tumpang tindih (start clip berikut < end clip sebelumnya) → konten terduplikasi/terpotong. **Fix:** Tahap 2 deteksi overlap (pasangan `-ss`+`-t`) & minta AI perbaiki 1x; Tahap 3 urutkan per waktu lalu **buang** clip yang overlap (pertahankan yang lebih awal). **Catatan:** AI cenderung mengunci durasi ke 300s (5:00) walau rentangnya 4-6 mnt; kalau ingin clip mengikuti topik utuh, longgarkan `--max` (mis. 8-10 mnt).
- **Provider AI bisa diganti (`AI_PROVIDER`):** pilihan `opencode` atau `openrouter`. **AKTIF: `opencode` + model `deepseek-v4.1-flash`** (OpenCode Go; saldo pulih 2026-09-19). Kenapa pernah pindah ke OpenRouter: saldo OpenCode Go habis (HTTP 401 `CreditsError`). Ganti cukup lewat `.env`:
  - Aktif (OpenCode): `AI_PROVIDER=opencode`, `OPENCODE_GO_MODEL=deepseek-v4.1-flash`, `OPENCODE_GO_REASONING=none`, kunci `OPENCODE_GO_API_KEY` (base `https://opencode.ai/zen/go/v1`, header `x-opencode-session` wajib).
  - Alternatif (OpenRouter): `AI_PROVIDER=openrouter`, `OPENROUTER_MODEL=deepseek/deepseek-v4.1-flash`, `OPENROUTER_REASONING=none`, kunci `OPENROUTER_API_KEY` (dari `~/.openclaw/openclaw.json`).
  - Model apa pun **wajib** `reasoning_effort=none`, kalau tidak Tahap 2 bisa 89-660s/timeout.
- **OpenCode Go `CreditsError` (HTTP 401, saldo habis):** Kalau API balas `401` dengan `"type":"CreditsError","message":"Insufficient balance"`, artinya saldo OpenCode Go habis — bukan bug pipeline. Pipeline berhenti di Tahap 2 setelah 2 percobaan retry. **Tindakan:** laporkan ke user untuk top-up billing OpenCode Go; JANGAN retry berulang (tiap retry gagal tanpa hasil). Transcript + audio Tahap 1 tetap tersimpan di `1_apify/` — **simpan folder itu** supaya retry setelah top-up langsung ke Tahap 2 (tanpa biaya Apify & download ulang).
- **OpenCode Go API timeout / lambat di Tahap 2 (FIXED v1.19.0):** Model `mimo-v2.5` punya *reasoning* internal yang bikin Tahap 2 lambat/gantung — terukur 660s+ (dan pernah timeout 900s) untuk transcript 95K char. **Fix:** kirim `"reasoning_effort": "none"` di payload → Tahap 2 turun ke ~26-29s (~23x lebih cepat). Sudah dipatch di pipeline.py; bisa dioverride via env `OPENCODE_GO_REASONING`. Timeout juga diturunkan 900s → 300s dengan retry otomatis 2x. **Penting:** URL harus berakhir `/chat/completions`, dan header `x-opencode-session` WAJIB ada (tanpa itu HTTP 400 `MissingSessionID`).
- **Honorifik "Ustad" (tanpa z) tidak dikenali regex — FIXED v1.32.1:** Judul bisa menulis **"Ustad Dr. dr. Arief Alamsyah"**. Regex lama hanya cocokkan `^Ustadz` / `^Ust\.`, sehingga `Ustad` lolos dan gelar di belakangnya **tidak ikut dibersihkan** (artist jadi `Ustad Dr. dr. Arief Alamsyah`). **Fix:** normalisasi `^Ust(?:adz|ad|az)?\.?\s+` → `Ustadz ` sebelum pembersihan gelar. **Catatan:** varian "Ustad", "Ustadz", "Ustaz", "Ust." semuanya harus ditangani.
- **Kata penyambung menggantung di tag album — FIXED v1.32.1:** Setelah nama ustadz dipotong, kata seperti **"bersama"/"oleh"/"dari"/"dan"** bisa tertinggal di akhir tag album (mis. `Berdamai dengan Ketidaksempurnaan bersama`). **Fix:** buang penyambung di akhir `meta_album`.
- **Actor Apify `pintostudio~youtube-transcript-scraper` bisa RUSAK total (`responseMessage is not defined`) — FIXED v1.32.0 dengan fallback:** Gejala: Tahap 1 gagal `RuntimeError: Apify HTTP 400` + `{"type":"run-failed",...,"status":"FAILED"}`. Cek log run (`/v2/actor-runs/<ID>/log`): `Something went wrong API failed. Error: responseMessage is not defined` lalu `Schema validation failed` pada `DatasetClient.pushItems`. **Ini bug di sisi actor, bukan pipeline** — dibuktikan video yang dulu sukses (`jUOuSiD_raE`) pun gagal saat kejadian (2026-09-26). **Fallback otomatis (v1.32.0):** kalau Apify gagal, pipeline ambil auto-caption langsung via yt-dlp (`fetch_transcript_ytdlp()` → `--write-auto-subs --sub-langs id,id-orig --sub-format json3`, di-parse ke format Apify `[{"data":[...]}]`). Terbukti jalan: 855 segmen dalam ~2s, gratis tanpa Apify. **Syarat:** video harus punya auto-caption. Cek lebih dulu: `yt-dlp --js-runtimes node --list-subs <URL>`.
- **Video tanpa auto-caption: Apify pun tidak bisa menolong (bukan soal actor rusak):** Beberapa video — terutama **live yang baru/streaming panjang** — tidak punya auto-caption sama sekali. Cek: `yt-dlp --list-subs` → `has no automatic captions` + `has no subtitles`. Contoh nyata 2026-09-26: `18898bVLUKc` dan `gCjTAhXPDa4` tidak punya caption, sementara `TIRxH3kHz8U` punya. **Tindakan:** lapor ke user bahwa video itu belum punya subtitle; minta coba lagi nanti (caption live kadang muncul setelah proses selesai) atau pilih video lain.
- **Gelar akademik di tag album — ingat tambah varian baru:** Regex pembersih di post-processing (`meta_album`) punya daftar gelar eksplisit. Varian yang PERNAH lolos & bikin album jelek: `M.H.` dan `S.H.` (fixed v1.32.0), juga `MARS.`, `Sp. KKLP.`, `M.Kes.`. Kalau muncul gelar baru yang tertinggal di tag album, tambahkan ke regex itu (dengan batas `(?<![\w.])` dan lookahead `(?=\s|$|[-–—|,;])` supaya nama seperti "Hamid"/"Sahid" tidak ikut terpotong).
- **Total runtime per durasi video:** Pipeline selesai dalam skala menit tergantung panjang video dan transcript. Data dari real runs:
  - **Video 40-50 min (~1000 segmen, 57K chars):** ~2-3 menit total dengan fix kecepatan — transcript fetch (10s), audio download (2-3 min), AI analysis (~25s), FFmpeg potong (20s).
  - **Video LIVE 81 min (1764 segmen, 95K chars):** ~2,5 menit total dengan fix — transcript fetch (14s), audio download (60s), AI analysis (~29s), FFmpeg potong 7 clip paralel (24s). (Run nyata 2026-09-14, 7 clip.)
  - **Video LIVE 90-180 min (100K-200K chars):** ~3-6 menit dengan fix. Tanpa `reasoning_effort=none`, Tahap 2 bisa 11-15 menit atau timeout 900s.
  - Saat dijalankan via Hermes agent, pipeline dapat terpotong oleh tool-call iteration limit sebelum selesai. **Mitigasi:** Gunakan background mode dengan notify_on_complete=true. Jika tool-call limit tercapai sebelum pipeline selesai, proses tetap berjalan di background — poll/log di turn berikutnya. Jangan delete output folder di tengah jalan kalau cache masih berguna untuk retry nanti.
