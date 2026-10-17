"""
Automated secret scan script for pre-commit verification.
Scans staged or tracked files for leaked API keys, tokens, sessions, or credentials.
"""

import os
import re
import sys
import subprocess
from pathlib import Path

# Ensure UTF-8 output on all shells including Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# High-risk patterns
SECRET_PATTERNS = [
    (r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b", "Telegram Bot Token"),
    (r"mongodb(\+srv)?:\/\/[A-Za-z0-9_\-\.]+:[^@\s]+@[A-Za-z0-9_\-\.]+", "MongoDB Atlas Connection with Password"),
    (r"-----BEGIN (RSA|OPENSSH|EC|DSA)? PRIVATE KEY-----", "Cryptographic Private Key"),
    (r'(?i)(api_hash|api_key|secret)\s*[:=]\s*["\'][0-9a-f]{32}["\']', "Exposed API Hash / Key"),
]

BLOCKED_FILES = [
    ".env",
]

BLOCKED_EXTENSIONS = [
    ".session",
    ".session-journal",
]


def run_secret_scan():
    print("🔍 [SECRET SCAN] Checking repository for exposed credentials...")
    repo_root = Path(__file__).parent.parent
    violations = []

    # Get git tracked or modified files
    try:
        res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
        git_lines = res.stdout.strip().splitlines()
    except Exception:
        git_lines = []

    for line in git_lines:
        status = line[:2]
        file_path = line[3:].strip().strip('"')

        # Check blocked files
        base_name = os.path.basename(file_path)
        if base_name in BLOCKED_FILES:
            violations.append(f"❌ Forbidden file staged/untracked in git: {file_path}")

        for ext in BLOCKED_EXTENSIONS:
            if file_path.endswith(ext):
                violations.append(f"❌ Sensitive session file found in git status: {file_path}")

    # Scan content of all tracked Python, Markdown, YAML files (excluding .git and .venv)
    for root, dirs, files in os.walk(repo_root):
        if ".git" in dirs:
            dirs.remove(".git")
        if ".venv" in dirs:
            dirs.remove(".venv")
        if "temp" in dirs:
            dirs.remove("temp")

        for f in files:
            if f.endswith((".py", ".md", ".yaml", ".yml", ".json", ".txt")) and f != ".env.example":
                full_path = Path(root) / f
                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as file_content:
                        for line_idx, line in enumerate(file_content, 1):
                            for pattern, desc in SECRET_PATTERNS:
                                if re.search(pattern, line):
                                    violations.append(
                                        f"❌ Potential {desc} detected at {full_path.relative_to(repo_root)}:line {line_idx}"
                                    )
                except Exception:
                    pass

    if violations:
        print("\n🚨 SECURITY ALERT: Credential leak detected!")
        for v in violations:
            print("  " + v)
        print("\nFix these issues before committing or pushing to GitHub!\n")
        sys.exit(1)
    else:
        print("✅ [SECRET SCAN PASSED] No exposed secrets, tokens, or private sessions detected.\n")
        sys.exit(0)


if __name__ == "__main__":
    run_secret_scan()
