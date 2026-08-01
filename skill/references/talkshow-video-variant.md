# Talkshow Video Variant (MP4)

Pipeline **sekarang default MP4 untuk talkshow radio**. Perubahan besar dari versi MP3 sebelumnya:

## Ringkasan Perubahan di pipeline.py (11 Jul 2026)

| Aspek | Sebelum (MP3) | Sesudah (MP4) |
|-------|---------------|---------------|
| Download | `download_audio()` — **bug: undefined!** | `download_video()` via `yt-dlp --merge-output-format mp4` |
| File source | `audio_full.mp3` | `video_full.mp4` |
| Output clip | `.mp3` | `.mp4` |
| FFmpeg video | `-vn` (no video) | `-c:v copy` (stream copy, no re-encode) |
| FFmpeg audio | loudnorm + afade | Sama (audio filter tetap) |
| Metadata | ID3 tags (`-write_id3v1`, `-id3v2_version 3`) | MP4 `-metadata` + `-movflags +faststart` |
| Default durasi | 4-6 menit | 1-2 menit |
| Auto clip | ÷10 (konservatif) | ÷4 (lebih banyak clip untuk 1-2 min) |
| AI fokus | Kajian (hindari opening/adzan/closing) | Talkshow radio (hindari break/iklan) |
| Cleanup | Hapus `audio_full.mp3` | Hapus `video_full.mp4` |

## Bug yang Diperbaiki

**`download_audio()` tidak pernah didefinisikan** — fungsi ini dipanggil di `tahap1()` baris 189 & 203 tapi tidak ada definisinya di mana pun. Pipeline lama bergantung pada cache transcript untuk menghindari code path itu (kalau transcript sudah cached dan audio ada, fungsi tidak dipanggil). Di versi baru, `download_audio()` diganti dengan `download_video()` yang sudah ada dan terdefinisi dengan benar (retry 1x).

## AI Prompt Baru (Talkshow Radio)

```python
SYSTEM_PROMPT = f"""...Kamu adalah editor video profesional yang ahli memilih momen terbaik
dari rekaman **talkshow radio** (wawancara, dialog interaktif, diskusi panel, dll).

## ATURAN SELEKSI CLIP
1. **WAJIB hindari:**
   - **BREAK IKLAN** - segmen host bilang "kita akan break", "setelah break", dll
   - **IKLAN RADIO** - promosi produk/sponsor, tagline sponsor
   - **OPENING** - salam pembuka, perkenalan host/narasumber
   - **CLOSING** - salam penutup, pengumuman acara mendatang
2. Durasi WAJIB antara {durasi_min}-{durasi_max} menit.
3. SEBAR di seluruh durasi.
4. Pilih yang paling engaging: debat, curhat, opini, fakta, humor, cerita personal.
5. Target ~{jumlah_clip} clip, kualitas > kuantitas.
6. NO OVERLAP, urut berdasarkan waktu.
..."""
```

Perbedaan utama dari prompt kajian:
- Spesifik tentang **break iklan** dan **iklan radio** (tidak ada di prompt kajian)
- Durasi lebih pendek (1-2 menit vs 4-6 menit)
- Fokus pada segmen **host-narasumber** bukan **ceramah/khutbah**
- Tidak ada aturan tentang adzan atau basmalah (karena talkshow radio umumnya tidak mengandung itu)

## FFmpeg Command Template (di AI Prompt .bat)

```batch
@echo off
SET INPUT=input.mp4

ffmpeg -y -ss 00:01:30.000 -i "%%INPUT%%" -t 60.0 -c:v copy ^
  -af "loudnorm=I=-16:TP=-1.5:LRA=11,afade=t=in:st=0:d=2,afade=t=out:st=58.0:d=2" ^
  -c:a libmp3lame -b:a 192k "01_judul.mp4"
```

Perubahan dari template lama:
- `-c:v copy` — stream copy video (tidak re-encode, cepat)
- `%%INPUT%%` — double persen (rawat di batch file)
- Output `.mp4` bukan `.mp3`
- Tidak ada `-vn`

## Cara Kembali ke Mode MP3 (Kajian)

Jika ingin MP3 (audio only) untuk konten kajian/ceramah:

1. Ubah `download_video()` call di `tahap1()` → `yt-dlp -x --audio-format mp3` (bikin ulang `download_audio()` atau inline call)
2. Di `parse_ffmpeg_commands()` & AI prompt: ganti `.mp4` → `.mp3`, hapus `-c:v copy`, tambah `-vn`
3. Di post-processing (`main()`): ganti glob `*.mp4` → `*.mp3`, metadata ID3 bukan MP4
4. Ganti default `--min 4 --max 6` di argparse

Atau maintain dua file terpisah: `pipeline.py` (MP4/talkshow) dan `pipeline_mp3.py` (MP3/kajian).
