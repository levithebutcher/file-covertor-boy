"""
Script to generate a prefilled Google Colab runner notebook from local .env.
The generated notebook (Colab_Runner.ipynb) is git-ignored and safe to run locally.
"""

import json
from pathlib import Path
from dotenv import dotenv_values

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
OUTPUT_NB_PATH = PROJECT_ROOT / "Colab_Runner.ipynb"


def generate_colab_notebook():
    if not ENV_PATH.exists():
        print("❌ Error: .env file not found in project root.")
        return

    config = dotenv_values(ENV_PATH)
    bot_token = config.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
    api_id = config.get("API_ID", "YOUR_API_ID_HERE")
    api_hash = config.get("API_HASH", "YOUR_API_HASH_HERE")
    owner_id = config.get("OWNER_ID", "8942914752")

    nb_data = {
        "cells": [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    "# 🚀 Telegram Media Suite — Google Colab Engine (Prefilled)\n",
                    "\n",
                    "This notebook is pre-configured with your credentials to run the **Telegram Media Suite** on Google Colab.\n",
                    "\n",
                    "> **⚠️ Important:**\n",
                    "> - Keep this browser tab open while the bot is running.\n",
                    "> - Colab free runtime gives up to 12 hours of processing per session."
                ]
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "# 1. Install system tools (FFmpeg, unar, 7-Zip, libarchive)\n",
                    "!apt-get update -qq\n",
                    "!apt-get install -y -qq ffmpeg p7zip-full unar libarchive-tools curl"
                ]
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "# 2. Clone repository & install dependencies\n",
                    "import os\n",
                    "REPO_URL = \"https://github.com/levithebutcher/file-covertor-boy.git\"\n",
                    "REPO_DIR = \"file-covertor-boy\"\n",
                    "\n",
                    "if not os.path.exists(REPO_DIR):\n",
                    "    !git clone {REPO_URL}\n",
                    "    %cd {REPO_DIR}\n",
                    "else:\n",
                    "    %cd {REPO_DIR}\n",
                    "    !git pull origin main\n",
                    "\n",
                    "!pip install -q -r requirements.txt"
                ]
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "# 3. Write prefilled .env with your credentials\n",
                    f"BOT_TOKEN = {json.dumps(bot_token)}\n",
                    f"API_ID = {json.dumps(api_id)}\n",
                    f"API_HASH = {json.dumps(api_hash)}\n",
                    f"OWNER_ID = {json.dumps(owner_id)}\n",
                    "\n",
                    "with open(\".env\", \"w\", encoding=\"utf-8\") as f:\n",
                    "    f.write(f\"BOT_TOKEN={BOT_TOKEN}\\n\")\n",
                    "    f.write(f\"API_ID={API_ID}\\n\")\n",
                    "    f.write(f\"API_HASH={API_HASH}\\n\")\n",
                    "    f.write(f\"OWNER_ID={OWNER_ID}\\n\")\n",
                    "    f.write(f\"ADMIN_IDS={OWNER_ID}\\n\")\n",
                    "    f.write(\"PORT=10000\\n\")\n",
                    "    f.write(\"MAX_CONCURRENT_JOBS=2\\n\")\n",
                    "\n",
                    "print(\"✅ Credentials and OWNER_ID configured for owner:\", OWNER_ID)"
                ]
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "# 4. Launch Bot\n",
                    "!python run.py"
                ]
            }
        ],
        "metadata": {
            "language_info": {
                "name": "python"
            }
        },
        "nbformat": 4,
        "nbformat_minor": 2
    }

    with open(OUTPUT_NB_PATH, "w", encoding="utf-8") as f:
        json.dump(nb_data, f, indent=2)

    print(f"[SUCCESS] Generated prefilled notebook: {OUTPUT_NB_PATH.name}")
    print("[INFO] Upload this file to https://colab.research.google.com and click 'Run all'!")


if __name__ == "__main__":
    generate_colab_notebook()
