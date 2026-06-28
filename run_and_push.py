#!/usr/bin/env python3
"""
GrainBrief Auto-Pusher
======================
Runs fetch_data.py then automatically pushes data.json to GitHub.
Vercel detects the push and serves the updated file instantly.

Usage:
    python run_and_push.py              # fetch once and push
    python run_and_push.py --loop       # fetch + push every 10 minutes

Requirements:
    - pip install yfinance requests
    - git installed and configured (github.com/cli or regular git)
    - This script must be in the same folder as fetch_data.py
"""

import subprocess
import sys
import time
import argparse
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent


def log(msg):
    print(f"[{datetime.now():%H:%M:%S}] {msg}")


def fetch():
    """Run fetch_data.py to pull market data and write data.json."""
    log("Fetching market data...")
    result = subprocess.run(
        [sys.executable, str(HERE / "fetch_data.py")],
        capture_output=False
    )
    if result.returncode != 0:
        log("⚠ fetch_data.py had errors — check output above")
    else:
        log("✓ data.json updated")


def git_push():
    """Stage data.json and push to GitHub."""
    log("Pushing to GitHub...")
    try:
        # Check if data.json exists
        if not (HERE / "data.json").exists():
            log("✗ data.json not found — skipping push")
            return

        # Git add, commit, push
        subprocess.run(["git", "-C", str(HERE), "add", "data.json"], check=True)
        
        # Check if there's anything to commit
        status = subprocess.run(
            ["git", "-C", str(HERE), "status", "--porcelain"],
            capture_output=True, text=True
        )
        
        if not status.stdout.strip():
            log("✓ No changes to push (data unchanged)")
            return

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        subprocess.run(
            ["git", "-C", str(HERE), "commit", "-m", f"data: refresh {timestamp}"],
            check=True
        )
        subprocess.run(["git", "-C", str(HERE), "push"], check=True)
        log("✓ Pushed to GitHub — Vercel will update in ~10 seconds")

    except subprocess.CalledProcessError as e:
        log(f"✗ Git error: {e}")
        log("  Make sure git is installed and you've run: gh auth login")
    except FileNotFoundError:
        log("✗ git not found — install from git-scm.com")


def run_once():
    fetch()
    git_push()
    log("─" * 45)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--loop", action="store_true", help="Refresh every 10 minutes")
    parser.add_argument("--interval", type=int, default=600, help="Seconds between refreshes")
    args = parser.parse_args()

    log("GrainBrief Auto-Pusher starting...")
    run_once()

    if args.loop:
        log(f"Looping every {args.interval // 60} minutes — press Ctrl+C to stop")
        while True:
            time.sleep(args.interval)
            run_once()


if __name__ == "__main__":
    main()
