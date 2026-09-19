## Prompt Rules (WAJIB dipatuhi AI)

Aturan ini sudah tertanam di `pipeline.py` system prompt. Jika ada modifikasi prompt, edit langsung di file pipeline.py, lalu update referensi di sini.

### Mode KAJIAN (default lama, MP3, --min 4 --max 6)

- **Aturan K1:** CARI TRANSISI TOPIK DULU. Clip boundary = batas antar topik, bukan batas waktu.
- **Aturan K2:** DURASI WAJIB antara min-max menit. JANGAN PERNAH melebihi max. Jika topik panjang, potong bagian terbaik saja.
- **Aturan K3:** HINDARI clip di bawah 3 menit — gabungkan atau skip.
- **Aturan K4:** JANGAN potong per menit bulet. Boundary di akhir kalimat/paragraf transcript.
- **Aturan K5:** "Target ~N clip, jangan maksain" — prioritas selesainya satu pembahasan utuh.
- **Aturan K6:** HINDARI bagian OPENING. Jangan pilih clip yang mengandung salam pembuka, basmalah, hamdalah, atau perkenalan pembicara.
- **Aturan K7:** HINDARI bagian ADZAN. Jika transcript mengandung lafadz adzan atau jeda adzan, jangan pilih segmen itu.
- **Aturan K8:** HINDARI bagian CLOSING. Jangan pilih clip yang mencakup doa penutup, wassalam, pengumuman kajian berikutnya, atau Q&A akhir.
- **Aturan K9:** Clip harus dari topik berbeda, jangan berurutan, sebar di seluruh video.
- **Aturan K10:** NO OVERLAP. Clip WAJIB diurutkan berdasarkan waktu. Start berikutnya > end sebelumnya.

### Mode TALKSHOW RADIO (default baru, MP4, --min 1 --max 2)

- **Aturan T1:** **WAJIB hindari BREAK IKLAN** — segmen di mana host bilang "kita akan break", "setelah break", "kembali setelah ini", musik jeda iklan, dll.
- **Aturan T2:** **WAJIB hindari IKLAN RADIO** — segmen promosi produk/sponsor, call to action iklan, tagline sponsor.
- **Aturan T3:** **WAJIB hindari OPENING** — salam pembuka, perkenalan host/narasumber, jingle pembuka.
- **Aturan T4:** **WAJIB hindari CLOSING** — salam penutup, pengumuman acara mendatang, kredit penutup.
- **Aturan T5:** DURASI WAJIB antara min-max menit. JANGAN PERNAH melebihi max. Clip <45 detik juga tidak boleh.
- **Aturan T6:** SEBAR di seluruh durasi — jangan ambil semua clip dari 10 menit pertama saja.
- **Aturan T7:** Pilih segmen paling engaging: debat menarik, curhat inspiratif, opini kontroversial, data/fakta mengejutkan, humor cerdas, cerita personal yang kuat.
- **Aturan T8:** Clip = satu sesi tanya-jawab atau satu topik mini. No overlap, urut berdasarkan waktu.

> **Perubahan penting di v1.1.0:** Aturan #6-#8 lama = hindari opening/adzan/closing. Sebelumnya aturan #6 hard-code skip 5 menit pertama. Sekarang AI deteksi dari teks transcript, lebih akurat.

> **Perubahan penting di v1.13.0:** Default berubah ke mode Talkshow Radio (MP4, 1-2 min). Mode Kajian (MP3, 4-6 min) tersedia via parameter eksplisit `--min 4 --max 6`. Lihat `references/talkshow-video-variant.md` untuk detail perubahan pipeline.
