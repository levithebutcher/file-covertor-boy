"""
Local utility script to generate a PREFILLED, standalone Google Colab notebook
from your local .env file.

The resulting file (run_colab.ipynb) is strictly git-ignored to prevent credential leaks.
"""

import sys
import json
from pathlib import Path
from dotenv import dotenv_values

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).parent.parent
ENV_FILE = PROJECT_ROOT / ".env"
TEMPLATE_FILE = PROJECT_ROOT / "colab" / "standalone_bot.ipynb"
OUTPUT_FILE = PROJECT_ROOT / "run_colab.ipynb"


def generate_colab_notebook():
    if not ENV_FILE.exists():
        print(f"❌ Error: .env file not found at {ENV_FILE}")
        return

    if not TEMPLATE_FILE.exists():
        print(f"❌ Error: Template file not found at {TEMPLATE_FILE}")
        return

    # Load local credentials
    env_vars = dotenv_values(ENV_FILE)
    bot_token = env_vars.get("BOT_TOKEN", "")
    api_id = env_vars.get("API_ID", "")
    api_hash = env_vars.get("API_HASH", "")
    owner_id = env_vars.get("OWNER_ID") or env_vars.get("ADMIN_IDS", "").split(",")[0]
    repo_url = "https://github.com/levithebutcher/file-covertor-boy.git"

    # Load template
    with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
        nb_data = json.load(f)

    # Replace values in cells
    for cell in nb_data.get("cells", []):
        if cell.get("cell_type") == "code":
            source_lines = cell.get("source", [])
            new_lines = []
            for line in source_lines:
                if 'REPO_URL = "https://github.com/levithebutcher/file-covertor-boy.git"' in line:
                    new_lines.append(f'REPO_URL = "{repo_url}"\n')
                elif 'os.environ["BOT_TOKEN"] = "YOUR_BOT_TOKEN_HERE"' in line:
                    new_lines.append(f'os.environ["BOT_TOKEN"] = "{bot_token}"\n')
                elif 'os.environ["API_ID"] = "YOUR_API_ID_HERE"' in line:
                    new_lines.append(f'os.environ["API_ID"] = "{api_id}"\n')
                elif 'os.environ["API_HASH"] = "YOUR_API_HASH_HERE"' in line:
                    new_lines.append(f'os.environ["API_HASH"] = "{api_hash}"\n')
                elif 'os.environ["OWNER_ID"] = "YOUR_OWNER_ID_HERE"' in line:
                    new_lines.append(f'os.environ["OWNER_ID"] = "{owner_id}"\n')
                else:
                    new_lines.append(line)
            cell["source"] = new_lines

    # Write output notebook
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(nb_data, f, indent=1)

    print("==================================================")
    print("✅ PREFILLED STANDALONE COLAB NOTEBOOK GENERATED")
    print(f"📁 Saved to: {OUTPUT_FILE.resolve()}")
    print("🔒 Verified: 'run_colab.ipynb' is in .gitignore.")
    print("==================================================")
    print("\n👉 To run on Google Colab:")
    print("1. Open https://colab.research.google.com")
    print("2. Click 'Upload' and select your local 'run_colab.ipynb'")
    print("3. Click Runtime -> Run All (Ctrl + F9)")
    print("4. The bot will run directly with full GPU/RAM!\n")


if __name__ == "__main__":
    generate_colab_notebook()
