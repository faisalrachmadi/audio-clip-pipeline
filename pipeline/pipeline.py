
"""
Pipeline: YouTube → Transcript + Video → Analisis AI → Clip MP4 (Talkshow Radio)
Usage:
  python pipeline.py <YOUTUBE_URL> [--clips N] [--min 1] [--max 2] [--skip-start M] [--audio]

Optimasi:
  A = FFmpeg parallel (clip dipotong bersamaan)
  C = Cache transcript (skip Apify kalau sudah ada)
"""

import json, os, re, sys, subprocess, shlex, time
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from dotenv import load_dotenv

# Fix: UTF-8 encoding for Windows console
if os.name == 'nt':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# --- Konfigurasi -------------------------------------------------
BASE_DIR = Path(__file__).parent.resolve()

load_dotenv(BASE_DIR / "1. apify + audio" / ".env")
APIFY_TOKEN = os.getenv("APIFY_TOKEN")

load_dotenv(BASE_DIR / "2. Analisa json" / ".env")
OPENCODE_KEY = os.getenv("OPENCODE_GO_API_KEY")

YT_DLP = r"C:\yt-dlp_win\yt-dlp.exe"
FFMPEG = r"C:\ffmpeg-2025-11-12-git-6cdd2cbe32-essentials_build\bin\ffmpeg.exe"

for path, name in [(YT_DLP, "yt-dlp"), (FFMPEG, "ffmpeg")]:
    if not os.path.exists(path):
        sys.exit(f"❌ {name} tidak ditemukan di: {path}")

APIFY_ACTOR = "https://api.apify.com/v2/acts/pintostudio~youtube-transcript-scraper/run-sync-get-dataset-items"
OPENCODE_URL = "https://opencode.ai/zen/go/v1/chat/completions"
MODEL_ID = "mimo-v2.5"

MAX_WORKERS = os.cpu_count() or 4


# --- Helper ------------------------------------------------------
def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def sanitize(text):
    """Remove chars unsafe for Windows paths."""
    text = re.sub(r'[\\/*?:"<>|' + """'!&#@%~`$+^""" + r']', '', text)
    return text.strip(" .-,()").rstrip(" .-,()")[:100].rstrip(" .-,()")


def parse_args():
    import argparse
    p = argparse.ArgumentParser(description="YouTube → Clip MP4 Pipeline (Talkshow Radio)")
    p.add_argument("url", help="URL YouTube")
    p.add_argument("--clips", type=int, default=0, help="Jumlah clip (0=auto, default: 0)")
    p.add_argument("--min", type=int, default=1, help="Durasi minimal per clip menit (default: 1)")
    p.add_argument("--max", type=int, default=2, help="Durasi maksimal per clip menit (default: 2)")
    p.add_argument("--skip-start", type=int, default=0, help="Skip N menit awal (default: 0)")
    p.add_argument("--audio", action="store_true", help="Audio-only mode (MP3, tanpa video)")
    return p.parse_args()


def run_subprocess(cmd, desc="proses", timeout=600, capture=True):
    """Jalankan subprocess."""
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


def get_media_duration(media_path):
    """Dapatkan durasi media dalam detik via ffprobe."""
    try:
        r = subprocess.run(
            [FFMPEG, "-i", str(media_path), "-f", "null", "-"],
            capture_output=True, text=True, errors="replace", timeout=30
        )
        m = re.search(r"Duration: (\d+):(\d+):(\d+)", r.stderr)
        if m:
            return int(m.group(1))*3600 + int(m.group(2))*60 + int(m.group(3))
    except Exception:
        pass
    return 0


def compute_clip_count(duration_sec):
    """Hitung jumlah clip optimal untuk talkshow radio (1-2 menit/clip)."""
    effective = max(0, duration_sec - 600)
    effective_min = effective / 60
    clips = max(3, min(15, round(effective_min / 4)))
    return clips


