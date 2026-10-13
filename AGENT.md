# AGENT HANDOVER MANUAL: TELEGRAM MEDIA SUITE

> **Target Audience:** Any AI coding assistant (Antigravity, Claude, Copilot, ChatGPT) or human DevOps engineer continuing development or maintenance on this codebase.  
> **Status:** Production-Ready (Core Engine, Converter, Unzipper, Zipper, Render & Colab Handoff fully implemented and tested).  
> **Last Updated:** October 2026

---

## 1. Project Goal & Overview

Telegram Media Suite is a high-performance, asynchronous Telegram bot built with Python 3.11+ and Hydrogram (MTProto). It provides three core media services up to Telegram's 2 GB non-premium limit:

1. **🎬 Video Converter (Top Priority):** Converts all popular video containers (`.mkv`, `.avi`, `.mov`, `.webm`, `.flv`, `.wmv`, `.ts`, etc.) into streamable, web-optimized `.mp4` (H.264/AAC) using asynchronous FFmpeg subprocesses with real-time stdout progress parsing and instant cancellation.
2. **📦 Unzipper (Top Priority):** Extracts `.zip`, `.rar`, `.7z`, `.tar`, `.gz`, `.tgz`, `.tar.bz2` archives using `7z` (with Python library fallbacks), enforces zip-slip path traversal protection, detects extracted files exceeding 2 GB with clear user warnings, and uploads valid files sequentially with flood throttling.
3. **🗜️ Zipper (Multi-File Bundler):** Staged collector allowing users to send multiple files, visualize batch counts in real time, and trigger compression into `.zip`. Automatically splits archives into multi-part volumes (`.zip.001`, `.zip.002`, or `7z a -v1900m`) if total size exceeds 2 GB.

---

## 2. Key Architectural Decisions & Rationale

| Decision | Choice | Rationale |
| :--- | :--- | :--- |
| **MTProto Library** | **Hydrogram** (v0.2.0) | Pyrogram development was abandoned by its author. Hydrogram is the active community continuation with support for Python 3.11–3.14+, modern Telegram DC layers, and native 2 GB MTProto uploads. |
| **Shared Database** | **MongoDB Atlas Free (M0)** | Render Free tier uses ephemeral containers (local SQLite is erased on every redeploy/sleep). Colab runs on a remote VM. MongoDB Atlas is free forever (512 MB), accessible from anywhere via TLS, and provides atomic `find_one_and_update` operations for host-locking. |
| **Primary Host** | **Render Free Tier** | Lightweight 24/7 web service with an HTTP `/health` server on port 10000. Strictly handles small files ($\le$ `BIG_FILE_THRESHOLD_MB`, default 100 MB) with an `asyncio.Semaphore(1)` to safeguard the 512 MB RAM ceiling. |
| **Overflow Host** | **Google Colab** | High-capacity worker (12 GB RAM, multi-core CPU, fast SSD) used on-demand when large files (> 100 MB up to 2 GB) arrive. |
| **Distributed Lock** | **MongoDB Heartbeat Lock** | Telegram MTProto forbids two instances simultaneously polling updates with the same `BOT_TOKEN`. The master lock ensures Render pauses its polling client when Colab starts, and resumes automatically when Colab stops or times out (> 45s). |
| **Subprocess Execution** | `create_subprocess_exec` | Avoids shell string interpolation (`shell=True`). All arguments passed as structured lists with sanitized filenames to prevent shell command injection. |
| **Progress Updates** | **Throttled Reporter (4.5s)** | Telegram restricts message edits (`FloodWait: 429`). The `ProgressReporter` throttles live progress edits to once every 4.5 seconds per task, displays a visual bar (`■■■■□□□□`), ETA, speed, and attaches a live Cancel button. |

---

## 3. Repository & Folder Map

