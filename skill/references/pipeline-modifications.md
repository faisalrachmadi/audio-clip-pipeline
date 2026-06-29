# Pipeline Modifications

## [2026-06-12] v1.2.0 — Rename & Metadata overhaul

**Perubahan besar:** Model, rename format, deteksi ustadz, metadata ID3.

### Model
- **Before:** `x-ai/grok-4.3`
- **After:** `deepseek/deepseek-v4-flash`
- **Alasan:** User switch provider

### Default
- **Before:** Auto clip dari durasi video (÷10)
- **After:** Default 5 clip, 4-6 menit jika user tidak sebut parameter
- **Alasan:** User request

### Execution
- **Before:** Jalankan langsung via `terminal()`
- **After:** Wajib via `delegate_task` (sub-agen), max 3 paralel
- **Alasan:** Biar bisa proses banyak video sekaligus

### sanitize() limit
- **Before:** `[:60]`
- **After:** `[:100]`
- **Alasan:** Folder output sering kepotong

### Rename clip (Post-Processing)
- **Before:** `01_metode-menghafal-al-quran.mp3` (kebab-case + nomor, dari AI)
- **After:** `Metode Menghafal Al Quran - Ustadz Abdul Somad.mp3` (Title Case, spasi, tanpa nomor, + nama ustadz)
- **Alasan:** User request format yang lebih rapi dan informatif

### Deteksi nama ustadz
- **Prefix regex:** Support `Ustadz`, `Ust.`, `Ust` (tanpa titik), `KH.`, `Kyai`, `Syekh`/`Syaikh`
- **Fallback:** Ambil segmen terakhir setelah separator `|` `–` `—`
- **Apostrophe:** Support `Rofi'i`, `Atho'illah` dll (`[A-Za-z\s.\'’]+`)
- **Gelar stripping:** Potong semua setelah koma: `re.sub(r',\s*.*$', '', raw_name)`
- **Singkatan depan:** Hapus `Dr.`, `H.`, `Hj.`, `Prof.`, `KH.` setelah "Ustadz"
- **Normalisasi:** "Ust." atau "Ust" → jadi "Ustadz"
- **Tambah prefix:** Jika nama tanpa prefix (fallback: "Khalid Basalamah" → "Ustadz Khalid Basalamah")
- **Max words:** 6 kata (biar muat nama panjang)

### Metadata ID3
- **Before:** Tidak ada metadata
- **After:**
  - **Title:** Judul clip (Title Case)
  - **Artist:** Nama ustadz (dengan Ustadz/Ust.)
  - **Album:** Judul video **tanpa** nama ustadz (dibersihkan)
  - **Date:** Tahun berjalan
- **Cara:** `-c copy` via FFmpeg (tanpa re-encode)

### Bug fixes sesi ini
1. Prefix regex tidak match "Ust." (hanya "Ustadz") → ditambah alternatif `Ust\.`
2. Apostrophe "Rofi'i" putuskan regex → ditambah `'` dan `’` ke character class
3. Fallback regex pakai `[A-Z]` untuk karakter pertama → diganti `.+` (apapun)
4. Gelar stripping daftar satu-satu → diganti potong semua setelah koma
5. Name_parts limit 4 kata → jadi 6 (biar muat nama panjang)
6. "Ust" tanpa titik jadi duplikasi "Ustadz Ust" → ditambah normalisasi `^Ust\.?\s+`
7. Album masih include nama ustadz → dibersihkan pakai match span

## [2026-06-14] v1.1.0 — Prompt: hindari opening, adzan, closing

**Perubahan:** System prompt di `pipeline.py` ATURAN SELEKSI CLIP.

**Before:**
- Rule 6: "Lewati semua segmen dengan start < 300 (5 menit pertama)" — hard-coded 5 menit
- Rule 7-9: topik berbeda, no overlap, clip akhir stop di akhir topik

**After:**
- Rule 6: HINDARI OPENING — deteksi dari teks (salam, basmalah, hamdalah, perkenalan)
- Rule 7: HINDARI ADZAN — skip lafadz/jeda adzan di tengah
- Rule 8: HINDARI CLOSING — doa penutup, wassalam, pengumuman, Q&A akhir
- Rule 9: topik berbeda (was #7)
- Rule 10: no overlap (was #8)

**Alasan:** User tidak ingin clip mengandung opening/adzan/closing. Pendekatan deteksi teks oleh AI lebih akurat daripada hard-code skip menit karena setiap video beda durasi opening-nya.