def download_video(url, video_path):
    """Download MP4 via yt-dlp dengan retry 1x."""
    video_path = Path(video_path)
    for attempt in range(2):
        try:
            run_subprocess(
                [YT_DLP, "--ignore-config",
                 "--merge-output-format", "mp4",
                 "--js-runtimes", "node",
                 "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                 "-o", str(video_path), url],
                desc=f"download video (percobaan {attempt+1})",
                timeout=600,
            )
            # yt-dlp kadang nambah extension (misal .mp4.mp4) karena config global
            # Cari file yg cocok di folder yang sama
            parent = video_path.parent
            stem = video_path.stem
            found = None
            for f in parent.glob(f"{stem}.*"):
                if f.suffix in (".mp4", ".mkv", ".webm", ".m4a", ".mp3"):
                    if f.suffix != ".mp4":
                        dest = parent / f"{stem}.mp4"
                        if f != dest:
                            if dest.exists():
                                dest.unlink()
                            f.rename(dest)
                            log(f"  \U0001f6e0\ufe0f  Rename {f.name} -> {dest.name}")
                        found = dest
                    else:
                        found = f
                    break
            if found and found.exists():
                return os.path.getsize(found)
            raise FileNotFoundError(f"File tidak ditemukan: {video_path}")
        except Exception as e:
            if attempt == 0:
                log(f"  \u26a0\ufe0f  Gagal, coba lagi: {e}")
                time.sleep(3)
            else:
                raise


def download_audio(url, audio_path):
    """Download audio MP3 via yt-dlp -x dengan retry 1x."""
    audio_path = Path(audio_path)
    for attempt in range(2):
        try:
            run_subprocess(
                [YT_DLP, "--ignore-config",
                 "-x", "--audio-format", "mp3",
                 "--js-runtimes", "node",
                 "-o", str(audio_path), url],
                desc=f"download audio (percobaan {attempt+1})",
                timeout=600,
            )
            parent = audio_path.parent
            stem = audio_path.stem
            for f in parent.glob(f"{stem}.*"):
                if f.suffix in (".mp3", ".m4a", ".opus", ".webm"):
                    if f != audio_path:
                        os.rename(f, audio_path)
                    break
            return audio_path.stat().st_size if audio_path.exists() else 0
        except Exception as e:
            if attempt == 0:
                log(f"  ⚠️ Download audio gagal: {e}, retry...")
            else:
                raise


def fetch_transcript(url, token):
    """Panggil Apify API, return data JSON."""
    resp = requests.post(
        f"{APIFY_ACTOR}?token={token}",
        json={"videoUrl": url},
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


# --- OPTIMASI C: Cache Transcript -------------------------------
def load_cached_transcript(transcript_path):
    """Coba load transcript dari cache."""
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


# --- TAHAP 1: Transcript + Video --------------------------------
def tahap1(url, output_dir, video_title, audio_mode=False):
    log("=== TAHAP 1: Transcript & Video ===")
    apify_dir = output_dir / "1_apify"
    apify_dir.mkdir(parents=True, exist_ok=True)
    transcript_path = apify_dir / "transcript.json"
    video_path = apify_dir / ("audio_full.mp3" if audio_mode else "video_full.mp4")

    if not APIFY_TOKEN and not transcript_path.exists():
        sys.exit("❌ APIFY_TOKEN tidak ditemukan di .env Tahap 1")

    # C: Cek cache transcript
    cached = load_cached_transcript(transcript_path)
    if cached:
        cached_data, seg_count = cached
        log(f"  📦 Transcript dari cache ({seg_count} segmen)")
        if not video_path.exists():
            if audio_mode:
                log(f"  ⚠️ audio_full.mp3 tidak ditemukan, download ulang audio...")
                download_audio(url, video_path)
            else:
                log(f"  ⚠️ video_full.mp4 tidak ditemukan, download ulang video...")
                download_video(url, video_path)
            log(f"  ✅ Media tersimpan ({video_path.stat().st_size/1024/1024:.1f} MB)")
    else:
        log("  📝 Cek transcript...")
        transcript_data = fetch_transcript(url, APIFY_TOKEN)
        seg_count = validate_transcript(transcript_data, transcript_path)
        log(f"  ✅ Transcript tersimpan ({seg_count} segmen)")

        if seg_count == 0:
            log("❌ Transcript kosong -- hentikan pipeline.")
            sys.exit("❌ Transcript kosong -- tidak ada segmen teks. Hentikan pipeline.")

        if audio_mode:
            log("  🎵 Transcript valid, lanjut download audio...")
            media_size = download_audio(url, video_path)
        else:
            log("  🎬 Transcript valid, lanjut download video...")
            media_size = download_video(url, video_path)
        log(f"  ✅ Media tersimpan ({media_size/1024/1024:.1f} MB)")

    # Hitung otomatis jumlah clip berdasarkan durasi video
    durasi_sec = get_media_duration(video_path)
    auto_clips = compute_clip_count(durasi_sec)
    log(f"  📊 Durasi: {durasi_sec//60} menit → rekomendasi {auto_clips} clip (1-2 menit/clip)")

    return str(video_path), str(transcript_path), auto_clips


# --- TAHAP 2: Analisis AI → BAT --------------------------------
def tahap2(transcript_path, output_dir, jumlah_clip, durasi_min, durasi_max, skip_start=0):
    log("=== TAHAP 2: Analisis AI → BAT ===")
    skip_seconds = skip_start * 60
    if skip_seconds > 0:
        log(f"  ⏭️ Skip {skip_start} menit awal ({skip_seconds}s)")
    analisa_dir = output_dir / "2_analisa"
    analisa_dir.mkdir(parents=True, exist_ok=True)

    if not OPENCODE_KEY:
        sys.exit("❌ OPENCODE_GO_API_KEY tidak ditemukan")

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
        log(f"  ⏭️ {skipped} segmen awal di-skip")

    if not lines:
        sys.exit("❌ Tidak ada teks untuk dianalisis. Hentikan pipeline.")

    full_transcript = "\n".join(lines)
    log(f"  Transcript: {len(lines)} baris, {len(full_transcript)} chars")

    SYSTEM_PROMPT = f"""Kamu adalah editor video profesional yang ahli memilih momen terbaik dari rekaman **talkshow radio** (wawancara, dialog interaktif, diskusi panel, dll).

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
- End time sebuah clip = `start` segment transcript terakhir + `dur` segment transcript terakhir
- Untuk FFmpeg:
  - **`-ss`** pakai format **`HH:MM:SS.ms`** (presisi milidetik)
  - **`-t`** (durasi clip) = end_detik - start_detik, pakai nilai presisi desimal
- Untuk nilai afade out (audio): st = durasi_detik - 2

Cara membaca konten:
- Baca teks BERURUTAN -- jangan lompat-lompat. Pahami alur percakapan.
- **Ini TALKSHOW RADIO**, ada host/penyiar dan narasumber/guest.
- Cari segmen percakapan yang **padat, menarik, dan berdiri sendiri**.

## TUGAS
Baca transcript dengan saksama. Tugasmu:
1. **Identifikasi segmen talkshow terbaik** -- cari momen tanya-jawab menarik, insight narasumber, cerita/opini kuat.
2. **Pilih N segmen terbaik** -- yang paling berdampak, informatif, atau engaging sebagai clip mandiri.
3. **Tentukan boundary clip** = awal & akhir satu sesi tanya-jawab atau satu topik mini.

## ATURAN SELEKSI CLIP
1. **WAJIB hindari:**
   - **BREAK IKLAN** -- segmen di mana host bilang "kita akan break", "setelah break", "kembali setelah ini", musik jeda iklan, dll.
   - **IKLAN RADIO** -- segmen promosi produk/sponsor, call to action iklan, tagline sponsor.
    - **ADZAN** -- segmen yang mengandung lafadz adzan atau jeda adzan.
   - **OPENING** -- salam pembuka, perkenalan host/narasumber, jingle pembuka.
   - **CLOSING** -- salam penutup, pengumuman acara mendatang, kredit penutup.
2. **Durasi WAJIB antara {durasi_min}-{durasi_max} menit.** JANGAN PERNAH melebihi {durasi_max} menit. Clip terlalu pendek (<45 detik) juga tidak boleh.
3. **SEBAR di seluruh durasi** -- jangan ambil semua clip dari 10 menit pertama saja.
4. **Pilih yang paling engaging:** debat menarik, curhat inspiratif, opini kontroversial, data/fakta mengejutkan, humor cerdas, cerita personal yang kuat.
5. Target sekitar {jumlah_clip} clip, jangan maksain -- kualitas > kuantitas.
6. **NO OVERLAP.** Clip WAJIB diurutkan berdasarkan waktu.

## FORMAT OUTPUT (ikuti persis, untuk setiap clip)
### Clip [Nomor]: [Judul Deskriptif Sesuai Isi Clip]
- **Kategori:** [Kategori, misal: Wawancara / Opini / Cerita / Debat / Fakta]
- **Mengapa dipilih:** [Alasan]
- **Awal topik (transcript):** [cuplikan 2-3 kata pertama]
- **Akhir topik (transcript):** [cuplikan 2-3 kata terakhir]
- **Start:** HH:MM:SS.ms
- **End:** HH:MM:SS.ms
- **Durasi:** X menit Y.Z detik

## SCRIPT .BAT
Setelah semua clip ditampilkan, buatkan satu file .bat lengkap dengan format berikut di dalam blok kode:

@echo off
SET INPUT=input.mp4

REM Clip 1 - [Judul]
ffmpeg -y -ss 00:01:30.000 -i "%%INPUT%%" -t 60.0 -c:v copy ^
  -af "loudnorm=I=-16:TP=-1.5:LRA=11,afade=t=in:st=0:d=2,afade=t=out:st=58.0:d=2" ^
  -c:a libmp3lame -b:a 192k "01_[judul-kebab-case].mp4"

Aturan nama file:
- Format: [nomor-2-digit]_[judul-singkat-kebab-case].mp4
- Maksimal 5 kata, huruf kecil, tanpa spasi/karakter khusus
- Nilai st (afade out) = total durasi_detik - 2
- Video stream: **WAJIB -c:v copy** (jangan re-encode video, biar cepat)
- INPUT pakai %%INPUT%% (double persen) biar bisa dibaca batch file"""

    log(f"  Mengirim ke OpenCode Go ({MODEL_ID})...")
    log(f"  Clip: {jumlah_clip}, Durasi: {durasi_min}-{durasi_max} menit")

    payload = {
        "model": MODEL_ID,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "Berikut adalah transkrip talkshow radio:\n\n" + full_transcript}
        ],
        "temperature": 0.2,
    }

    resp = requests.post(
        OPENCODE_URL,
        headers={
            "Authorization": f"Bearer {OPENCODE_KEY}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=1200,
    )

    if not resp.ok:
        sys.exit(f"❌ OpenCode Go gagal (HTTP {resp.status_code}): {resp.text[:300]}")

    ai_response = resp.json()["choices"][0]["message"]["content"]
    log(f"  ✅ Response AI ({len(ai_response)} chars)")

    log_path = analisa_dir / "potong_log_alasan.md"
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(ai_response)

    bat_match = re.search(
        r"```(?:bat|batch|cmd)?\n(.*?@echo off.*?)```",
        ai_response, re.DOTALL | re.IGNORECASE
    )
    if bat_match:
        bat_content = bat_match.group(1).strip()
    elif "@echo off" in ai_response:
        bat_content = ai_response[ai_response.find("@echo off"):].strip()
    else:
        log("  ⚠️ Format .bat tidak ditemukan, simpan raw output")
        bat_content = ai_response

    bat_content = bat_content.replace("%%INPUT%%", "%INPUT%")

    bat_path = analisa_dir / "potong.bat"
    with open(bat_path, "w", encoding="utf-8") as f:
        f.write(bat_content)
    log(f"  ✅ BAT tersimpan ({len(bat_content)} chars)")

    return str(bat_path)


# --- OPTIMASI A: Parse .bat → daftar perintah ------------------
def parse_ffmpeg_commands(bat_path, video_path, hasil_dir, audio_mode=False):
    """Parse file .bat jadi daftar perintah ffmpeg siap jalan."""
    max_seconds = 0
    try:
        r = subprocess.run(
            [FFMPEG, "-i", str(video_path), "-f", "null", "-"],
            capture_output=True, text=True, errors="replace", timeout=30
        )
        m = re.search(r"Duration: (\d+):(\d+):(\d+)", r.stderr)
        if m:
            max_seconds = int(m.group(1))*3600 + int(m.group(2))*60 + int(m.group(3))
    except Exception:
        pass

    with open(bat_path, "r", encoding="utf-8") as f:
        raw = f.read()

    # Gabung baris yang pecah pake ^ (line continuation)
    raw_joined = raw.replace("^\n", " ").replace("^\r\n", " ")
    lines = raw_joined.split("\n")

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
                        original = parts[ss_idx + 1]
                        corrected = f"00:{h:02d}:{m:02d}.{int(s):03d}"
                        parts[ss_idx + 1] = corrected
                        log(f"  🛠️ Timestamp {original} → {corrected} (dikoreksi)")
                except (ValueError, IndexError):
                    pass

        if "-i" in parts:
            i_idx = parts.index("-i")
            parts[i_idx + 1] = video_path

        # Pastikan ada -c:v copy (video stream copy)
        if "-c:v" not in parts and "-vn" not in parts:
            if "-i" in parts:
                i_idx = parts.index("-i")
                insert_at = i_idx + 2
                parts.insert(insert_at, "-c:v")
                parts.insert(insert_at + 1, "copy")
        elif "-vn" in parts:
            if not audio_mode:
                vn_idx = parts.index("-vn")
                parts[vn_idx] = "-c:v"
                parts.insert(vn_idx + 1, "copy")

        output_file = parts[-1]
        if audio_mode:
            if not output_file.lower().endswith(".mp3"):
                output_file = os.path.splitext(output_file)[0] + ".mp3"
            # Force audio-only
            if "-c:v" in parts:
                cv_idx = parts.index("-c:v")
                del parts[cv_idx:cv_idx+2]
            if "-vn" not in parts:
                parts.insert(-1, "-vn")
        else:
            if not output_file.lower().endswith(".mp4"):
                output_file = os.path.splitext(output_file)[0] + ".mp4"
        parts[-1] = str(hasil_dir / os.path.basename(output_file))
        parts[0] = FFMPEG

        commands.append(parts)

    return commands


def get_file_duration(filepath):
    """Dapatkan durasi real file video dalam format MM:SS."""
    try:
        r = subprocess.run(
            [FFMPEG, "-i", str(filepath), "-f", "null", "-"],
            capture_output=True, text=True, errors="replace", timeout=15
        )
        m = re.search(r"Duration: (\d+):(\d+):(\d+)", r.stderr)
        if m:
            h, m2, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
            total_menit = h * 60 + m2
            return f"{total_menit}:{int(s):02d}"
    except Exception:
        pass
    return "?"


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


# --- TAHAP 3: Potong Video (OPTIMASI A: Parallel FFmpeg) --------
def tahap3(video_path, bat_path, output_dir, audio_mode=False):
    log("=== TAHAP 3: Potong Video ===")
    hasil_dir = output_dir / "3_hasil_potong"
    hasil_dir.mkdir(parents=True, exist_ok=True)
    ext = "*.mp3" if audio_mode else "*.mp4"
    for old_file in hasil_dir.glob(ext):
        old_file.unlink()

    commands = parse_ffmpeg_commands(bat_path, video_path, hasil_dir, audio_mode=audio_mode)
    total = len(commands)

    if total == 0:
        sys.exit("❌ Tidak ada perintah ffmpeg valid di file .bat. Hentikan pipeline.")

    log(f"  Total clip: {total}, worker: {min(MAX_WORKERS, total)}")

    hasil = []
    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, total)) as exc:
        futures = {
            exc.submit(run_single_ffmpeg, cmd, i + 1, total): i + 1
            for i, cmd in enumerate(commands)
        }
        for future in as_completed(futures):
            hasil.append(future.result())

    hasil.sort(key=lambda x: x[0])

    sukses = 0
    for idx, ok, name, info, elapsed, durasi in hasil:
        if ok:
            log(f"  [{idx}/{total}] ✅ {name} ({durasi}, {info/1024:.0f} KB, {elapsed:.1f}s)")
            sukses += 1
        else:
            log(f"  [{idx}/{total}] ❌ {name}: {info}")

    clip_files = list(hasil_dir.glob("*.mp4"))
    total_size = sum(f.stat().st_size for f in clip_files)
    log(f"  ✅ {sukses}/{total} clip berhasil ({total_size/1024/1024:.1f} MB)")