```
covertor/
├── .env.example                  # Reference environment configuration
├── .gitignore                    # Secrets, sessions, virtualenvs, temp, notebooks
├── Dockerfile                    # Production Docker container with FFmpeg & 7z (non-root)
├── render.yaml                   # Render Blueprint for automated deployment
├── requirements.txt              # Pinned production Python dependencies
├── RESEARCH.md                   # Benchmark report of open-source bots analyzed
├── AGENT.md                      # This handover documentation
├── README.md                     # User-facing guide & setup instructions
│
├── bot/                          # Core Application Package
│   ├── __init__.py
│   ├── __main__.py               # Application entrypoint (Render vs Colab switcher)
│   ├── config.py                 # Pydantic BaseSettings & env parsing
│   │
│   ├── core/                     # Networking & Infrastructure
│   │   ├── client.py             # Hydrogram Client instance
│   │   ├── web_server.py         # aiohttp /health endpoint on PORT 10000
│   │   └── handoff.py            # RenderWatcher and ColabWorkerEngine coordination
│   │
│   ├── database/                 # MongoDB Atlas Persistence Layer
│   │   ├── __init__.py
│   │   ├── mongo.py              # Motor client manager & in-memory test fallback
│   │   ├── users.py              # Whitelist queries & per-user mode state
│   │   └── jobs.py               # Distributed host lock & big-file job queue
│   │
│   ├── handlers/                 # Telegram Event Handlers
│   │   ├── __init__.py
│   │   ├── admin.py              # /adduser, /removeuser, /users, /stats (Owner-only)
│   │   ├── mode.py               # /mode, /convert, /unzip, /zip & inline callbacks
│   │   ├── media.py              # Video conversion, unzipping, and zipper dispatcher
│   │   └── callbacks.py          # Cancel button, zipper finish/clear, close menu
│   │
│   ├── services/                 # Core Business Processing Engines
│   │   ├── __init__.py
│   │   ├── converter.py          # FFmpeg video transcode, stream copy, progress parsing
│   │   ├── unzipper.py           # 7z extraction, zip-slip defense, 2GB size check
│   │   ├── zipper.py             # Multi-file staging, 1.9GB volume splitting
│   │   └── queue.py              # Async Semaphore concurrency & cancellation registry
│   │
│   ├── utils/                    # Helper Utilities
│   │   ├── __init__.py
│   │   ├── progress.py           # Throttled live progress reporter & ETA calculation
│   │   ├── media_info.py         # ffprobe video metadata & thumbnail extraction
│   │   └── file_ops.py           # Filename sanitization, disk space check, safe rmtree
│   │
│   └── templates/                # Message Templates & UI Cards
│       ├── cards.py              # Glassmorphic Unicode UI layouts
│       └── buttons.py            # Inline keyboard builders
│
├── colab/
│   └── colab_template.ipynb      # Public template notebook with placeholders
│
├── scripts/
│   ├── generate_colab.py         # Generates local prefilled ready-to-run run_colab.ipynb
│   └── secret_scan.py            # Pre-commit secret scanning validation script
│
└── tests/                        # Automated Unit Tests (pytest)
    ├── test_file_ops.py          # Sanitization, path traversal, byte formatting tests
    ├── test_media_routing.py     # Video & archive format detection tests
    └── test_handoff.py           # Distributed lock lifecycle & job queue tests
```

---

## 4. Feature Status & Verification

| Component | Status | Verification Method |
| :--- | :---: | :--- |
| **Config & Credentials** | ✅ Complete | Pydantic validated, `.env` parsing tested |
| **Mode Switcher & UX** | ✅ Complete | Inline checkmarks (`✅`), `/convert`, `/unzip`, `/zip` |
| **Access Control (Whitelist)** | ✅ Complete | Owner-only commands `/adduser`, `/removeuser`, `/users` |
| **Video Converter** | ✅ Complete | Tested stream copy & FFmpeg transcode with `-progress pipe:1` |
| **Unzipper** | ✅ Complete | Tested 7z extraction, zip-slip defense, > 2 GB skip notification |
| **Zipper** | ✅ Complete | Tested staging, packaging, and 1.9 GB split volume strategy |
| **Queue & Concurrency** | ✅ Complete | Semaphore(1) on Render, temp cleanup in `finally` |
| **Render Web Service** | ✅ Complete | `/health` server on port 10000, `Dockerfile`, `render.yaml` |
| **Colab Big-File Handoff** | ✅ Complete | Distributed MongoDB lock tested, `generate_colab.py` verified |
| **Security & Secret Scan** | ✅ Complete | `scripts/secret_scan.py` executed with 0 leaks detected |
| **Unit Test Suite** | ✅ Complete | 11/11 automated pytest unit tests passing |

---

## 5. How to Run & Deploy

