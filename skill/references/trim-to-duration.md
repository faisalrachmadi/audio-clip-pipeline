# Trim Video ke N Menit Pertama

## Skenario

User ingin clip hanya dari **N menit pertama** video (misal kajian cuma 1 jam 25 menit pertama, sisanya Q&A atau gak relevan).

Pipeline tidak punya parameter `--max-duration`. Solusi: manual Tahap 1, lalu re-run.

## Langkah

### 1. Fetch transcript

```python
import requests, json, os, subprocess
from pathlib import Path
from datetime import datetime

API_TOKEN = "your_apify_token"
YT_DLP = r"C:\yt-dlp_win\yt-dlp.exe"
FFMPEG = r"C:\ffmpeg-...\bin\ffmpeg.exe"
BASE_DIR = Path(r"D:\Insert Automation\Insert maker\automate insert")
URL = "https://youtube.com/..."
MAX_SEC = 85 * 60  # 1 jam 25 menit = 5100 detik

# Get title
title = subprocess.run([YT_DLP, "--get-title", URL], capture_output=True, text=True).stdout.strip()
import re
def sanitize(t):
    return re.sub(r'[\\/*?:"<>|]', "", t).strip(" .-,()").rstrip(" .-,()")[:60].rstrip(" .-,()")
folder = f'{datetime.now().strftime("%Y-%m-%d")}_{sanitize(title)}'
out_dir = BASE_DIR / "output" / folder
apify_dir = out_dir / "1_apify"
apify_dir.mkdir(parents=True, exist_ok=True)

# Fetch transcript
resp = requests.post(
    f"https://api.apify.com/v2/acts/pintostudio~youtube-transcript-scraper/run-sync-get-dataset-items?token={API_TOKEN}",
    json={"videoUrl": URL, "targetLanguage": "en"}, timeout=300
)
data = resp.json()
```

### 2. Filter transcript ke < MAX_SEC

```python
filtered = []
for block in data:
    if "data" in block:
        segs = [s for s in block["data"] if s.get("text","").strip() and float(s.get("start", 0)) < MAX_SEC]
        filtered.append({"data": segs})
    else:
        filtered.append(block)

with open(apify_dir / "transcript.json", "w", encoding="utf-8") as f:
    json.dump(filtered, f, indent=4, ensure_ascii=False)
print(f"Segmen tersimpan: {sum(len(b.get('data',[])) for b in filtered)}")
```

### 3. Download audio + trim

```python
audio_path = apify_dir / "audio_full.mp3"
subprocess.run([YT_DLP, "-x", "--audio-format", "mp3", "--audio-quality", "0", "-o", str(audio_path), URL], check=True, timeout=600)

# Trim
trimmed = apify_dir / "audio_full_trimmed.mp3"
subprocess.run([FFMPEG, "-y", "-i", str(audio_path), "-ss", "0", "-t", str(MAX_SEC), "-acodec", "libmp3lame", "-b:a", "192k", str(trimmed)], check=True, timeout=120)
os.remove(audio_path)
os.rename(trimmed, audio_path)
print(f"Audio trimmed: {audio_path.stat().st_size/1024/1024:.1f} MB")
```

### 4. Jalankan pipeline

Pipeline akan deteksi transcript.json + audio_full.mp3, skip Tahap 1, langsung ke Tahap 2 & 3.

```bash
cd "D:/Insert Automation/Insert maker/automate insert/1. apify + audio"
source venv/Scripts/activate
python ../pipeline.py "URL" [--clips N]
```

## Catatan

- **Durasi untuk auto clip count** dihitung dari audio hasil trim, bukan video asli.
- **Gunakan `--clips N`** jika auto-count terlalu banyak/sedikit untuk durasi terbatas.
- **Transcript original** bisa ribuan segmen — filter sebelum MAX_SEC penting agar AI hanya analisis bagian yang relevan.
- **Audionya bisa >100MB** untuk video 2 jam — trimming dengan ffmpeg cepat (~1 menit).
