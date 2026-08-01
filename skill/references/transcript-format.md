# Apify Transcript Format & convert_subs.py

## Apify API Contract

Pipeline menggunakan actor `pintostudio~youtube-transcript-scraper`:

```
POST https://api.apify.com/v2/acts/pintostudio~youtube-transcript-scraper/run-sync-get-dataset-items?token={TOKEN}
Body: {"videoUrl": "https://youtube.com/watch?v=..."}
```

Response adalah array JSON, setiap elemen:
```json
{
  "data": [
    {
      "start": "305.500",    // detik dari awal video
      "dur": "4.320",        // durasi segmen ini (detik)
      "text": "isi teks"     // teks caption
    }
  ]
}
```

- `start` dan `dur` dalam format string desimal (PRESISI milidetik)
- Satu elemen `data` bisa punya beberapa segmen dalam array
- Jika video tidak punya caption, API return `{"data": []}` (array kosong)

## YouTube JSON3 Format (Auto-Captions)

YouTube auto-captions kadang hanya tersedia dalam format JSON3 (bukan via Apify). Format:

```json
{
  "events": [
    {
      "tStartMs": 305500,        // millisecond
      "dDurationMs": 4320,       // millisecond
      "segs": [
        {"utf8": "teks "},
        {"utf8": "lanjutan"}
      ]
    }
  ]
}
```

## convert_subs.py

Lokasi: `D:\Insert Automation\Insert maker\automate insert-video\1. apify + audio\convert_subs.py`

Utility untuk konversi YouTube JSON3 → format Apify transcript:

```bash
python convert_subs.py input.json3 output.json
```

Cocok dipakai saat:
- Apify gagal fetch transcript (video tanpa CC)
- Video punya auto-captions yang didownload manual via yt-dlp: `yt-dlp --write-auto-subs --sub-format json3 --skip-download <URL>`
- Butuh transcript cepat tanpa menunggu Apify

## Pipeline Transcript Cache (Optimasi C)

Pipeline otomatis cache transcript ke `1_apify/transcript.json`. Sebelum panggil Apify, pipeline cek:
1. Apakah file `transcript.json` ada
2. Parse JSON
3. Validasi `seg_count > 0`

Kalau valid, skip Apify (hemat ~10-30 detik per run). Audio tetap didownload ulang kalau `audio_full.mp3` tidak ada (misal terhapus oleh cleanup run sebelumnya).

## Key Implementation Detail (pipeline.py)

Di `tahap2()`, transcript di-*flatten* jadi format baris untuk AI prompt:

```
[start - dur:dur] text
```

Contoh: `[305.500 - dur:4.320] Bismillahirrahmanirrahim`

Yang penting:
- Baris dengan `start < skip_start*60` dihapus (jika `--skip-start` dipakai)
- Teks kosong dilewati
- AI mendapat teks berurutan untuk deteksi transisi topik
- Timestamp PRESISI (desimal, bukan integer) — AI WAJIB generate timestamp presisi juga