# --- MAIN --------------------------------------------------------
def main():
    args = parse_args()
    log(f"🎬 URL: {args.url}")
    log(f"📊 Clip: {args.clips}, Durasi: {args.min}-{args.max} menit" + (f", Skip awal: {args.skip_start}m" if args.skip_start else ""))
    print()

    log("Mendapatkan judul video...")
    title = run_subprocess(
        [YT_DLP, "--get-title", args.url],
        desc="ambil judul"
    ).strip()
    folder_name = f"{datetime.now().strftime('%Y-%m-%d')}_{sanitize(title)}"
    output_dir = Path(r"D:\Insert Automation\Insert maker\automate insert\output") / folder_name
    output_dir.mkdir(parents=True, exist_ok=True)
    log(f"🎬 Output: {output_dir}\\n")

    try:
        video_path, transcript_path, auto_clips = tahap1(args.url, output_dir, title, audio_mode=args.audio)
        jumlah_clip = auto_clips if args.clips == 0 else args.clips
        log(f"📊 Clip: {jumlah_clip} (auto)" if args.clips == 0 else f"📊 Clip: {jumlah_clip} (manual)")
        log(f"   Durasi: {args.min}-{args.max} menit" + (f", Skip awal: {args.skip_start}m" if args.skip_start else ""))
        print()
        bat_path = tahap2(transcript_path, output_dir, jumlah_clip, args.min, args.max, args.skip_start)
        print()
        tahap3(video_path, bat_path, output_dir, audio_mode=args.audio)
        print()

        # --- Rename & Metadata ---
        hasil_dir = output_dir / "3_hasil_potong"
        clip_ext = "*.mp3" if args.audio else "*.mp4"
        clip_files = sorted(hasil_dir.glob(clip_ext))
        if clip_files:
            # Deteksi nama tokoh dari judul video
            tokoh_full = None
            tokoh_match = re.search(
                r'(Ustadz?\.?\s+(?:Dr\.?\s+)?(?:H\.?\s+)?(?:Hj\.?\s+)?[A-Za-z\s.\'\\u2019]+?'
                r'|Ust\.\s+(?:Dr\.?\s+)?(?:H\.?\s+)?(?:Hj\.?\s+)?[A-Za-z\s.\'\\u2019]+?)'
                r'(?:,|\||\\u2013|\\u2014|-|\bat\b|\bvia\b|$|\bBERSAMA\b|\bbersama\b)',
                title, re.IGNORECASE
            )
            if not tokoh_match:
                seg_match = re.search(r'[|\\u2013\\u2014]\s*(.+)$', title)
                if seg_match:
                    candidate = seg_match.group(1).strip()
                    words = candidate.split()
                    common = {"dan", "yang", "di", "ke", "dari", "untuk", "pada", "dengan", "oleh", "ini", "itu", "ada", "tidak", "akan", "telah", "sudah", "dalam", "setelah", "tentang", "live", "seri", "radio", "talkshow", "fm", "voice"}
                    has_letter = any(any(c.isalpha() for c in w) for w in words)
                    if has_letter and not all(w.lower() in common for w in words):
                        tokoh_match = seg_match

            if tokoh_match:
                raw_name = tokoh_match.group(1).strip().rstrip("., ")
                raw_name = re.sub(r',\s*.*$', '', raw_name).strip()
                raw_name = re.sub(r'\s*\[.*?\]\s*$', '', raw_name).strip()
                raw_name = re.sub(r'\s+via\s+.*$', '', raw_name, flags=re.IGNORECASE).strip()
                raw_name = re.sub(r'\s+live\s+.*$', '', raw_name, flags=re.IGNORECASE).strip()
                name_parts = raw_name.split()[:6]
                tokoh_full = " ".join(name_parts).strip().rstrip("., ")
                tokoh_full = re.sub(r'^Ust\.\s+', 'Ustadz ', tokoh_full, flags=re.IGNORECASE)
                tokoh_full = re.sub(r'^Ustadz\s+(?:Dr\.?\s*|H\.?\s*|Hj\.?\s*|Prof\.?\s*|KH\.?\s*)+', 'Ustadz ', tokoh_full, flags=re.IGNORECASE).strip()
                tokoh_full = re.sub(r'^Ust\.?\s+', 'Ustadz ', tokoh_full, flags=re.IGNORECASE)
                if not re.match(r'Ustadz?\.?\s', tokoh_full, re.IGNORECASE):
                    tokoh_full = f"Ustadz {tokoh_full}"
                log(f"  📝 Tokoh: {tokoh_full}")

            # Album: hapus nama tokoh dari judul
            if tokoh_match:
                ustart, uend = tokoh_match.start(), tokoh_match.end()
                if ustart == 0:
                    album_clean = title[uend:]
                    album_clean = re.sub(r'^\s*[-\\u2013\\u2014|,;]\s*', '', album_clean)
                elif uend == len(title):
                    album_clean = title[:ustart]
                    album_clean = re.sub(r'\s*[-\\u2013\\u2014|,;]\s*$', '', album_clean)
                else:
                    album_clean = title[:ustart] + title[uend:]
                    album_clean = album_clean.strip(" -\\u2013\\u2014|,;")
                meta_album = album_clean.strip()
            else:
                meta_album = title.strip()

            for f in clip_files:
                stem = f.stem
                clip_raw = re.sub(r'^\d+_', '', stem)
                clip_title = " ".join(w.capitalize() for w in clip_raw.replace("-", " ").replace("_", " ").split())

                if tokoh_full:
                    new_stem = f"{clip_title} - {tokoh_full}"
                else:
                    new_stem = clip_title

                new_path = f.parent / f"{new_stem}{f.suffix}"

                if new_path != f:
                    counter = 1
                    orig = new_path
                    while new_path.exists():
                        new_path = orig.parent / f"{orig.stem} ({counter}){orig.suffix}"
                        counter += 1
                    os.rename(f, new_path)
                    log(f"  🏷️ {f.name} → {new_path.name}")

                # Tambah metadata MP4
                try:
                    meta_title = clip_title
                    meta_artist = tokoh_full if tokoh_full else (re.sub(r'^.*?[-\\u2013|]\\s*', '', title).strip() or "Talkshow Radio")
                    temp_path = hasil_dir / f"_temp_{new_path.name}"
                    meta_cmd = [
                        FFMPEG, "-i", str(new_path),
                        "-map", "0",
                        "-c", "copy",
                        "-metadata", f"title={meta_title}",
                        "-metadata", f"artist={meta_artist}",
                        "-metadata", f"album={meta_album}",
                        "-metadata", f"date={datetime.now().year}",
                        "-y", str(temp_path)
                    ]
                    if not args.audio:
                        meta_cmd.insert(-1, "-movflags")
                        meta_cmd.insert(-1, "+faststart")
                    subprocess.run(meta_cmd, check=True, capture_output=True, timeout=30)
                    os.replace(temp_path, new_path)
                    log(f"  💿 Metadata: {meta_title} -- {meta_artist}")
                except Exception as e:
                    log(f"  ⚠️ Metadata gagal: {e}")

        log("🎉 PIPELINE SELESAI!")
        if video_path and os.path.exists(video_path):
            size_mb = os.path.getsize(video_path) / (1024*1024)
            for _attempt in range(5):
                try:
                    os.remove(video_path)
                    log(f"  📊 Media dihapus ({size_mb:.1f} MB)")
                    break
                except PermissionError:
                    if _attempt < 4:
                        time.sleep(1)
                    else:
                        log(f"  ⚠️ video_full.mp4 gagal dihapus (masih dipakai proses lain)")

    except (requests.exceptions.RequestException, subprocess.TimeoutExpired,
            subprocess.CalledProcessError, json.JSONDecodeError) as e:
        log(f"💥 Pipeline gagal: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
