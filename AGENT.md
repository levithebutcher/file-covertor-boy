# AGENT HANDOVER MANUAL: TELEGRAM MEDIA SUITE

> **Target Audience:** Any AI coding assistant or human DevOps engineer continuing development or maintenance on this codebase.  
> **Status:** Production-Ready (Standalone Render Web Service with Local SQLite, Zero External DB Dependencies).  
> **Last Updated:** October 2026

---

## 1. Project Goal & Overview

Telegram Media Suite is a high-performance, asynchronous Telegram bot built with Python 3.11+ and Hydrogram (MTProto). It provides three core media services up to Telegram's 2 GB non-premium limit:

1. **🎬 Video Converter (Top Priority):** Converts all popular video containers (`.mkv`, `.avi`, `.mov`, `.webm`, `.flv`, `.wmv`, `.ts`, etc.) into streamable, web-optimized `.mp4` (H.264/AAC) using asynchronous FFmpeg subprocesses with real-time stdout progress parsing and instant cancellation.
2. **📦 Unzipper (Top Priority):** Extracts `.zip`, `.rar`, `.7z`, `.tar`, `.gz`, `.tgz`, `.tar.bz2` archives using `7z` (with Python library fallbacks), delivers photos/videos in standardized Telegram albums, handles password protection, and uploads valid files sequentially with flood throttling.
3. **🗜️ Zipper (Multi-File Bundler):** Staged collector allowing users to send multiple files, visualize batch counts in real time, and trigger compression into `.zip`. Automatically splits archives into multi-part volumes if total size exceeds 2 GB.
4. **🎭 Casual Text Humor:** Non-veg / adult humor auto-replies to random conversational messages ("hi", "hlw", etc.).

---

## 2. Key Architectural Decisions & Rationale

| Decision | Choice | Rationale |
| :--- | :--- | :--- |
| **MTProto Library** | **Hydrogram** (v0.2.0) | Active community continuation of Pyrogram with support for Python 3.11–3.14+, modern Telegram DC layers, and native 2 GB MTProto uploads. |
| **Database** | **Local SQLite (WAL Mode)** | Completely standalone, persistent, zero-network, and lightning fast. Eliminates external MongoDB Atlas connection latency, DNS SRV errors, and network timeouts. |
| **Primary Host** | **Render Free Web Service** | Bound to HTTP port 10000 instantly (< 50ms) on startup to satisfy Render health checks and external cron keep-alive pingers without timing out. |
| **Standalone Colab Option** | **`run_colab.ipynb`** | Standalone Jupyter notebook generated locally on device for running the bot directly on Google Colab with free GPU/RAM if desired. Zero handoff code clutter in the bot repo. |
| **Subprocess Execution** | `create_subprocess_exec` | Avoids shell string interpolation (`shell=True`). All arguments passed as structured lists with sanitized filenames to prevent shell command injection. |
| **Progress Updates** | **Throttled Reporter (4.5s)** | Telegram restricts message edits (`FloodWait: 429`). The `ProgressReporter` throttles live progress edits to once every 4.5 seconds per task, displays a visual bar (`■■■■□□□□`), ETA, speed, and attaches a live Cancel button. |

---

## 3. Repository & Folder Map

```
covertor/
├── .env.example                  # Reference environment configuration
├── .gitignore                    # Secrets, sessions, databases, virtualenvs, temp
├── Dockerfile                    # Production Docker container with FFmpeg & 7z (non-root)
├── render.yaml                   # Render Blueprint for automated deployment
├── requirements.txt              # Pinned production Python dependencies
├── RESEARCH.md                   # Benchmark report of open-source bots analyzed
├── AGENT.md                      # This handover documentation
├── README.md                     # User-facing guide & setup instructions
│
├── bot/                          # Core Application Package
│   ├── __init__.py
│   ├── __main__.py               # Standalone application entrypoint
│   ├── config.py                 # Pydantic BaseSettings & env parsing
│   │
│   ├── core/                     # Networking & Infrastructure
│   │   ├── client.py             # Hydrogram Client instance (Lazy Proxy)
│   │   └── web_server.py         # aiohttp /health endpoint on PORT 10000
│   │
│   ├── database/                 # Local SQLite Persistence Layer
│   │   ├── __init__.py
│   │   ├── db.py                 # Thread-safe SQLite engine in WAL mode
│   │   └── users.py              # Whitelist queries & per-user mode state
│   │
│   ├── handlers/                 # Telegram Event Handlers
│   │   ├── __init__.py
│   │   ├── admin.py              # /adduser, /removeuser, /users, /stats (Owner-only)
│   │   ├── mode.py               # /mode, /convert, /unzip, /zip & inline callbacks
│   │   ├── media.py              # Video conversion, unzipping, and zipper dispatcher
│   │   ├── chat.py               # Conversational text humor handler
│   │   └── callbacks.py          # Cancel button, zipper finish/clear, close menu
│   │
│   ├── services/                 # Core Business Processing Engines
│   │   ├── __init__.py
│   │   ├── converter.py          # FFmpeg video transcode, stream copy, progress parsing
│   │   ├── unzipper.py           # 7z extraction, album packaging, 2GB size check
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
│   └── standalone_bot.ipynb      # Standalone Colab notebook template
│
├── scripts/
│   ├── generate_colab.py         # Generates local prefilled ready-to-run run_colab.ipynb
│   └── secret_scan.py            # Pre-commit secret scanning validation script
│
└── tests/                        # Automated Unit Tests (pytest)
    ├── test_database.py          # SQLite whitelist & mode switching tests
    ├── test_file_ops.py          # Sanitization, path traversal, byte formatting tests
    ├── test_jokes_zipper.py      # Humor & zipper workflow tests
    ├── test_media_routing.py     # Video & archive format detection tests
    └── test_unzipper.py          # Album classification & password detection tests
```

---

## 4. Configuration / Environment Variables Reference

| Variable | Required | Description | Example |
| :--- | :---: | :--- | :--- |
| `BOT_TOKEN` | Yes | Telegram Bot Token from @BotFather | `123456:ABC-DEF...` |
| `API_ID` | Yes | Telegram API ID from my.telegram.org | `1234567` |
| `API_HASH` | Yes | Telegram API Hash from my.telegram.org | `abcdef012345...` |
| `OWNER_ID` | Yes | Primary Telegram user ID of the owner | `123456789` |
| `ADMIN_IDS` | No | Additional comma-separated admin IDs | `12345,67890` |
| `PORT` | No | HTTP Port for Render health check (Default: 10000) | `10000` |
| `MAX_CONCURRENT_JOBS` | No | Max active jobs on this node (Default: 1 for Render) | `1` |

---

## 5. Security Rules for Future AI Developers

1. **NEVER hardcode credentials:** Always retrieve credentials via `bot.config.settings`.
2. **NEVER print secrets in logs:** No tokens, API hashes, or passwords in exceptions or logs.
3. **No Shell Invocations:** Always use `asyncio.create_subprocess_exec(*arg_list)`. Never construct shell commands with `f"ffmpeg -i {filename}"`.
4. **Pre-commit Scan:** Run `python scripts/secret_scan.py` before any commit to verify no secrets are staged.
5. **Preserve .gitignore:** Ensure `.env`, `*.session`, `run_colab.ipynb`, `data/`, and `temp/` are never removed from `.gitignore`.