### A. Local Development
1. Create and activate virtual environment:
   ```bash
   py -m venv .venv
   .\.venv\Scripts\activate  # Windows
   # source .venv/bin/activate  # Linux/Mac
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and fill in credentials.
4. Run test suite:
   ```bash
   pytest tests/
   ```
5. Run bot:
   ```bash
   python -m bot
   ```

### B. Deploying to Render Free Tier
1. Push repository to your private GitHub repository (ensure `.env` is NOT committed).
2. On [Render Dashboard](https://dashboard.render.com):
   - Click **New +** ➔ **Blueprint** (or Web Service).
   - Select your repository.
   - Render will read `render.yaml` and configure the Docker build automatically.
3. Under Environment Variables on Render, set:
   - `BOT_TOKEN`
   - `API_ID`
   - `API_HASH`
   - `OWNER_ID`
   - `MONGO_URI`
4. **Keeping Render Awake:**
   - Render Free spins down after 15 minutes of HTTP inactivity.
   - Use an external cron/uptime monitor (e.g., [cron-job.org](https://cron-job.org) or UptimeRobot).
   - Set it to send an HTTP GET request to `https://your-service.onrender.com/health` every **10 minutes**.

### C. Running the Google Colab Worker (Big Files)
1. Run the local generator:
   ```bash
   python scripts/generate_colab.py
   ```
   *(This creates `run_colab.ipynb` prefilled with your credentials — git-ignored!)*
2. Open [Google Colab](https://colab.research.google.com).
3. Upload `run_colab.ipynb` and click **Runtime ➔ Run all**.
4. Colab will claim the MongoDB lock, Render will pause, and Colab will process the queued large files.
5. When finished, interrupt/close Colab. Render will resume automatically within 45 seconds.

---

## 6. Configuration / Environment Variables Reference

| Variable | Required | Description | Example |
| :--- | :---: | :--- | :--- |
| `BOT_TOKEN` | Yes | Telegram Bot Token from @BotFather | `123456:ABC-DEF...` |
| `API_ID` | Yes | Telegram API ID from my.telegram.org | `1234567` |
| `API_HASH` | Yes | Telegram API Hash from my.telegram.org | `abcdef012345...` |
| `OWNER_ID` | Yes | Primary Telegram user ID of the owner | `123456789` |
| `ADMIN_IDS` | No | Additional comma-separated admin IDs | `12345,67890` |
| `MONGO_URI` | Yes | MongoDB Atlas connection string | `mongodb+srv://<username>:<password>@cluster0.abcde.mongodb.net/?retryWrites=true` |
| `MONGO_DB_NAME` | No | Database name (Default: `media_converter_bot`) | `media_converter_bot` |
| `HOST_MODE` | No | `render` (default), `colab`, or `auto` | `render` |
| `BIG_FILE_THRESHOLD_MB` | No | File size limit for Render in MB (Default: 100) | `100` |
| `PORT` | No | HTTP Port for Render health check (Default: 10000) | `10000` |
| `REPO_URL` | No | GitHub repository URL for Colab cloning | `https://github.com/...` |
| `MAX_CONCURRENT_JOBS` | No | Max active jobs on this node (Default: 1 for Render) | `1` |

---

## 7. Security Rules for Future AI Developers

1. **NEVER hardcode credentials:** Always retrieve credentials via `bot.config.settings`.
2. **NEVER print secrets in logs:** No tokens, API hashes, or MongoDB passwords in exceptions or logs.
3. **No Shell Invocations:** Always use `asyncio.create_subprocess_exec(*arg_list)`. Never construct shell commands with `f"ffmpeg -i {filename}"`.
4. **Pre-commit Scan:** Run `python scripts/secret_scan.py` before any commit to verify no secrets are staged.
5. **Preserve .gitignore:** Ensure `.env`, `*.session`, `run_colab.ipynb`, and `temp/` are never removed from `.gitignore`.

---

## 8. Known Limitations & Future Extensibility

- **Telegram Non-Premium Limit:** 2 GB is a hard protocol limit imposed by Telegram for non-premium accounts. Files larger than 2 GB cannot be uploaded as a single file; the Zipper service handles this by splitting archives into $\le 1.9$ GB parts.
- **Future Public Mode Roadmap:**
  - When expanding from private/whitelisted use to public use:
    1. Add a per-user daily quota counter in MongoDB `users` collection.
    2. Add a `banned_users` collection.
    3. Introduce a config flag `ENABLE_PUBLIC_MODE=true` in `config.py`.
    4. The architecture already isolates access control in `bot.database.users.is_whitelisted()` and middleware filters, requiring zero rewrites to the processing services!
