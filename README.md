# ✨ Nexus Media Suite — Production Telegram Bot

> **A premium, high-performance Telegram automation bot built for Video Conversion, Archive Extraction, and Multi-File Archiving.**  
> Optimized for **Render Free Tier (512 MB RAM)** with automated **Google Colab Big-File Handoff** and **MongoDB Atlas** distributed state.

---

## 🌟 Key Features

| Feature | Capabilities |
| :--- | :--- |
| **🎬 Video Converter** | Converts any popular video format (`.mkv`, `.avi`, `.mov`, `.webm`, `.flv`, `.wmv`, `.ts`, `.3gp`, `.mpg`, etc.) to streaming `.mp4` (H.264/AAC). Features smart stream-copy when already compatible, real-time throttled progress updates, thumbnail extraction, and instant cancellation. |
| **📦 Unzipper** | Extracts `.zip`, `.rar`, `.7z`, `.tar`, `.gz`, `.tgz`, `.tar.bz2` archives. Features zip-slip path traversal defense, skips files > 2 GB with clear user warnings without crashing, and streams valid files sequentially with flood protection. |
| **🗜️ Zipper** | Multi-file staging batch collector. Send multiple files, monitor live batch statistics, and package into a `.zip`. Automatically splits archives into multi-part volumes (`.zip.001`, `.zip.002`) if total size exceeds 2 GB. |
| **⚙️ Interactive Mode Switcher** | Modern glassmorphic `/mode` control center with dynamic checkmarks (`[ 🎬 Video Converter ✅ ]`), instant in-place button updates (zero spam), and direct shortcuts (`/convert`, `/unzip`, `/zip`). |
| **☁️ Render + Colab Handoff** | Small files ($\le$ 100 MB) are processed 24/7 on Render Free. Large files (> 100 MB up to 2 GB) are safely queued in MongoDB Atlas for Google Colab processing without crashing Render's 512 MB RAM. |
| **🔒 Enterprise Security** | Strict owner whitelist access control (`/adduser`, `/removeuser`, `/users`), parameter-list subprocess execution (zero shell injection), non-root Docker container, and automated pre-commit secret scanning. |

---

## 🚀 Quick Start (Local Setup)

### 1. Clone & Setup Virtual Environment
```bash
git clone <REPO_URL>
cd covertor

# Create and activate virtual environment
py -m venv .venv
.\.venv\Scripts\activate   # On Windows
# source .venv/bin/activate # On Linux/macOS
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Credentials
Copy `.env.example` to `.env` and fill in your details:
```bash
cp .env.example .env
```
```env
BOT_TOKEN=1234567890:ABCdefGhIJKlmNoPQRsTUVwxyZ
API_ID=1234567
API_HASH=0123456789abcdef0123456789abcdef
OWNER_ID=123456789
MONGO_URI=mongodb+srv://<username>:<password>@cluster0.abcde.mongodb.net/?retryWrites=true&w=majority
```

### 4. Run Automated Test Suite
```bash
pytest tests/
```

### 5. Launch Bot
```bash
python -m bot
```

---

## 🌐 Deployment on Render (Free Tier)

This bot includes a production Dockerfile and `render.yaml` blueprint optimized for Render Free.

1. **Push your code to your private GitHub repository:**
   *(Ensure `.env` is never committed — it is protected by `.gitignore`)*.
2. **Deploy on Render:**
   - Go to [dashboard.render.com](https://dashboard.render.com) ➔ **New +** ➔ **Blueprint**.
   - Connect your GitHub repository.
   - Render will build the Docker container and start the web service on port 10000.
3. **Set Environment Variables on Render:**
   - Under Service Settings ➔ Environment, add your `BOT_TOKEN`, `API_ID`, `API_HASH`, `OWNER_ID`, and `MONGO_URI`.
4. **Keeping Render Awake (Prevent 15-Minute Idle Sleep):**
   - Render Free spins down after 15 minutes without HTTP requests.
   - Set up an external cron pinger (e.g. [cron-job.org](https://cron-job.org) or UptimeRobot) to send an HTTP GET request to:
     `https://your-service.onrender.com/health`
     every **10 minutes**.

---

## ⚡ Google Colab Worker (Processing Big Files > 100 MB)

When a large video or archive arrives on Render, the bot queues the job in MongoDB and notifies you:

1. Generate your prefilled, ready-to-run Colab notebook locally:
   ```bash
   python scripts/generate_colab.py
   ```
   *(This creates `run_colab.ipynb` using your local `.env` — it is strictly git-ignored!)*
2. Open [Google Colab](https://colab.research.google.com).
3. Upload `run_colab.ipynb` and click **Runtime ➔ Run all**.
4. The Colab node claims the MongoDB master lock, Render pauses its Telegram client automatically, and Colab processes all queued files using its 12 GB RAM and high-speed CPU.
5. When finished, interrupt or close Colab. Render detects the release and resumes 24/7 monitoring automatically!

---

## 🛡️ Security & Pre-Commit Verification

Verify no sensitive credentials or tokens are staged before pushing to git:
```bash
python scripts/secret_scan.py
```

---

## 📜 Credits & Attribution

This project incorporates battle-tested architectural patterns from top open-source Telegram bots:
- **[mirror-leech-telegram-bot](https://github.com/anasty17/mirror-leech-telegram-bot)** (Anas Tayyar) — Real-time FFmpeg pipe parsing, 7z stdout streaming, and Telegram FloodWait management.
- **[unzip-bot](https://github.com/EDM115/unzip-bot)** (EDM115) — Comprehensive archive extraction and 2 GB threshold protections.
- **[Telegram-Leecher](https://github.com/XronTrix10/Telegram-Leecher)** (XronTrix10) — Multi-part volume splitting concepts and Colab execution patterns.
- **[Hydrogram](https://github.com/hydrogram/hydrogram)** — Modern asynchronous MTProto framework.

**License:** GNU General Public License v3.0 (GPLv3)
