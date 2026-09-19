"""
Pipeline: YouTube → Transcript + Audio → Analisis AI → Clip MP3
Usage:
  python pipeline.py <YOUTUBE_URL> [--clips N] [--min M] [--max M]

Optimasi:
  A = FFmpeg parallel (clip dipotong bersamaan)
  C = Cache transcript (skip Apify kalau sudah ada)
"""

import json, os, re, sys, subprocess, shlex, shutil, time
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from dotenv import load_dotenv

# Fix: UTF-8 encoding for Windows console (biar gak perlu chcp 65001 manual)
if os.name == 'nt':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# ─── Konfigurasi ───────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.resolve()

load_dotenv(BASE_DIR / ".env")
APIFY_TOKEN = os.getenv("APIFY_TOKEN")
# API key: prioritaskan OpenCode Go (OPENCODE_GO_API_KEY), fallback DeepSeek direct (DEEPSEEK_API_KEY)
DEEPSEEK_KEY = os.getenv("OPENCODE_GO_API_KEY") or os.getenv("DEEPSEEK_API_KEY")

YT_DLP = shutil.which("yt-dlp")
FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")

if not YT_DLP:
    sys.exit("❌ yt-dlp tidak ditemukan di PATH")
if not FFMPEG:
    sys.exit("❌ ffmpeg tidak ditemukan di PATH")

APIFY_ACTOR = "https://api.apify.com/v2/acts/pintostudio~youtube-transcript-scraper/run-sync-get-dataset-items"

