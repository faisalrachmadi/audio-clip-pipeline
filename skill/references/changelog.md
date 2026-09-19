# Changelog insert-radio

# CHANGES:
# 1.27.0 - OPTIMASI: probe durasi via ffprobe (baca header, ~0.03s) ganti ffmpeg -f null (decode penuh, ~3s)
#          di 3 tempat (get_audio_duration, parse_ffmpeg_commands, get_file_duration); tag album buang separator
#          menggantung; hapus dead code (_durs). Diukur: audio 78MB 3.24s -> 0.03s; clip 8MB 0.37s -> 0.03s.
# 1.26.0 - REKONSILIASI dari branch main: SYSTEM_PROMPT wajib KONTEKS UTUH (SUB-TOPIK kalau > max, TES AKHIR per clip
#          prioritas keutuhan konteks > jumlah clip > durasi), --clips default 5 (fixed, bukan auto),
#          bersihkan_gelar() hapus gelar akademik (guard pemisah; fix "KH" jangan makan "Khalid"), pitfall video DUO.
#          Mesin tetap versi server-linux (provider switch, targetLanguage=id, guard durasi+overlap, reasoning off).
# 1.25.0 - Tambah "Checklist Progres (per Tahap)" di SKILL.md (T0 preflight, T1-T3, post, publish, verifikasi akhir).
# 1.24.0 - Model Tahap 2 -> OpenCode Go `deepseek-v4.1-flash` (saldo pulih 2026-09-19). Switch provider via AI_PROVIDER.
# 1.22.0 - GUARD OVERLAP: Tahap 2 deteksi clip tumpang tindih -> minta AI perbaiki; Tahap 3 urutkan & buang clip overlap (deterministik).
#       - Catatan kualitas: AI cenderung mengunci durasi ke 300s (5:00) & memaksa batas -> rawan potong konteks/overlap.
# 1.21.0 - PROVIDER SWITCH via env AI_PROVIDER (openrouter | opencode). Default: openrouter (OpenCode Go saldo habis).
#          OpenRouter: base https://openrouter.ai/api/v1, model deepseek/deepseek-v4.1-flash, kunci OPENROUTER_API_KEY (ada di config OpenClaw).
#          reasoning_effort=none WAJIB juga utk OpenRouter: default 89s vs none 3s (probe transcript 59K char, video 56 mnt).
#          Hasil run nyata: Tahap 2 ~30s (default) / 8 clip 4-5 mnt, semua patuh rentang.
# 1.20.1 - Added pitfall: OpenCode Go CreditsError (HTTP 401 saldo habis) — stop, lapor user, simpan cache Tahap 1
# 1.20.0 - FIX KUALITAS: fetch_transcript kirim targetLanguage='id' (default, override env APIFY_LANG).
#          Tanpa ini Apify balas caption auto-translate (Inggris) -> AI salah pilih topik & durasi.
#       - GUARD DURASI: Tahap 2 validasi durasi clip; kalau di luar min-max, minta AI perbaiki 1x,
#          lalu Tahap 3 skip deterministik clip yang masih menyimpang (jangan hasilkan clip ngawur)
# 1.19.0 - Port ke Linux (server OpenClaw): path yt-dlp/ffmpeg dari PATH, .env tunggal di root,
#          yt-dlp standalone terbaru (apt dihapus) + --js-runtimes node, output folder dd-mm-yyyy
#       - KECEPATAN: payload AI kirim reasoning_effort=none -> Tahap 2 660s+ (atau timeout 900s)
#          turun jadi ~26-29s untuk transcript 95K char (~23x lebih cepat)
#       - Timeout AI 900s -> 300s + retry otomatis 2x (pengganti retry manual)
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
