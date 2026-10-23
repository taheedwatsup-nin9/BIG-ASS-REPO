#!/usr/bin/env python3
"""Report stale connector runs and Claude Sessions inbox markdown files."""

from datetime import datetime, timedelta
from pathlib import Path
import subprocess
import sys


MAX_AGE = timedelta(hours=26)
UNITS = (
    "hermes-sync.service",
    "obsidian-sync.service",
    "claude-sessions-import.service",
)
INBOX = Path("/home/taheed/02_Areas/BRAIN/00-Inbox/ClaudeSessions")


def check_unit(unit: str, now: datetime) -> list[str]:
    try:
        result = subprocess.run(
            [
                "systemctl",
                "--user",
                "show",
                unit,
                "-p",
                "ExecMainExitTimestamp",
                "-p",
                "Result",
                "--value",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return [f"{unit}: could not query systemd ({exc})"]

    if result.returncode != 0:
        return [f"{unit}: systemctl show failed (exit {result.returncode})"]

    values = result.stdout.splitlines()
    if len(values) != 2:
        return [f"{unit}: unexpected systemctl output"]

    timestamp, run_result = values
    violations = []
    if run_result != "success":
        violations.append(f"{unit}: Result is {run_result or '(empty)'}, expected success")

    parts = timestamp.split()
    try:
        if len(parts) != 4:
            raise ValueError("unexpected timestamp format")
        last_run = datetime.strptime(" ".join(parts[:3]), "%a %Y-%m-%d %H:%M:%S")
    except ValueError:
        violations.append(f"{unit}: last run timestamp is missing or unparseable")
    else:
        if now - last_run > MAX_AGE:
            violations.append(f"{unit}: last run is older than 26 hours ({timestamp})")

    return violations


def check_inbox(now: datetime) -> list[str]:
    try:
        markdown_files = [
            path for path in INBOX.iterdir() if path.suffix == ".md" and path.is_file()
        ]
        newest_mtime = max((path.stat().st_mtime for path in markdown_files), default=None)
    except OSError as exc:
        return [f"{INBOX}: could not inspect markdown file mtimes ({exc})"]

    if newest_mtime is None:
        return [f"{INBOX}: no .md files found"]
    if now.timestamp() - newest_mtime > MAX_AGE.total_seconds():
        return [f"{INBOX}: newest .md file is older than 26 hours"]
    return []


def main() -> int:
    now = datetime.now()
    violations = []
    for unit in UNITS:
        violations.extend(check_unit(unit, now))
    violations.extend(check_inbox(now))

    if violations:
        print("\n".join(violations))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
