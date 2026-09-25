# Transcritor

Free, private transcription for interviews and recorded classes on a Mac, powered by OpenAI's open-source Whisper model (large-v3-turbo). Everything runs locally — no API key, no cost, nothing uploaded.

- **Apple Silicon Macs:** [mlx-whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper) (uses the GPU)
- **Intel Macs:** [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (CPU)
- Drag-and-drop web interface in Portuguese and English, running on `127.0.0.1` only
- Exports Word (.docx), plain text, text with timestamps, and subtitles (.srt) to `~/Documents/Transcritor`

## Install (for end users)

1. Download **Transcritor.zip** from the [latest release](../../releases/latest) and unzip it.
   *(Use the release zip, not "Code → Download ZIP" — the release keeps the installer executable.)*
2. Double-click **Instalar Transcritor.command**. If macOS blocks it: System Settings → Privacy & Security → **Open Anyway**.
3. Wait for "✓ All set!" (~10 min; downloads the model, ~1.5 GB). A **Transcritor** app appears in Applications.

See `LEIA-ME · READ ME.txt` for full bilingual instructions.

## How it works

| File | Purpose |
|---|---|
| `Instalar Transcritor.command` | Installs [uv](https://github.com/astral-sh/uv), Python 3.12 and dependencies into `~/Library/Application Support/Transcritor`, pre-downloads the model, builds `Transcritor.app` |
| `app/run.sh` | Starts the local server (under `caffeinate`) and opens the browser |
| `app/server.py` | Flask server with a job queue; auto-quits 15 min after the window closes |
| `app/engine.py` | Whisper backends + audio/video decoding via PyAV (no ffmpeg needed) |
| `app/formats.py` | Paragraphing and .txt / .srt / .docx output |
| `app/static/index.html` | The interface |
| `Desinstalar Transcritor.command` | Removes the app and model (keeps transcripts) |

Requires macOS 13.5+ on Apple Silicon, or macOS 11+ on Intel.