# ─── Provider AI (dipilih via env AI_PROVIDER) ─────────────────
# "openrouter" (default) atau "opencode". Kunci dibaca dari .env.
AI_PROVIDER = os.getenv("AI_PROVIDER", "openrouter").strip().lower()
if AI_PROVIDER == "openrouter":
    DEEPSEEK_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1") + "/chat/completions"
    DEEPSEEK_KEY = os.getenv("OPENROUTER_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
    MODEL_ID = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-v4.1-flash")
    AI_REASONING = os.getenv("OPENROUTER_REASONING", "")
    AI_EXTRA_HEADERS = {"HTTP-Referer": "https://localhost", "X-Title": "AutoClip Pipeline"}
else:
    DEEPSEEK_URL = os.getenv("OPENCODE_GO_BASE_URL", "https://opencode.ai/zen/go/v1") + "/chat/completions"
    DEEPSEEK_KEY = os.getenv("OPENCODE_GO_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
    MODEL_ID = os.getenv("OPENCODE_GO_MODEL", "mimo-v2.5")
    AI_REASONING = os.getenv("OPENCODE_GO_REASONING", "none")
    AI_EXTRA_HEADERS = {"x-opencode-session": "autoclip-pipeline-v1", "HTTP-Referer": "https://localhost", "X-Title": "AutoClip Pipeline"}

MAX_WORKERS = os.cpu_count() or 4


# ─── Helper ────────────────────────────────────────────────────
def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def sanitize(text):
    # Remove chars unsafe for Windows paths & command-line parsing (quotes, shell specials)
    text = re.sub(r'[\\/*?:"<>|' + r"""'!&#@%~`$+^""" + r']', '', text)
    return text.strip(" .-,()").rstrip(" .-,()")[:100].rstrip(" .-,()")


def bersihkan_gelar(nama):
    """Hapus gelar akademik di depan/belakang nama ustadz (Dr, Lc, MA, M.Sc, Ph.D, dll)."""
    deg = (r"(?:Dr|Drs|Dra|MA|M\.A|M\.Ag|M\.Pd|M\.Sc|M\.Si|MM|MBA|MPd|MAg|Lc|L\.c"
           r"|PhD|Ph\.D|S\.Pd|S\.Ag|S\.H|S\.E|S\.Sos|S\.T|S\.Kom|S\.Fil|SPd|SAg"
           r"|BA|ST|SE|SH|Prof|KH|Hj)")
    s = nama
    while True:
        prev = s
        # gelar di belakang - wajib ada pemisah (spasi/koma)
        s = re.sub(r"(?:\s*,\s*|\s+)" + deg + r"\.?\s*$", "", s, flags=re.IGNORECASE).strip()
        # gelar di depan setelah "Ustadz" - wajib pemisah, biar "Khalid" tidak kena "KH"
        s = re.sub(r"^Ustadz(?:\s*,\s*|\s+)(?:(?:" + deg + r")\.?(?:\s*,\s*|\s+))+",
                   "Ustadz ", s, flags=re.IGNORECASE).strip()
        if s == prev:
            break
    return s.rstrip("., ").strip()


def _normalisasi_judul(title):
    """Normalisasi judul untuk deteksi nama ustadz: buang tulisan Arab (doa/honorifik
    seperti حفظه الله), emoji, dan tag [LIVE] — supaya regex Latin bisa match sampai akhir."""
    t = re.sub(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]+', ' ', title)
    t = re.sub(r'[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F\u2B00-\u2BFF]', '', t)
    t = re.sub(r'\[(?:LIVE(?: TUNDA)?|REKAMAN|PREMIERE)\]', ' ', t, flags=re.IGNORECASE)
    t = re.sub(r'\s{2,}', ' ', t)
    return t.strip(' -–—|,;')


def parse_args():
    import argparse
    p = argparse.ArgumentParser(description="YouTube → Clip MP3 Pipeline")
    p.add_argument("url", help="URL YouTube")
    p.add_argument("--clips", type=int, default=5, help="Jumlah clip (0=auto berdasarkan durasi video, default: 5)")
    p.add_argument("--min", type=int, default=4, help="Durasi minimal per clip menit (default: 4)")
    p.add_argument("--max", type=int, default=6, help="Durasi maksimal per clip menit (default: 6)")
    p.add_argument("--skip-start", type=int, default=0, help="Skip N menit awal (default: 0)")
    return p.parse_args()


def run_subprocess(cmd, desc="proses", timeout=600, capture=True):
    """Jalankan subprocess. capture=True → return stdout; False → return None."""
    log(f"  ⏳ {desc}...")
    kwargs = dict(timeout=timeout,
                  creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    if capture:
        kwargs.update(capture_output=True, text=True, errors="replace")

    result = subprocess.run(cmd, **kwargs)
    if result.returncode != 0:
        err = result.stderr.strip()[:500] if capture else f"exit code {result.returncode}"
        raise RuntimeError(f"{desc} gagal: {err}")
    return result.stdout if capture else None


def _probe_duration_sec(path):
    """Durasi (detik) via ffprobe — baca header saja (~0.03s), bukan decode penuh (~3s)."""
    try:
        r = subprocess.run(
            [FFPROBE or "ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(path)],
            capture_output=True, text=True, errors="replace", timeout=30
        )
        return float(r.stdout.strip())
    except Exception:
        return 0.0


def get_audio_duration(audio_path):
    """Dapatkan durasi audio dalam detik via ffprobe (cepat: baca header)."""
    return int(_probe_duration_sec(audio_path))


def compute_clip_count(duration_sec):
    """Hitung jumlah clip optimal berdasarkan durasi efektif (skip 5 menit awal + 5 menit akhir)."""
    effective = max(0, duration_sec - 600)  # kurangi 10 menit (5 awal + 5 akhir)
    effective_min = effective / 60
    clips = max(3, min(12, round(effective_min / 10)))  # ~10 menit per clip, konservatif
    return clips


def download_audio(url, audio_path):
    """Download MP3 via yt-dlp dengan retry 1x."""
    for attempt in range(2):
        try:
            run_subprocess(
                [YT_DLP, "--js-runtimes", "node", "-x", "--audio-format", "mp3", "--audio-quality", "0",
                 "-o", str(audio_path), url],
                desc=f"download audio (percobaan {attempt+1})",
                timeout=600,
            )
            return os.path.getsize(audio_path)
        except Exception as e:
            if attempt == 0:
                log(f"  ⚠️  Gagal, coba lagi: {e}")
                time.sleep(3)
            else:
                raise


def fetch_transcript(url, token):
    """Panggil Apify API, return data JSON.

    targetLanguage: bahasa transcript. Default 'id' (asli video berbahasa Indonesia).
    Tanpa ini, Apify mengembalikan caption auto-translate (sering Inggris) sehingga
    kualitas pemilihan topik turun.
    """
    lang = os.getenv("APIFY_LANG", "id")
    resp = requests.post(
        f"{APIFY_ACTOR}?token={token}",
        json={"videoUrl": url, "targetLanguage": lang},
        timeout=300,
    )
    if not resp.ok:
        raise RuntimeError(f"Apify HTTP {resp.status_code}: {resp.text[:300]}")
    return resp.json()


def validate_transcript(transcript_data, transcript_path):
    """Simpan & validasi transcript. Return jumlah segmen."""
    with open(transcript_path, "w", encoding="utf-8") as f:
        json.dump(transcript_data, f, indent=4, ensure_ascii=False)

    seg_count = 0
    for block in transcript_data:
        if "data" in block:
            seg_count += len([s for s in block["data"] if s.get("text", "").strip()])
    return seg_count


# ─── OPTIMASI C: Cache Transcript ─────────────────────────────
def load_cached_transcript(transcript_path):
    """Coba load transcript dari cache. Return (data, seg_count) atau None."""
    if not transcript_path.exists():
        return None
    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        seg_count = 0
        for block in data:
            if "data" in block:
                seg_count += len([s for s in block["data"] if s.get("text", "").strip()])
        if seg_count > 0:
            return data, seg_count
    except (json.JSONDecodeError, KeyError):
        pass
    return None


# ─── TAHAP 1: Transcript + Audio ──────────────────────────────
def tahap1(url, output_dir, video_title):
    log("═══ TAHAP 1: Transcript & Audio ═══")
    apify_dir = output_dir / "1_apify"
    apify_dir.mkdir(parents=True, exist_ok=True)
    transcript_path = apify_dir / "transcript.json"
    audio_path = apify_dir / "audio_full.mp3"

    if not APIFY_TOKEN and not transcript_path.exists():
        sys.exit("❌ APIFY_TOKEN tidak ditemukan di .env Tahap 1")

    # ── C: Cek cache transcript ──
    cached = load_cached_transcript(transcript_path)
    if cached:
        cached_data, seg_count = cached
        log(f"  📦 Transcript dari cache ({seg_count} segmen)")
        # Cek apakah audio masih ada, kalo udah kedel eats, download ulang audio aja
        if not audio_path.exists():
            log(f"  ⚠️  audio_full.mp3 tidak ditemukan, download ulang audio...")
            download_audio(url, audio_path)
            log(f"  ✅ Audio tersimpan ({audio_path.stat().st_size/1024/1024:.1f} MB)")
    else:
        # ── Sequential: transcript dulu, baru audio (jika transcript ada) ──
        log("  📝 Cek transcript...")
        transcript_data = fetch_transcript(url, APIFY_TOKEN)
        seg_count = validate_transcript(transcript_data, transcript_path)
        log(f"  ✅ Transcript tersimpan ({seg_count} segmen)")

        if seg_count == 0:
            log("❌ Transcript kosong — hentikan pipeline.")
            sys.exit("❌ Transcript kosong — tidak ada segmen teks. Hentikan pipeline.")

        log("  🎵 Transcript valid, lanjut download audio...")
        audio_size = download_audio(url, audio_path)
        log(f"  ✅ Audio tersimpan ({audio_size/1024/1024:.1f} MB)")

    # ── Hitung otomatis jumlah clip berdasarkan durasi audio ──
    durasi_sec = get_audio_duration(audio_path)
    auto_clips = compute_clip_count(durasi_sec)
    log(f"  📊 Durasi: {durasi_sec//60} menit → rekomendasi {auto_clips} clip")

    return str(audio_path), str(transcript_path), auto_clips


# ─── TAHAP 2: Analisis AI → BAT ───────────────────────────────
def tahap2(transcript_path, output_dir, jumlah_clip, durasi_min, durasi_max, skip_start=0):
    log("═══ TAHAP 2: Analisis AI → BAT ═══")
    skip_seconds = skip_start * 60
    if skip_seconds > 0:
        log(f"  ⏭️  Skip {skip_start} menit awal ({skip_seconds}s)")
    analisa_dir = output_dir / "2_analisa"
    analisa_dir.mkdir(parents=True, exist_ok=True)

    if not DEEPSEEK_KEY:
        sys.exit(f"❌ API key AI ({AI_PROVIDER}) tidak ditemukan di .env")

    with open(transcript_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    lines = []
    skipped = 0
    for block in data:
        if "data" in block:
            for seg in block["data"]:
                start = seg.get("start", "")
                dur = seg.get("dur", "")
                text = seg.get("text", "").strip()
                if not text:
                    continue
                try:
                    start_sec = float(start)
                except (ValueError, TypeError):
                    start_sec = 0
                if skip_seconds > 0 and start_sec < skip_seconds:
                    skipped += 1
                    continue
                lines.append(f"[{start} - dur:{dur}] {text}")
    if skipped > 0:
        log(f"  ⏭️  {skipped} segmen awal di-skip")

    if not lines:
        sys.exit("❌ Tidak ada teks untuk dianalisis. Hentikan pipeline.")

    full_transcript = "\n".join(lines)
    log(f"  Transcript: {len(lines)} baris, {len(full_transcript)} chars")

    SYSTEM_PROMPT = f"""Kamu adalah editor audio/video profesional yang ahli memilih momen terbaik dari rekaman panjang (podcast, wawancara, talk show, seminar, dll).

## FORMAT TRANSCRIPT (JSON)
Transcript diberikan dalam format JSON array dengan struktur:
[
  {{
    "data": [
      {{
        "start": "detik_mulai",
        "dur": "durasi",
        "text": "isi teks"
      }}
    ]
  }}
]

Cara membaca timestamp:
- "start" adalah **detik** dari awal video. Contoh: start=305.5 berarti menit ke-5..detik 5.5
- Untuk clip boundary, **WAJIB pakai timestamp PRESISI dari transcript** (desimal), jangan dibulatkan ke menit bulet.
- End time sebuah clip = `start` segment transcript terakhir + `dur` segment transcript terakhir
- Untuk FFmpeg:
  - **`-ss`** pakai format **`HH:MM:SS.ms`** (presisi milidetik). Contoh: start=305.5 → `-ss 00:05:05.500`
  - **`-t`** (durasi clip) = end_detik - start_detik, **pakai nilai presisi desimal** (bisa koma). Contoh: durasi=294.7 → `-t 294.7`
- Untuk nilai afade out: st = durasi_detik - 2

Cara membaca konten:
- Baca teks BERURUTAN — jangan lompat-lompat. Pahami alur pembicaraan dari awal sampai akhir.
- **Cari transisi topik:** perhatikan saat pembicara:
  - Mengucapkan kata kunci transisi: "selanjutnya", "kemudian", "adapun", "berikutnya", "kita lanjut", "pindah ke", "selesai", "sekian", "kita tinggalkan"
  - Membuat kesimpulan/rangkuman dari satu poin
  - Mengubah topik secara natural (konteks bergeser)
- Tandai di mana topik LAMA berakhir dan topik BARU dimulai.
- Abaikan teks noise seperti "H ya", "I", "Hmm", "e", "anu"

## TUGAS
Baca transcript dengan saksama. Tugasmu:
1. **Identifikasi transisi topik** — baca konten teks, cari di mana pembicara selesai satu bahasan dan pindah ke bahasan baru.
2. **Pilih N topik terbaik** — pilih yang paling berdampak, informatif, atau menarik sebagai clip mandiri.
3. **Tentukan boundary clip = awal & akhir satu topik utuh.** Clip WAJIB mulai dari saat topik itu DIBUKA dan berakhir setelah topik itu TUNTAS dibahas. Jangan potong di tengah topik, di tengah kalimat, atau di tengah alur penjelasan.

Durasi clip ADALAH KONSEKUENSI DARI PANJANG TOPIK — bukan target yang harus dipaksakan seragam.

## ATURAN SELEKSI CLIP
1. **CARI TRANGSISI TOPIK DULU.** Baca teks transcript, identifikasi dimana pembahasan berganti (misal: pembicara selesai bahas topik A lalu bilang "selanjutnya..." / "berikutnya..." / "adapun..." / jeda panjang). Clip boundary = batas transisi topik.
2. **DURASI: {durasi_min}-{durasi_max} menit adalah PAGAR, bukan target.** JANGAN PERNAH melebihi {durasi_max} menit. Durasi tiap clip = JARAK dari awal topik sampai topik itu tuntas — jadi **setiap clip hampir pasti berbeda**. Kalau satu topik lebih panjang dari {durasi_max} menit, cari SUB-TOPIK utuh di dalamnya atau pilih topik lain yang muat — jangan potong di tengah alur.
3. **DURASI WAJIB BERAGAM.** Dilarang membuat semua clip berdurasi sama. Dilarang memakai angka bulat (240/300/360 detik atau 4:00/5:00/6:00). Pakai nilai detik desimal hasil boundary transcript (mis. 294.7, 331.2). Kalau dua clip kebetulan sama panjang, itu kecurigaan bahwa boundary belum mengikuti topik.
4. **HINDARI clip di bawah 3 menit** — terlalu pendek untuk konten mandiri. Gabungkan dengan topik kecil lain yang berdekatan, atau skip.
5. **Target {jumlah_clip} clip**, tapi utamakan MUTU & KEUTUHAN materi. Kalau transcript tidak punya cukup topik utuh yang bermutu, **LEBIH BAIK menghasilkan KURANG dari {jumlah_clip}** — jangan mengejar jumlah dengan memotong konteks.
6. **HINDARI bagian OPENING.** Jangan pilih clip yang mengandung salam pembuka (Assalamu'alaikum), basmalah (Bismillahirrahmanirrahim), puji-pujian (Alhamdulillah, hamdalah), atau perkenalan pembicara/pembawa acara. Clip harus dari ISI KAJIAN inti.
7. **HINDARI bagian ADZAN.** Jika transcript mengandung lafadz adzan atau jeda adzan di tengah video, jangan pilih segmen itu sebagai clip.
8. **HINDARI bagian CLOSING.** Jangan pilih clip yang mencakup doa penutup, wassalam, pengumuman kajian berikutnya, atau Q&A di akhir sesi. Clip AKHIR: berhenti di akhir topik kajian, potong SEBELUM penutup dimulai.
9. WAJIB: Clip harus dari TOPIK/BAHASAN yang berbeda-beda. Jangan berurutan/nyambung antar clip. Sebar di seluruh durasi video.
10. **NO OVERLAP. Clip WAJIB diurutkan berdasarkan waktu.** Start clip berikutnya HARUS > end clip sebelumnya. Cek ulang semua timestamp sebelum kirim output — pastikan tidak ada yang tumpang tindih.

## ATURAN KONTEKS (WAJIB)
- **Clip = 1 topik utuh.** Satu clip berisi satu pembahasan lengkap dari awal sampai tuntas.
- **Awal clip:** kalimat pertama topik yang bisa dipahami tanpa konteks sebelumnya.
- **Akhir clip:** kalimat TERAKHIR sebelum pembicara pindah ke topik baru. Cari di transcript: kata-kata penutup topik (kesimpulan, rangkuman) atau frasa transisi ("selanjutnya", "berikutnya", "adapun", "kita lanjut", "selesai", dll).
- **TIDAK BOLEH** potong di tengah kalimat, di tengah paragraf, atau saat pembicara masih menjelaskan satu poin.
- **WAJIB: durasi clip = {durasi_min}-{durasi_max} menit.** Clip TIDAK BOLEH melebihi {durasi_max} menit dalam keadaan apapun.
- **Kalau satu topik utuh lebih panjang dari {durasi_max} menit:** JANGAN potong asal di tengah — cari **SUB-TOPIK yang utuh** di dalamnya (yang punya pembuka & penutup sendiri), atau pilih topik lain yang muat. Yang dilarang: memotong di tengah alur penjelasan hanya demi durasi.
- **TES AKHIR (wajib dilakukan untuk setiap clip):** bayangkan clip diputar berdiri sendiri. Apakah pendengar paham dari awal sampai akhir, tanpa merasa ada bagian yang menggantung atau hilang? Kalau tidak, GESER boundary-nya sampai utuh.
- **PRIORITAS:** keutuhan konteks > jumlah clip > durasi maksimum.

**⚠️ DISIPLIN OUTPUT (WAJIB):** Kerjakan analisis, koreksi, dan pengecekan (termasuk TES AKHIR) secara **INTERNAL**. JANGAN tulis proses berpikir, pertimbangan, alternatif, atau revisi di jawaban. Output HARUS langsung: daftar clip FINAL sesuai format di bawah, lalu blok `.bat`. Jangan menulis "Clip 2 (Revisi)" atau mengulang clip.

## FORMAT OUTPUT (ikuti persis, untuk setiap clip)
### Clip [Nomor]: [Judul Deskriptif Sesuai Isi Clip]
- **Kategori:** [Kategori]
- **Mengapa dipilih:** [Alasan]
- **Awal topik (transcript):** [cuplikan 2-3 kata pertama dari transcript di titik awal]
- **Akhir topik (transcript):** [cuplikan 2-3 kata terakhir transcript sebelum transisi topik]
- **Start:** HH:MM:SS.ms
- **End:** HH:MM:SS.ms
- **Durasi:** X menit Y.Z detik

## SCRIPT .BAT
Setelah semua clip ditampilkan, buatkan satu file .bat lengkap dengan format berikut di dalam blok kode:

@echo off
SET INPUT=input.mp4

REM Clip 1 - [Judul]
ffmpeg -y -ss 00:05:05.500 -t 294.7 -i "%INPUT%" -vn -af "loudnorm=I=-16:TP=-1.5:LRA=11,afade=t=in:st=0:d=2,afade=t=out:st=292.7:d=2" -acodec libmp3lame -b:a 192k "01_[judul-kebab-case].mp3"

Aturan nama file:
- Format: [nomor-2-digit]_[judul-singkat-kebab-case].mp3
- Maksimal 5 kata, huruf kecil, tanpa spasi/karakter khusus
- Nilai [durasi_detik-2] = total durasi clip dikurangi 2"""

    log(f"  Mengirim ke {AI_PROVIDER} ({MODEL_ID})...")
    log(f"  Clip: {jumlah_clip}, Durasi: {durasi_min}-{durasi_max} menit")

    payload = {
        "model": MODEL_ID,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "Berikut adalah transkripnya:\n\n" + full_transcript}
        ],
        "temperature": 0.2,
    }
    # OpenCode Go: reasoning_effort=none (660s -> ~26s). OpenRouter: biarkan default kecuali di-set.
    if AI_REASONING:
        payload["reasoning_effort"] = AI_REASONING

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_KEY}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
        "Content-Type": "application/json",
        **AI_EXTRA_HEADERS,
    }

    ai_response = None
    last_err = None
    for attempt in range(1, 3):
        try:
            resp = requests.post(DEEPSEEK_URL, headers=headers, json=payload, timeout=300)
            if not resp.ok:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
            ai_response = resp.json()["choices"][0]["message"]["content"]
            break
        except Exception as e:
            last_err = e
            log(f"  ⚠️  AI gagal (percobaan {attempt}): {str(e)[:150]}")
            if attempt < 2:
                time.sleep(5)

    if ai_response is None:
        sys.exit(f"❌ AI gagal setelah 2 percobaan: {last_err}")

    log(f"  ✅ Response AI ({len(ai_response)} chars)")

    def _extract_bat(txt):
        m = re.search(r"```(?:bat|batch|cmd)?\n(.*?@echo off.*?)```", txt, re.DOTALL | re.IGNORECASE)
        if m:
            return m.group(1).strip()
        if "@echo off" in txt:
            return txt[txt.find("@echo off"):].strip()
        return txt

    bat_content = _extract_bat(ai_response)

    # ── Validasi durasi + overlap (deterministik). Kalau melanggar, minta AI perbaiki 1x ──
    min_sec, max_sec = durasi_min * 60, durasi_max * 60

    def _spans(txt):
        spans = []
        for m in re.finditer(r"-ss\s+(\d+):(\d+):(\d+(?:\.\d+)?)\s+-t\s+(\d+(?:\.\d+)?)", txt):
            h, mm, ss, d = m.groups()
            spans.append((int(h) * 3600 + int(mm) * 60 + float(ss), float(d)))
        return spans

    def _violations(txt):
        spans = _spans(txt)
        dur_bad = [round(d) for _, d in spans if d < min_sec or d > max_sec]
        ov = []
        srt = sorted(spans)
        for (s1, d1), (s2, _) in zip(srt, srt[1:]):
            if s2 < s1 + d1:
                ov.append((round(s1), round(s1 + d1), round(s2)))
        # Durasi seragam / angka bulat -> tanda AI memaksa durasi, bukan mengikuti topik
        uni = []
        vals = [round(d, 1) for _, d in spans]
        if len(vals) >= 3:
            best = max(set(vals), key=vals.count)
            n = vals.count(best)
            if n >= max(3, len(vals) - 1):
                uni = [best, n]
        return dur_bad, ov, uni

    for attempt in (1, 2):
        dur_bad, ov, uni = _violations(bat_content)
        if (not dur_bad and not ov and not uni) or attempt == 2:
            break
        issues = []
        if dur_bad:
            issues.append(f"durasi di luar {durasi_min}-{durasi_max} mnt: {dur_bad}s")
        if ov:
            issues.append(f"clip TUMPANG TINDIH (prev_start,prev_end,next_start): {ov}")
        if uni:
            issues.append(f"durasi SERAGAM: {uni[1]} clip sama-sama {uni[0]}s (harus mengikuti panjang topik)")
        log(f"  ⚠️  {'; '.join(issues)} → minta AI perbaiki")
        fix_msg = (
            "ATURAN DILANGGAR — " + "; ".join(issues) + ". "
            f"Tulis ULANG hanya blok .bat. WAJIB: (1) tiap clip {min_sec}-{max_sec} detik; "
            "(2) NO OVERLAP — start clip berikut HARUS > end clip sebelumnya, urut waktu; "
            "(3) boundary di akhir kalimat utuh, jangan potong di tengah pembahasan. "
            "Jangan bikin semua clip berdurasi sama; sesuaikan dengan panjang topik."
        )
        # ── Anti-seragam: durasi harus berasal dari boundary topik, bukan angka aman di tengah rentang ──
        fix_msg = (
            "ATURAN DILANGGAR — " + "; ".join(issues) + ". "
            "Perbaiki blok .bat SAJA, tapi HITUNG ULANG boundary dari transcript.\n"
            f"(1) Durasi = jarak awal-topik sampai topik tuntas. Rentang {min_sec}-{max_sec} detik itu PAGAR, bukan target.\n"
            "(2) DURASI WAJIB BERAGAM antar clip. DILARANG semua clip berdurasi sama. DILARANG angka bulat "
            "(240/300/360 atau 4:00/5:00/6:00) — pakai nilai desimal dari boundary kalimat transcript (mis. 287.4, 331.9).\n"
            "(3) NO OVERLAP — start clip berikut HARUS > end clip sebelumnya, urut waktu.\n"
            "(4) Boundary di akhir kalimat utuh, jangan potong di tengah pembahasan."
        )
        try:
            fix_payload = {
                "model": MODEL_ID,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": "Berikut adalah transkripnya:\n\n" + full_transcript},
                    {"role": "assistant", "content": ai_response},
                    {"role": "user", "content": fix_msg},
                ],
                "temperature": 0.2,
            }
            if AI_REASONING:
                fix_payload["reasoning_effort"] = AI_REASONING
            r2 = requests.post(DEEPSEEK_URL, headers=headers, json=fix_payload, timeout=300)
            if not r2.ok:
                log(f"  ⚠️  Re-ask gagal (HTTP {r2.status_code})")
                break
            ai_response = r2.json()["choices"][0]["message"]["content"]
            bat_content = _extract_bat(ai_response)
            log(f"  🔁 AI memperbaiki output ({len(ai_response)} chars)")
        except Exception as e:
            log(f"  ⚠️  Re-ask gagal: {str(e)[:120]}")
            break

    dur_bad, ov, uni = _violations(bat_content)
    if dur_bad or ov:
        log(f"  ⚠️  Masih ada pelanggaran (durasi={dur_bad}, overlap={ov}) — dibersihkan di Tahap 3")
    if uni:
        log(f"  ⚠️  Durasi seragam tersisa ({uni[1]} clip = {uni[0]}s) — topik mungkin belum dipisah natural")

    log_path = analisa_dir / "potong_log_alasan.md"
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(ai_response)

    bat_path = analisa_dir / "potong.bat"
    with open(bat_path, "w", encoding="utf-8") as f:
        f.write(bat_content)
    log(f"  ✅ BAT tersimpan ({len(bat_content)} chars)")

    return str(bat_path)


