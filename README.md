# 🎬 Telegram Media Converter & Archive Suite — Production Bot

> **A fast, high-performance Telegram automation bot built for Video Conversion, Archive Extraction, and Multi-File Archiving.**  
> Completely **standalone**, optimized for **Render Free Tier**, with **zero external database dependencies** (built-in SQLite).

---

## 🌟 Key Features

| Feature | Capabilities |
| :--- | :--- |
| **🎬 Video Converter** | Converts any popular video format (`.mkv`, `.avi`, `.mov`, `.webm`, `.flv`, `.wmv`, `.ts`, `.3gp`, `.mpg`, etc.) to streaming `.mp4` (H.264/AAC). Features smart stream-copy when already compatible, real-time throttled progress updates, thumbnail extraction, and instant cancellation. |
| **📦 Unzipper** | Extracts `.zip`, `.rar`, `.7z`, `.tar`, `.gz`, `.tgz`, `.tar.bz2` archives. Formats extracted media into standardized Telegram albums, handles password protection, skips files > 2 GB with clear user warnings, and streams valid files sequentially with flood protection. |
| **🗜️ Zipper** | Multi-file staging batch collector. Send multiple files, monitor live batch statistics, and package into a `.zip`. Automatically splits archives into multi-part volumes if total size exceeds 2 GB. |
| **⚙️ Interactive Mode Switcher** | Modern glassmorphic `/mode` control center with dynamic checkmarks (`[ 🎬 Video Converter ✅ ]`), instant in-place button updates (zero spam), and direct shortcuts (`/convert`, `/unzip`, `/zip`). |
| **💾 Zero-Config Database** | Built-in local SQLite in WAL mode. Persistent, instantaneous (< 1ms), and eliminates all external connection timeouts and MongoDB Atlas requirements. |
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
   - Go to [dashboard.render.com](https://dashboard.render.com).
   - Create or connect your Web Service pointing to your GitHub repository.
   - Render will build the Docker container and start the web service on port 10000.
3. **Set Environment Variables on Render:**
   - Under Service Settings ➔ Environment, add your `BOT_TOKEN`, `API_ID`, `API_HASH`, and `OWNER_ID`.
4. **Keeping Render Awake (Prevent 15-Minute Idle Sleep):**
   - Render Free spins down after 15 minutes without HTTP requests.
   - Set up an external cron pinger (e.g. [cron-job.org](https://cron-job.org) or UptimeRobot) to send an HTTP GET request to:
     `https://your-service.onrender.com/health`
     every **5 to 10 minutes**.

---

## ⚡ Optional: Run Standalone on Google Colab

If you ever want to run the bot directly on Google Colab with free GPU/high RAM:
1. Generate your prefilled, ready-to-run Colab notebook locally:
   ```bash
   python scripts/generate_colab.py
   ```
   *(This creates `run_colab.ipynb` using your local `.env` — it is strictly git-ignored!)*
2. Open [Google Colab](https://colab.research.google.com).
3. Upload `run_colab.ipynb` and click **Runtime ➔ Run all**.
4. The bot will run standalone on Colab with zero extra setup needed!

---

## 🛡️ Security & Pre-Commit Verification

Before any commit or push, verify that no secrets or sessions are staged:
```bash
python scripts/secret_scan.py
```
