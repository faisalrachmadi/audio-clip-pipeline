# Ustadz Detection Failure Cases

Dokumentasi kasus di mana deteksi nama ustadz otomatis pipeline salah.
Gunakan ini sebagai referensi cepat untuk fix manual.

## Kasus 1: Inisial Dr. + H. greedy regex

**Video:** `Fase-Fase Dalam Mendidik Anak - Ustadz Dr. Hudzaifah M. Maricar, Lc., MA`
**Salah:** `Ustadz udzaifah M. Maricar` (huruf "H" kepotong)
**Benar:** `Ustadz Hudzaifah M. Maricar`
**Penyebab:** Regex hapus gelar di depan `H\.` (dengan titik) juga match huruf `H` pertama dari nama "Hudzaifah" karena pipeline hapus `H` tanpa lookahead batas token utuh.
**Fix:** `ffmpeg -i file.mp3 -c copy -metadata artist="Ustadz Hudzaifah M. Maricar" file_baru.mp3`

## Kasus 2: Channel name vs ustadz name

**Video:** `SALAH SATU KUNCI KESUKSESAN ADALAH DOA DARI ORANG TUA | BIKERS TALK - RIAL HAMZAH`
**Salah:** `Ustadz BIKERS TALK - RIAL HAMZAH` (channel name terdeteksi sebagai ustadz)
**Benar:** `Ustadz Subhan Bawazier`
**Penyebab:** Judul tidak punya prefix ustadz; fallback ambil segmen terakhir setelah `|`
**Fix:** `ffmpeg -i file.mp3 -c copy -metadata artist="Ustadz Subhan Bawazier" -metadata album="Kunci Kesuksesan Doa Orang Tua" file_baru.mp3`

## Kasus 3: Speaker bukan ustadz (nama konten kreator)

**Video:** `Inspirasi Hijrah — Ucapan Bismillah Bukan Kaleng-Kaleng - Maell Lee`
**Salah:** Tidak terdeteksi (clip tanpa nama ustadz)
**Benar:** `Ustadz Khalid Basalamah`
**Penyebab:** Judul tidak pakai prefix ustadz, dan "Maell Lee" bukan nama yang dikenali regex ustadz.
**Fix:** `ffmpeg -i file.mp3 -c copy -metadata artist="Ustadz Khalid Basalamah" -metadata album="Inspirasi Hijrah" file_baru.mp3`

## Kasus 4: Gelar panjang setelah koma

**Video:** `Yang Tidak Boleh di Abaikan — Ustadz DR Syafiq Riza Basalamah MA`
**Salah:** `Ustadz Syafiq Riza Basalamah MA` (MA kepanjangan)
**Benar:** `Ustadz Syafiq Riza Basalamah`
**Penyebab:** Regex potong setelah koma, tapi `MA` tanpa koma tidak terhapus.
**Fix:** Sudah ditangani pipeline (ambil max 6 kata), bisa diterima atau manual.

## Kasus 5: Nama ustadz di awal judul dengan separator hypen

**Contoh:** `Ustadz Adi Hidayat - Kajian Musawarah Fest`
**Salah:** Bisa terdeteksi ganda atau kelebihan kata
**Penyebab:** Regex prefix mendeteksi "Ustadz Adi Hidayat" dari awal, tapi separator `-` (hypen biasa) tidak dikenali fallback.
**Fix:** Pipeline punya prefix regex yang handle ini di langkah #1.

## Kasus 6: Prefix "Ustadz" diikuti teks deskriptif (bukan nama)

