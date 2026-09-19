"""
Runner SEQUENTIAL untuk insert-radio pipeline (Linux).
Menjalankan beberapa video SATU PER SATU untuk menghindari rate-limit API.

Cara pakai:
  python3 run_sequential.py "URL1" "URL2" "URL3" [--clips 5] [--skip-start M1 M2 ...]
  - --skip-start: offset menit skip awal per URL (optional, harus sejumlah URL)
"""

import subprocess
import sys
import shlex
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PIPELINE = os.path.join(BASE_DIR, "pipeline.py")
PYTHON = sys.executable

def parse_args(argv):
    urls = []
    clips = 5
    skip_starts = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--clips":
            clips = int(argv[i+1]); i += 2; continue
        if a == "--skip-start":
            # next N tokens are minutes
            rest = argv[i+1:]
            skip_starts = [int(x) for x in rest]
            break
        urls.append(a)
        i += 1
    return urls, clips, skip_starts

def main():
    urls, clips, skip_starts = parse_args(sys.argv[1:])
    if not urls:
        print("Gunakan: python3 run_sequential.py URL1 URL2 ... [--clips N] [--skip-start m1 m2 ...]")
        return

    if skip_starts and len(skip_starts) != len(urls):
        print(f"⚠️  --skip-start jumlah ({len(skip_starts)}) != jumlah URL ({len(urls)}). Abaikan skip.")
        skip_starts = []

    print(f"🚀 {len(urls)} video akan jalan SEQUENTIAL (1-per-1). Clips={clips}")
    for idx, url in enumerate(urls, 1):
        skip = skip_starts[idx-1] if skip_starts else None
        cmd = [PYTHON, PIPELINE, url, "--clips", str(clips), "--min", "4", "--max", "6"]
        if skip:
            cmd += ["--skip-start", str(skip)]
        print(f"\n{'='*60}\n▶  [{idx}/{len(urls)}] {url}" + (f"  (skip {skip}m)" if skip else "") + f"\n  CMD: {' '.join(shlex.quote(c) for c in cmd)}\n{'='*60}")
        r = subprocess.run(cmd)
        status = "✅ OK" if r.returncode == 0 else f"❌ FAIL (exit {r.returncode})"
        print(f"\n>>> VIDEO {idx} {status}")
        print(f">>> Lanjut video berikutnya...\n")

    print("\n🎉 SEMUA SEQUENTIAL SELESAI.")

if __name__ == "__main__":
    main()
