# 🎬 Telegram Media Suite — High-Performance Automation Bot

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.14-blue?logo=python)](https://python.org)
[![MTProto](https://img.shields.io/badge/Framework-Hydrogram%20v0.2.0-blueviolet?logo=telegram)](https://github.com/hydrogram/hydrogram)
[![FFmpeg](https://img.shields.io/badge/Engine-FFmpeg-green?logo=ffmpeg)](https://ffmpeg.org)
[![7-Zip](https://img.shields.io/badge/Archives-7--Zip%20%7C%20unar-orange)](https://7-zip.org)
[![Platform](https://img.shields.io/badge/Platform-Google%20Colab%20%7C%20Render-red?logo=googlecolab)](https://colab.research.google.com)
[![License](https://img.shields.io/badge/License-MIT-lightgrey)](LICENSE)

**An asynchronous Telegram bot for Video Conversion, Split & URL Archive Extraction, and Multi-File Bundling.**  
*Runs with high-speed bandwidth and hardware acceleration on Google Colab or standalone on Render / VPS with zero external database dependencies.*

</div>

---

## 🌟 Key Features

| Feature | Capabilities & Architecture |
| :--- | :--- |
| **🎬 Video Converter** | Converts any popular video format (`.mkv`, `.avi`, `.mov`, `.webm`, `.flv`, `.wmv`, `.ts`, `.3gp`, `.mpg`, etc.) to streamable `.mp4` (H.264/AAC). Features **instant stream copy** when streams are already compatible, multi-threaded CPU encoding (`-threads 0`, `-preset veryfast -crf 23`), automatic silent audio track synthesis for player controls, high-resolution thumbnail extraction, and live throttled progress. |
| **📦 Unzipper (URL & Split Engine)** | Extracts `.zip`, `.rar`, `.7z`, `.tar`, `.gz`, `.tgz`, `.tar.bz2`, `.cbr`, `.cbz` archives through a multi-backend pipeline (`7z`, `unar`, `unrar`, `bsdtar/tar`, `py7zr`, `rarfile`). Delivers photos and videos in native **Telegram Media Albums** (up to 10 per album) with clean document fallback. |
| **🌐 Direct URL Unzipper** | Paste any direct download link (`https://...`, Google Drive, Mediafire, etc.) in Unzipper mode. The bot stream-downloads the archive directly from the web to Colab/Server, **completely bypassing Telegram's 2 GB file download restrictions**. |
| **🧩 Split Archive Collector (`/merge`)** | Send multi-part archive volumes (`.7z.001`, `.7z.002`, or `.part1.rar`, `.part2.rar`). The bot stages all parts in an isolated directory and unpacks the complete volume set together with one tap on **[🚀 Extract All Parts]** (or `/done`). |
| **⚡ Auto-Split for Extracted Files > 2 GB** | If an extracted file inside an archive exceeds Telegram's 2 GB upload limit, the bot **automatically splits it into 1.9 GB zip pieces** (`.zip.001`, `.zip.002`) and uploads all parts sequentially so you **never lose large files**. |
| **🗜️ Zipper (Multi-File Bundler)** | Multi-file staging batch collector. Send multiple documents, photos, or videos, view live batch counts and size, and package them into a `.zip`. If the output archive exceeds 2 GB, it automatically creates split zip volumes. |
| **⚙️ Interactive Mode Switcher** | Modern glassmorphic `/mode` control center with dynamic checkmarks (`[ 🎬 Video Converter ✅ ]`), instant in-place button updates (zero spam), and direct shortcuts (`/convert`, `/unzip`, `/zip`). |
| **💾 Zero-Config Database** | Built-in local SQLite in WAL mode. Persistent, instantaneous (< 1ms), and eliminates all external connection timeouts and MongoDB Atlas cluster requirements. |
| **🔒 Enterprise Security** | Strict owner whitelist access control (`/adduser`, `/removeuser`, `/users`), parameter-list subprocess execution (zero shell injection), and automated pre-commit secret scanning. |

---

## 🤖 Available Bot Commands

| Command | Description |
| :--- | :--- |
| `/start` | Open welcome screen and view current active mode |
| `/mode` | Interactive inline keyboard mode switcher |
| `/convert` | Shortcut: Switch immediately to Video Converter Mode |
| `/unzip` | Shortcut: Switch immediately to Unzipper Mode |
| `/zip` | Shortcut: Switch immediately to Zipper Mode |
| `/merge` or `/parts` | Open the Split Archive Collector to stage multi-part volumes |
| `/done` or `/finish` | Finish and package current staging batch (Zipper or Split Archive) |
| `/clear` | Clear all active staging queues |
| `/adduser <id>` | *(Owner only)* Authorize a user ID to access the bot |
| `/removeuser <id>` | *(Owner only)* Revoke authorization from a user ID |
| `/users` | *(Owner only)* List all authorized users |
| `/stats` | View active hardware, disk, RAM, and process metrics |

---

## 🚀 Deployment Guide

### Option 1: Google Colab (Recommended for Unlimited Speed & 100 GB Disk)

Google Colab provides high-speed bandwidth (1 Gbps) and 100+ GB of temporary disk space, making it ideal for processing multi-gigabyte videos and archives.

1. **One-Click Pre-Configured Notebook:**
   - Run the local notebook generator on your machine:
     ```bash
     python scripts/generate_colab_notebook.py
     ```
   - This creates `Colab_Runner.ipynb` prefilled with your credentials (protected by `.gitignore`).
2. **Open in Google Colab:**
   - Go to [Google Colab](https://colab.research.google.com/) and click **Upload Notebook**.
   - Select `Colab_Runner.ipynb` (or `colab_template.ipynb`).
   - In the Colab menu, click **Runtime ➔ Run all**.
   - The bot starts instantly and stays actively connected to Telegram.

---

### Option 2: Local Installation

```bash
# 1. Clone repository
git clone https://github.com/levithebutcher/file-covertor-boy.git
cd file-covertor-boy

# 2. Setup virtual environment
python -m venv .venv
source .venv/bin/activate   # On Linux/macOS
# .\.venv\Scripts\activate  # On Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure .env
cp .env.example .env
# Fill in your BOT_TOKEN, API_ID, API_HASH, and OWNER_ID

# 5. Run tests
pytest tests/

# 6. Start the bot
python run.py
```

---

### Option 3: Docker / Render Web Service

The repository includes a production `Dockerfile` with FFmpeg, 7-Zip, unar, and bsdtar pre-installed:

```bash
docker build -t telegram-media-suite .
docker run -d --env-file .env -p 10000:10000 --name media-bot telegram-media-suite
```

---

## 🛡️ Security & Secret Scanning

Before committing or pushing any code, verify that no tokens, credentials, or private session files are staged:

```bash
python scripts/secret_scan.py
```

---

## 💖 Credits & Acknowledgments

This project stands on the shoulders of the open-source community. Special thanks and attribution to:

- **[EDM115/unzip-bot](https://github.com/EDM115/unzip-bot)** & **[Itz-fork/Unzipper-Bot](https://github.com/Itz-fork/Unzipper-Bot)**: For pioneering ideas on multi-part split archive merging (`/merge`), direct URL download patterns, and multi-volume archive splitting.
- **[Hydrogram](https://github.com/hydrogram/hydrogram)** & **[Pyrogram](https://github.com/pyrogram/pyrogram)**: For the asynchronous Telegram MTProto client framework supporting native 2 GB file operations.
- **[FFmpeg Team](https://ffmpeg.org)**: For the multimedia transcoding and streaming framework.
- **[7-Zip (Igor Pavlov)](https://7-zip.org)**: For high-speed multi-format compression and split volume creation.
- **[The Unarchiver (`unar`) by Dag Ågren / MacPaw](https://theunarchiver.com/command-line)**: For universal command-line extraction of modern RAR (v1–v5) and legacy archives.
- **[libarchive (`bsdtar`)](https://www.libarchive.org/)**: For cross-platform multi-format archive decompression.
- **[py7zr (Miurahr)](https://github.com/miurahr/py7zr)** & **[rarfile (Marko Kreen)](https://github.com/markokr/rarfile)**: For robust Python archive extraction bindings.
- **[aiohttp](https://github.com/aio-libs/aiohttp)** & **[aiosqlite](https://github.com/omnilib/aiosqlite)**: For asynchronous HTTP streaming and standalone SQLite database storage.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
