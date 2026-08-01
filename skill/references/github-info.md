# GitHub Repo — Audio Clip Pipeline

**Repo:** https://github.com/faisalrachmadi/audio-clip-pipeline

## Isi Repo

```
audio-clip-pipeline/
├── README.md          ← Cara pakai lengkap (ID)
├── .gitignore
├── pipeline/
│   ├── pipeline.py    ← Script utama insert-radio
│   ├── requirements.txt
│   └── .env.example
└── skill/
    ├── SKILL.md       ← Skill Hermes Agent (insert-radio)
    └── references/
        ├── pipeline-modifications.md
        └── trim-to-duration.md
```

## Cara Share

Cukup kirim link: https://github.com/faisalrachmadi/audio-clip-pipeline

## Cara Clone & Setup

```bash
git clone https://github.com/faisalrachmadi/audio-clip-pipeline.git
cd audio-clip-pipeline/pipeline
python -m venv venv
# Windows: source venv/Scripts/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env: isi APIFY_TOKEN & OPENROUTER_API_KEY
```

## Prerequisites yang Perlu Diinstall Sendiri

- **yt-dlp** — download audio YouTube (https://github.com/yt-dlp/yt-dlp)
- **FFmpeg** — potong audio (https://ffmpeg.org/)
- **Python 3.10+**