# ─── OPTIMASI A: Parse .bat → daftar perintah ──────────────────
def parse_ffmpeg_commands(bat_path, audio_path, hasil_dir):
    """Parse file .bat jadi daftar perintah ffmpeg siap jalan, validasi timestamp."""
    # Dapatkan durasi audio (dalam detik) untuk validasi — ffprobe, baca header saja
    max_seconds = int(_probe_duration_sec(audio_path))
    with open(bat_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    commands = []
    for line in lines:
        line = line.strip()
        if not line or line.lower().startswith("rem") or line.startswith("::"):
            continue

        parts = shlex.split(line)
        if "ffmpeg" not in os.path.basename(parts[0]).lower():
            continue

        # Validasi & koreksi timestamp -ss
        if max_seconds > 0 and "-ss" in parts:
            ss_idx = parts.index("-ss")
            ts_parts = parts[ss_idx + 1].split(":")
            if len(ts_parts) == 3:
                try:
                    h, m, s = int(ts_parts[0]), int(ts_parts[1]), float(ts_parts[2])
                    total_sec = h * 3600 + m * 60 + s
                    if h > 0 and total_sec > max_seconds * 2:
                        # AI salah baca MM:SS jadi HH:MM:SS, koreksi
                        original = parts[ss_idx + 1]
                        parts[ss_idx + 1] = f"00:{h:02d}:{m:02d}" if s == 0 else f"00:{h:02d}:{m:02d}"
                        log(f"  🛠️  Timestamp {original} → {parts[ss_idx + 1]} (dikoreksi)")
                except (ValueError, IndexError):
                    pass

        if "-i" in parts:
            i_idx = parts.index("-i")
            parts[i_idx + 1] = audio_path

        output_file = parts[-1]
        parts[-1] = str(hasil_dir / os.path.basename(output_file))
        parts[0] = FFMPEG

        commands.append(parts)
    return commands


def get_file_duration(filepath):
    """Durasi file audio (MM:SS) via ffprobe — baca header saja, bukan decode penuh."""
    total = _probe_duration_sec(filepath)
    if not total:
        return "?"
    return f"{int(total // 60)}:{int(total % 60):02d}"


def run_single_ffmpeg(cmd, idx, total):
    """Jalankan 1 perintah ffmpeg. Dipanggil dari thread pool."""
    out_name = os.path.basename(cmd[-1])
    try:
        start = time.time()
        subprocess.run(
            cmd, check=True, capture_output=True, text=True, timeout=600,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        )
        elapsed = time.time() - start
        size = os.path.getsize(cmd[-1])
        durasi = get_file_duration(cmd[-1])
        return (idx, True, out_name, size, elapsed, durasi)
    except Exception as e:
        return (idx, False, out_name, str(e)[:200], None, "")


# ─── TAHAP 3: Potong Audio (OPTIMASI A: Parallel FFmpeg) ──────
def tahap3(audio_path, bat_path, output_dir, durasi_min=None, durasi_max=None):
    log("═══ TAHAP 3: Potong Audio ═══")
    hasil_dir = output_dir / "3_hasil_potong"
    hasil_dir.mkdir(parents=True, exist_ok=True)
    # Bersihin file mp3 lama dari run sebelumnya (biar gak numpuk)
    for old_file in hasil_dir.glob("*.mp3"):
        old_file.unlink()

    commands = parse_ffmpeg_commands(bat_path, audio_path, hasil_dir)

    # ── Pengaman deterministik: urutkan per waktu, buang clip di luar rentang durasi & yang overlap ──
    def _c_start(cmd):
        if "-ss" in cmd:
            raw = cmd[cmd.index("-ss") + 1]
            try:
                p = raw.split(":")
                if len(p) == 3:
                    return int(p[0]) * 3600 + int(p[1]) * 60 + float(p[2])
                return float(raw)
            except (ValueError, IndexError):
                return None
        return None

    def _c_dur(cmd):
        if "-t" in cmd:
            try:
                return float(cmd[cmd.index("-t") + 1])
            except (ValueError, IndexError):
                return None
        return None

    timed = [(c, _c_start(c), _c_dur(c)) for c in commands]
    timed.sort(key=lambda x: (x[1] is None, x[1] if x[1] is not None else 0.0))

    kept = []
    last_end = None
    for cmd, s, d in timed:
        name = os.path.basename(cmd[-1])
        if durasi_min and durasi_max and d is not None and (d < durasi_min * 60 or d > durasi_max * 60):
            log(f"  ⏭️  Skip {name} ({d:.0f}s, di luar {durasi_min}-{durasi_max} mnt)")
            continue
        if s is not None and d is not None and last_end is not None and s < last_end:
            log(f"  ⏭️  Skip {name} (overlap: start {s:.0f}s < end sebelumnya {last_end:.0f}s)")
            continue
        kept.append(cmd)
        if s is not None and d is not None:
            last_end = s + d if last_end is None else max(last_end, s + d)

    commands = kept
    total = len(commands)

    if total == 0:
        sys.exit("❌ Tidak ada perintah ffmpeg valid di file .bat. Hentikan pipeline.")

    log(f"  Total clip: {total}, worker: {min(MAX_WORKERS, total)}")

    # ── A: Eksekusi parallel pake ThreadPoolExecutor ──
    hasil = []
    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, total)) as exc:
        futures = {
            exc.submit(run_single_ffmpeg, cmd, i + 1, total): i + 1
            for i, cmd in enumerate(commands)
        }

        for future in as_completed(futures):
            hasil.append(future.result())

    # Urutkan berdasarkan index clip
    hasil.sort(key=lambda x: x[0])

    # Tampilkan hasil
    sukses = 0
    for idx, ok, name, info, elapsed, durasi in hasil:
        if ok:
            log(f"  [{idx}/{total}] ✅ {name} ({durasi}, {info/1024:.0f} KB, {elapsed:.1f}s)")
            sukses += 1
        else:
            log(f"  [{idx}/{total}] ❌ {name}: {info}")

    clip_files = list(hasil_dir.glob("*.mp3"))
    total_size = sum(f.stat().st_size for f in clip_files)
    log(f"  ✅ {sukses}/{total} clip berhasil ({total_size/1024/1024:.1f} MB)")


