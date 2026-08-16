#!/usr/bin/env python3
"""
EL AL-NOOR AI - Auto-Updater Module (GitHub Integration)
----------------------------------------------------------
Checks internet connection on startup.
If online: fetches latest update from GitHub repository (https://github.com/a360n/EL-AL-NOOR-AI-Desktop-App.git).
If offline: directly runs the existing local version seamlessly.
Outputs 100% clean English in terminal to ensure cross-platform compatibility without BiDi artifacts.
"""

import os
import socket
import logging
import subprocess
from typing import Dict, Any

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger("AutoUpdater")

REPO_URL = "https://github.com/a360n/EL-AL-NOOR-AI-Desktop-App.git"
APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def check_internet_connection(host: str = "github.com", port: int = 443, timeout: float = 2.0) -> bool:
    """Checks whether the machine has an active internet connection."""
    try:
        socket.setdefaulttimeout(timeout)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((host, port))
            return True
    except (socket.timeout, socket.gaierror, OSError):
        try:
            # Fallback to public DNS (8.8.8.8)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect(("8.8.8.8", 53))
                return True
        except Exception:
            return False


def run_git_command(args, cwd=APP_DIR) -> subprocess.CompletedProcess:
    """Executes a git command inside the app directory."""
    return subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=15
    )


def check_and_apply_update() -> Dict[str, Any]:
    """
    Performs auto-update verification:
    1. Checks internet connectivity.
    2. If offline: returns offline status and proceeds to launch local copy.
    3. If online: checks git repository for updates and safely applies updates via reset/pull.
    """
    print("\n" + "=" * 60)
    print("[UPDATER] Checking network connectivity and GitHub updates...")
    print("=" * 60)

    # 1. Check Internet
    if not check_internet_connection():
        msg = "No internet connection detected (Offline Mode). Launching local version immediately..."
        print(f"[UPDATER] {msg}")
        logger.info(msg)
        return {"status": "offline", "updated": False, "message": msg}

    print("[UPDATER] Internet connection active. Checking repository: https://github.com/a360n/EL-AL-NOOR-AI-Desktop-App.git")

    # 2. Check if .git directory exists
    git_dir = os.path.join(APP_DIR, ".git")
    if not os.path.exists(git_dir):
        msg = "No .git directory found. Running existing local build."
        print(f"[UPDATER] {msg}")
        return {"status": "no_git", "updated": False, "message": msg}

    try:
        # Check current remote
        remote_res = run_git_command(["remote", "get-url", "origin"])
        if remote_res.returncode != 0 or not remote_res.stdout.strip():
            run_git_command(["remote", "add", "origin", REPO_URL])

        # Fetch latest commits from origin main
        print("[UPDATER] Fetching latest commits from GitHub (git fetch origin main)...")
        fetch_res = run_git_command(["fetch", "origin", "main"])
        if fetch_res.returncode != 0:
            msg = f"Unable to fetch updates from GitHub: {fetch_res.stderr.strip()}"
            print(f"[UPDATER] [WARNING] {msg}")
            return {"status": "fetch_error", "updated": False, "message": msg}

        # Compare local HEAD with origin/main
        local_hash = run_git_command(["rev-parse", "HEAD"]).stdout.strip()
        remote_hash = run_git_command(["rev-parse", "origin/main"]).stdout.strip()

        if local_hash and remote_hash and local_hash != remote_hash:
            print(f"[UPDATER] New update found on GitHub ({remote_hash[:7]})! Applying update...")
            # Safely reset to remote to avoid local merge conflict on runtime files (e.g. SQLite database)
            run_git_command(["reset", "--hard", "origin/main"])
            msg = f"Successfully updated application to latest release ({remote_hash[:7]})!"
            print(f"[UPDATER] [SUCCESS] {msg}")
            logger.info(msg)
            return {"status": "updated", "updated": True, "commit": remote_hash[:7], "message": msg}
        else:
            msg = f"Application is already up to date with GitHub ({local_hash[:7] if local_hash else 'Latest'})."
            print(f"[UPDATER] [OK] {msg}")
            logger.info(msg)
            return {"status": "up_to_date", "updated": False, "message": msg}

    except Exception as e:
        msg = f"Error occurred during update check: {e}"
        print(f"[UPDATER] [ERROR] {msg}")
        logger.warning(msg)
        return {"status": "error", "updated": False, "message": str(e)}


if __name__ == "__main__":
    res = check_and_apply_update()
    print(res)