**Video:** `Ustadz dibayar Ngisi Kajian, Dosa atau Boleh`
**Salah:** `Ustadz dibayar Ngisi Kajian` (teks setelah "Ustadz" adalah deskripsi aktivitas, bukan nama)
**Benar:** `Ustadz Ammi Nur Baits` (setelah dikoreksi user)
**Penyebab:** Judul dimulai dengan prefix "Ustadz" → prefix regex match → pipeline ambil sisa teks setelah "Ustadz " → "dibayar Ngisi Kajian, Dosa atau Boleh" → strip setelah koma → "dibayar Ngisi Kajian" → tambah "Ustadz " kembali → "Ustadz dibayar Ngisi Kajian". Padahal teks setelah "Ustadz" adalah verb phrase (dibayar = paid), bukan nama orang.
**Ciri-ciri:** Judul dimulai "Ustadz [kata kerja]" atau "Ustadz [kalimat tanya]" — di mana kata setelah "Ustadz" bukan kata benda nama.
**Fix:** Manual rename setelah pipeline selesai, atau cari tahu nama ustadz dari user.

## Kasus 7: "Ust" (singkatan) tidak dikonversi ke "Ustadz" penuh

**Video:** `[FULL] Bab 33 Tawakal Kepada Allah - Kitab Tauhid 17 - Ust Badru Salam, Lc`
**Salah:** `Ust Badru Salam, Lc` (singkatan, bukan nama lengkap)
**Benar:** `Ustadz Badru Salam, Lc`
**Penyebab:** Pipeline tidak mendeteksi "Ust" (tanpa titik) sebagai variant — atau regex gagal konversi karena "Ust" diikuti langsung spasi + nama tanpa titik.
**Fix:** Manual rename + metadata: `ffmpeg -i file.mp3 -c copy -metadata artist="Ustadz Badru Salam, Lc" file_baru.mp3`

## Kasus 8: No prefix match + wrong fallback (speaker name in title)

**Video:** `TENANGKAN DIRIMU, PERCAYALAH ALLAH SELALU BERSAMAMU — Ustadz Syafiq Rizal Basalamah`
**Hasil:** Berhasil deteksi `Ustadz Syafiq Rizal Basalamah` ✅ (karena ada prefix + em dash separator)
**Catatan:** Berhasil karena judul punya em dash `—` sebagai separator dan "Ustadz" di segmen akhir.

## Kasus 9: Title series format → fallback mangled + WinError 123 crash

**Video:** `SERI 43 Minhaj Al-Firqah An-Naajiyah Bab 39 Cabang-cabang iman [1] Muflih Safitra, M.Sc`
**Salah:** `Ustadz Bab 39: Cabang-cabang iman [1] |` — mengandung karakter illegal Windows (`:`, `|`) → `os.rename` crash `OSError: [WinError 123] The filename, directory name, or volume label syntax is incorrect` di akhir pipeline (setelah clip 4/4 berhasil dipotong).
**Benar:** `Ustadz Muflih Safitra`
**Penyebab:** Judul tidak punya prefix ustadz dan tidak punya separator `|`/`–`/`—`; fallback regex salah menangkap segmen tengah judul + sisa pipe. Hasil rename mengandung `:` dan `|` yang illegal di Windows.
**Ciri-ciri:** Judul format seri (`SERI N ... Bab X ... [nomor]`) dengan nama pemateri di akhir tanpa separator.
**Fix:** Clip SUDAH jadi di `3_hasil_potong/` (potongan berhasil, cuma rename gagal). Rename manual + metadata via ffmpeg (`-metadata artist="Ustadz Muflih Safitra" -metadata album="SERI 43 Minhaj Al-Firqah An-Naajiyah Bab 39 Cabang-cabang iman [1]" -metadata date="2026"`). Album = judul video tanpa nama ustadz di akhir.

## Cara Fix Manual (Quick Command)

```bash
cd "D:/.../3_hasil_potong/"
for f in *.mp3; do
  clip_title="${f%% - Ustadz*}"
  ffmpeg -y -i "$f" -c copy \
    -metadata title="$clip_title" \
    -metadata artist="Ustadz Nama Yang Benar" \
    -metadata album="Judul Album" \
    -metadata date="2026" \
    "${clip_title} - Ustadz Nama Yang Benar.mp3"
  rm "$f"
done
```

## Cara Cek Metadata

```bash
ffprobe -v quiet -show_entries format_tags=title,artist,album file.mp3
```
