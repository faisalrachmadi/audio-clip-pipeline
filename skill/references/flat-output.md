## Post-Run: Copy ke Flat Output

User sering minta semua clip dipindah ke `output/` (flat) setelah pipeline selesai, tanpa subfolder per-video. Lakukan ini setelah tiap batch selesai:

```bash
# Copy semua clip dari folder batch tertentu ke output/
for dir in "D:/Insert Automation/Insert maker/automate insert/output/YYYY-MM-DD"*; do
  sub="$dir/3_hasil_potong"
  if [ -d "$sub" ]; then
    cp -n "$sub"/*.mp3 "D:/Insert Automation/Insert maker/automate insert/output/"
  fi
done
```

Atau via Python (saat terminal broken):
```python
import os, shutil, glob
base = r"D:\Insert Automation\Insert maker\automate insert\output"
for folder in os.listdir(base):
    hasil = os.path.join(base, folder, "3_hasil_potong")
    if os.path.isdir(hasil):
        for f in glob.glob(os.path.join(hasil, "*.mp3")):
            dest = os.path.join(base, os.path.basename(f))
            if not os.path.exists(dest):
                shutil.copy2(f, dest)
```

Jangan pindahkan/move — gunakan **copy** (`cp -n` / `shutil.copy2`) agar struktur folder per-video tetap utuh sebagai backup.
