# yt-dlp Cookies & Authentication

YouTube semakin ketat memblokir request tanpa autentikasi. Pipeline gagal di Tahap 1 dengan error **HTTP 429 Too Many Requests** kalau yt-dlp tidak punya cookies valid.

## Error yang Muncul

```
WARNING: [youtube] VIDEO_ID: Unable to download webpage: HTTP Error 429: Too Many Requests
...
ERROR: [youtube] VIDEO_ID: Sign in to confirm you're not a bot.
```

Pipeline berhenti total — tidak bisa lanjut ke download audio atau Tahap 2/3.

## Diagnosa Cepat

| Command | Hasil | Arti |
|---------|-------|------|
| `yt-dlp --get-title <URL>` | 429 + "Sign in" | Blokir total — butuh cookies |
| `yt-dlp --cookies-from-browser chrome --get-title <URL>` | "Could not copy" | Chrome sedang berjalan, cookie DB terkunci |
| `yt-dlp --extractor-args "youtube:player_client=android" --get-title <URL>` | "This live event has ended" + SABR warning | Android client berhasil parsing tapi video ended live stream — tetap butuh token |

## Solusi

### Opsi A: Tutup browser, lalu --cookies-from-browser

1. **Tutup SEMUA window Chrome/Edge** (pastikan tidak ada proses `chrome.exe` / `msedge.exe` di Task Manager)
2. Jalankan pipeline ulang — yt-dlp bisa akses cookie database karena tidak terkunci

### Opsi B: Export cookies.txt manual

1. Install extension **Get cookies.txt** (Chrome Web Store) atau **cookies.txt** (Firefox)
2. Login ke YouTube.com di browser
3. Export cookies ke file teks, simpan sebagai `cookies.txt` di `C:\yt-dlp_win\cookies.txt`
4. Patch pipeline.py tambah arg `--cookies` di command yt-dlp:
   ```python
   # pipeline.py, cari command yt-dlp, tambah:
   YTDLP_COOKIES = "--cookies C:\\yt-dlp_win\\cookies.txt"
   ```
   Atau langsung edit di tempat pemanggilan — cari `[YT_DLP, "-x", "--audio-format"]` dan `[YT_DLP, "--get-title"]`, tambah `--cookies` setelah `YT_DLP`.

### Opsi C: Ambil judul via oEmbed API (workaround untuk title)

Kalau cuma butuh judul video (Tahap 1 step title), bisa bypass yt-dlp sama sekali:

```bash
curl -s "https://www.youtube.com/oembed?url=<URL>&format=json"
```

Response JSON langsung kasih `title` dan `author_name`. Tapi ini **hanya untuk judul** — download audio tetap butuh yt-dlp + cookies.

## Catatan

- **`player_client=android`** bisa bypass 429 untuk video normal, tapi **tidak cukup** untuk:
  - Ended live streams (butuh PO Token untuk SABR-only streaming)
  - Age-restricted videos
  - Private/unlisted videos
- **JS Runtime warning** ("No supported JavaScript runtime could be found") adalah **warning harmless** — tidak blocking, tidak perlu install deno/node
- Cookies perlu **dire-export secara berkala** — YouTube cookies expire