# ─── MAIN ──────────────────────────────────────────────────────
def main():
    args = parse_args()
    log(f"🎬 URL: {args.url}")
    log(f"📐 Clip: {args.clips}, Durasi: {args.min}-{args.max} menit" + (f", Skip awal: {args.skip_start}m" if args.skip_start else ""))
    print()

    log("Mendapatkan judul video...")
    title = run_subprocess(
        [YT_DLP, "--js-runtimes", "node", "--get-title", args.url],
        desc="ambil judul"
    ).strip()
    folder_name = f"{datetime.now().strftime('%d-%m-%Y')}_{sanitize(title)}"
    output_dir = BASE_DIR / "output" / folder_name
    output_dir.mkdir(parents=True, exist_ok=True)
    log(f"📁 Output: {output_dir}\n")

    try:
        audio_path, transcript_path, auto_clips = tahap1(args.url, output_dir, title)
        # Auto-detect clips: jika --clips 0, pakai hasil hitung dari durasi audio
        jumlah_clip = auto_clips if args.clips == 0 else args.clips
        log(f"📐 Clip: {jumlah_clip} (auto)" if args.clips == 0 else f"📐 Clip: {jumlah_clip} (manual)")
        log(f"   Durasi: {args.min}-{args.max} menit" + (f", Skip awal: {args.skip_start}m" if args.skip_start else ""))
        print()
        bat_path = tahap2(transcript_path, output_dir, jumlah_clip, args.min, args.max, args.skip_start)
        print()
        tahap3(audio_path, bat_path, output_dir, args.min, args.max)
        print()
        # ── Rename & Metadata: format title case + tambah nama ustadz ──
        hasil_dir = output_dir / "3_hasil_potong"
        clip_files = sorted(hasil_dir.glob("*.mp3"))
        if clip_files:
            # Deteksi nama ustadz dari judul video.
            # Judul dinormalisasi dulu: buang tulisan Arab (doa/honorifik seperti حفظه الله),
            # emoji, dan tag [LIVE] — kalau tidak, kelas [A-Za-z...] gagal match & nama ustadz tak terdeteksi.
            title_detect = _normalisasi_judul(title)
            ustadz_full = None
            # 1. Coba pola dengan prefix (Ustadz, Ust., KH., dll)
            ustadz_match = re.search(
                r'(Ustadz?\.?\s+(?:Dr\.?\s+)?(?:H\.?\s+)?(?:Hj\.?\s+)?[A-Za-z\s.\'’]+?'
                r'|Ust\.\s+(?:Dr\.?\s+)?(?:H\.?\s+)?(?:Hj\.?\s+)?[A-Za-z\s.\'’]+?)'
                r'(?:,|\||–|—|-|\bat\b|\bvia\b|$)',
                title_detect, re.IGNORECASE
            )
            if not ustadz_match:
                # 2. Fallback: segmen terakhir setelah separator (wajib berspasi, biar "Fase-Fase" tidak kena)
                seg_match = re.search(r'\s[-–—|]\s+(.+)$', title_detect)
                if seg_match:
                    candidate = seg_match.group(1).strip()
                    # Filter: harus mengandung huruf (bukan cuma angka/simbol)
                    words = candidate.split()
                    common = {"dan", "yang", "di", "ke", "dari", "untuk", "pada", "dengan", "oleh", "ini", "itu", "ada", "tidak", "akan", "telah", "sudah", "dalam", "setelah", "tentang", "live", "seri"}
                    has_letter = any(any(c.isalpha() for c in w) for w in words)
                    if has_letter and not all(w.lower() in common for w in words):
                        ustadz_match = seg_match

            if ustadz_match:
                raw_name = ustadz_match.group(1).strip().rstrip("., ")
                # Hapus semua gelar/gelar: apapun setelah koma
                raw_name = re.sub(r',\s*.*$', '', raw_name).strip()
                # Bersihin info dalam kurung siku [...] di akhir
                raw_name = re.sub(r'\s*\[.*?\]\s*$', '', raw_name).strip()
                # Bersihin "via ...", "live", dll
                raw_name = re.sub(r'\s+via\s+.*$', '', raw_name, flags=re.IGNORECASE).strip()
                raw_name = re.sub(r'\s+live\s+.*$', '', raw_name, flags=re.IGNORECASE).strip()
                # Ambil maksimal 6 kata biar muat nama panjang
                name_parts = raw_name.split()[:6]
                ustadz_full = " ".join(name_parts).strip().rstrip("., ")
                # Pastikan diawali "Ustadz" — ganti "Ust." jadi "Ustadz"
                ustadz_full = re.sub(r'^Ust\.\s+', 'Ustadz ', ustadz_full, flags=re.IGNORECASE)
                # Hapus singkatan gelar di depan (Dr., H., Hj., Prof., KH.) — WAJIB diikuti spasi,
                # biar "Hudzaifah"/"Khalid" tidak kepotong jadi "udzaifah"/"alid"
                ustadz_full = re.sub(r'^Ustadz\s+(?:(?:Dr|H|Hj|Prof|KH)\.?\s+)+', 'Ustadz ', ustadz_full, flags=re.IGNORECASE).strip()
                # Ganti "Ust" (dengan/tanpa titik) jadi "Ustadz"
                ustadz_full = re.sub(r'^Ust\.?\s+', 'Ustadz ', ustadz_full, flags=re.IGNORECASE)
                if not re.match(r'Ustadz?\.?\s', ustadz_full, re.IGNORECASE):
                    ustadz_full = f"Ustadz {ustadz_full}"
                ustadz_full = bersihkan_gelar(ustadz_full)
                log(f"  👤 Ustadz: {ustadz_full}")

            # ── Album: hapus nama ustadz dari judul ──
            if ustadz_match:
                # Hapus bagian ustadz dari title untuk album
                ustart, uend = ustadz_match.start(), ustadz_match.end()
                if ustart == 0:
                    album_clean = title_detect[uend:]
                    album_clean = re.sub(r'^\s*[-–—|,;]\s*', '', album_clean)
                elif uend == len(title_detect):
                    album_clean = title_detect[:ustart]
                    album_clean = re.sub(r'\s*[-–—|,;]\s*$', '', album_clean)
                else:
                    album_clean = title_detect[:ustart] + title_detect[uend:]
                    album_clean = album_clean.strip(" -–—|,;")
                meta_album = album_clean.strip()
            else:
                meta_album = title_detect.strip()
            # Bersihkan sisa gelar akademik (mis. "M.Sc.") yang tertinggal setelah nama ustadz dihapus
            meta_album = re.sub(
                r'(?<![\w.])(?:M\.?\s*Sc\.?|M\.?\s*A\.?|M\.?\s*Ag\.?|M\.?\s*Pd\.?|M\.?\s*Hum\.?|M\.?\s*E\.?|Lc\.?|Ph\.?\s*D\.?|S\.?\s*Ag\.?|S\.?\s*Pd\.?|S\.?\s*Kom\.?|S\.?\s*T\.?|S\.?\s*S\.?)(?=\s|$|[-–—|,;])',
                '', meta_album, flags=re.IGNORECASE
            )
            # Rapikan separator ganda jadi satu, lalu spasi berlebih + buang separator menggantung
            meta_album = re.sub(r'\s*[|–—]\s*[|–—]\s*', ' | ', meta_album)
            meta_album = re.sub(r'^\s*[-–—|,;]+\s*', '', meta_album)
            meta_album = re.sub(r'\s*[-–—|,;]+\s*$', '', meta_album)
            meta_album = re.sub(r'\s{2,}', ' ', meta_album).strip()

            for f in clip_files:
                # Ekstrak judul clip dari nama file asli: "01_metode-menghafal-al-quran"
                stem = f.stem
                # Buang nomor di depan (01_, 01-, 01 , 02_, dll)
                clip_raw = re.sub(r'^\d+[\s_\-]+', '', stem)
                # Ubah kebab-case → Title Case
                clip_title = " ".join(w.capitalize() for w in clip_raw.replace("-", " ").replace("_", " ").split())
                
                # Susun nama file baru
                if ustadz_full:
                    new_stem = f"{clip_title} - {ustadz_full}"
                else:
                    new_stem = clip_title
                
                new_path = f.parent / f"{new_stem}{f.suffix}"
                
                # Rename file
                if new_path != f:
                    # Handle path conflict: nama file sudah ada
                    counter = 1
                    orig = new_path
                    while new_path.exists():
                        new_path = orig.parent / f"{orig.stem} ({counter}){orig.suffix}"
                        counter += 1
                    os.rename(f, new_path)
                    log(f"  🏷️  {f.name} → {new_path.name}")
                
                # ── Tambah metadata ID3 ──
                try:
                    meta_title = clip_title
                    meta_artist = ustadz_full if ustadz_full else (re.sub(r'^.*?[-–|]\s*', '', title_detect).strip() or "Kajian")
                    # meta_album sudah diset di atas (dibersihkan dari nama ustadz)
                    temp_path = hasil_dir / f"_temp_{new_path.name}"
                    subprocess.run([
                        FFMPEG, "-i", str(new_path),
                        "-map", "0:a",
                        "-c", "copy",
                        "-metadata", f"title={meta_title}",
                        "-metadata", f"artist={meta_artist}",
                        "-metadata", f"album={meta_album}",
                        "-metadata", f"date={datetime.now().year}",
                        "-write_id3v1", "1",
                        "-id3v2_version", "3",
                        "-y", str(temp_path)
                    ], check=True, capture_output=True, timeout=30)
                    os.replace(temp_path, new_path)
                    log(f"  💿 Metadata: {meta_title} — {meta_artist}")
                except Exception as e:
                    log(f"  ⚠️  Metadata gagal: {e}")
        log("🎉 PIPELINE SELESAI!")
        # Cleanup: hapus audio_full.mp3 (udah gak dipakai setelah clipping)
        if audio_path and os.path.exists(audio_path):
            size_mb = os.path.getsize(audio_path) / (1024*1024)
            # Retry loop: Windows kadang masih lock file habis ffmpeg paralel
            for _attempt in range(5):
                try:
                    os.remove(audio_path)
                    log(f"  🧹 audio_full.mp3 dihapus ({size_mb:.1f} MB)")
                    break
                except PermissionError:
                    if _attempt < 4:
                        time.sleep(1)
                    else:
                        log(f"  ⚠️  audio_full.mp3 gagal dihapus (masih dipakai proses lain)")
    except (requests.exceptions.RequestException, subprocess.TimeoutExpired,
            subprocess.CalledProcessError, json.JSONDecodeError) as e:
        log(f"💥 Pipeline gagal: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
