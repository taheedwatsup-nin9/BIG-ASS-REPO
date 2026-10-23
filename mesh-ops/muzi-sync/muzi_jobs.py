#!/usr/bin/env python3
"""Process narrowly allowlisted MUZI jobs from the repository."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

REPO = Path("/home/taheed/Workspaces/sys/BIG-ASS-REPO")
JOBS_DIR = REPO / "mesh-ops/muzi-sync/jobs"
WATCHDOG = REPO / "mesh-ops/brain/freshness_watchdog.py"
S10_SCRIPT = REPO / "mesh-ops/experiments/runner/lenovo/s10.sh"
S10_SHA256 = "134ac5c6d523f4fd5789cce5f1589f25265a851eb7e7b18f48a762ceed4092d7"
ADB = Path("/home/taheed/Android/Sdk/platform-tools/adb")
S10_RECORDINGS = "/sdcard/Android/data/com.nll.asr/files/recordings"
OLLAMA_TAGS_URL = "http://127.0.0.1:11434/api/tags"
S10_MODEL_RE = re.compile(r"^SM[_-]G9(?:70|73|75|77)[A-Z0-9_]*$")
START_UNITS = frozenset(
    {"obsidian-sync.service", "claude-sessions-import.service", "freshness-watchdog.service"}
)
RESTART_UNITS = frozenset(
    {
        "hermes-gateway.service",
        "hermes-dashboard.service",
        "cr8mor-blackboard-bridge.service",
        "claude-always-open.service",
        "network-watch.service",
    }
)
BRAIN_EMBED_UNIT = "brain-embed-nomic.service"
ALLOWED_DIRS = (
    REPO,
    Path("/home/taheed/02_Areas/BRAIN"),
)
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
UNIT_RE = re.compile(r"^[a-z0-9@._-]+\.(?:service|timer)$")
MAX_OUTPUT = 4000
TIMEOUT_SECONDS = 120

REDACT_PATTERNS = (
    (re.compile(r"\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\b"), "[REDACTED JWT]"),
    (re.compile(r"\b\d{6,}:[A-Za-z0-9_-]{20,}\b"), "[REDACTED TELEGRAM TOKEN]"),
    (re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"), "[REDACTED TOKEN]"),
    (re.compile(r"\b(?:xox[baprs]-[A-Za-z0-9-]{10,})\b"), "[REDACTED TOKEN]"),
    (
        re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}"),
        "Bearer [REDACTED]",
    ),
    (
        re.compile(
            r"""(?i)\b(api[_-]?key|private[_-]?key|key|access[_-]?token|refresh[_-]?token|authorization|password|passwd|passphrase|pwd|secret|token)\b(\s*[:=]\s*)(?:"[^"]*"|'[^']*'|[^\s,;]+)"""
        ),
        r"\1\2[REDACTED]",
    ),
)


def redact(text: str) -> str:
    for pattern, replacement in REDACT_PATTERNS:
        text = pattern.sub(replacement, text)
    return text[:MAX_OUTPUT]


def run_command(
    argv: list[str], *, cwd: Path = REPO, env: dict[str, str] | None = None
) -> tuple[int, str]:
    try:
        result = subprocess.run(
            argv,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            env=env,
        )
        return result.returncode, result.stdout + result.stderr
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout or ""
        stderr = error.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        return 124, f"Command timed out.\n{stdout}{stderr}"
    except OSError as error:
        return 127, f"Could not start command: {error}"


def safe_directory(value: Any) -> Path | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        requested = Path(value).expanduser().resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    if not requested.is_dir():
        return None
    roots = []
    for root in ALLOWED_DIRS:
        try:
            roots.append(root.resolve(strict=True))
        except (OSError, RuntimeError):
            continue
    if any(requested == root or root in requested.parents for root in roots):
        return requested
    return None


def ollama_health() -> tuple[int, str]:
    try:
        with urlopen(OLLAMA_TAGS_URL, timeout=5) as response:
            payload = json.load(response)
    except (OSError, URLError, json.JSONDecodeError) as error:
        return 1, f"Ollama health check failed: {type(error).__name__}"
    models = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(models, list):
        return 1, "Ollama health check returned an unexpected response"
    names = sorted(
        item["name"]
        for item in models
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    )
    return 0, f"HTTP 200; models: {', '.join(names)}"


def s10_serial() -> tuple[str | None, str | None]:
    if not ADB.is_file():
        return None, "ADB executable is missing"
    code, output = run_command([str(ADB), "devices", "-l"])
    if code:
        return None, "ADB device listing failed"
    rows = [
        line.split()
        for line in output.splitlines()
        if line.strip() and not line.startswith("List of devices")
    ]
    if len(rows) != 1 or len(rows[0]) < 3 or rows[0][1] != "device":
        return None, "Expected exactly one authorized S10 device"
    model = next(
        (item.removeprefix("model:") for item in rows[0][2:] if item.startswith("model:")),
        "",
    )
    if not S10_MODEL_RE.fullmatch(model):
        return None, "Connected Android device is not a recognized Galaxy S10 model"
    return rows[0][0], None


def set_s10_airplane(state: str) -> tuple[int, str]:
    serial, error = s10_serial()
    if error or serial is None:
        return 2, error or "Could not identify S10 device"
    enabled = state == "on"
    value = "true" if enabled else "false"
    code, output = run_command(
        [str(ADB), "-s", serial, "shell", "settings", "put", "global", "airplane_mode_on", "1" if enabled else "0"]
    )
    if code:
        return code, output
    code, broadcast = run_command(
        [
            str(ADB),
            "-s",
            serial,
            "shell",
            "am",
            "broadcast",
            "-a",
            "android.intent.action.AIRPLANE_MODE",
            "--ez",
            "state",
            value,
        ]
    )
    return code, output + broadcast


def validate_job(job_type: Any, args: Any) -> str | None:
    if not isinstance(args, dict):
        return "REFUSED: args must be an object"

    if job_type == "service_status":
        unit = args.get("unit")
        if set(args) != {"unit"} or not isinstance(unit, str) or not UNIT_RE.fullmatch(unit):
            return "REFUSED: invalid unit"
        return None

    if job_type == "journal_tail":
        unit = args.get("unit")
        lines = args.get("lines")
        if (
            set(args) != {"unit", "lines"}
            or not isinstance(unit, str)
            or not UNIT_RE.fullmatch(unit)
            or isinstance(lines, bool)
            or not isinstance(lines, int)
            or not 1 <= lines <= 200
        ):
            return "REFUSED: invalid journal_tail arguments"
        return None

    if job_type == "watchdog":
        if args:
            return "REFUSED: watchdog takes no arguments"
        return None

    if job_type == "disk_usage":
        if args:
            return "REFUSED: disk_usage takes no arguments"
        return None

    if job_type == "list_dir":
        if set(args) != {"path"}:
            return "REFUSED: invalid list_dir arguments"
        if safe_directory(args.get("path")) is None:
            return "REFUSED: path must be a directory under an approved root"
        return None

    if job_type == "start_service":
        unit = args.get("unit")
        if set(args) != {"unit"} or not isinstance(unit, str) or unit not in START_UNITS:
            return "REFUSED: service is not on the start allowlist"
        return None

    if job_type == "brain_embed_nomic":
        action = args.get("action")
        if set(args) != {"action"} or not isinstance(action, str) or action not in {"start", "stop"}:
            return "REFUSED: action must be start or stop"
        return None

    if job_type == "ollama_health":
        if args:
            return "REFUSED: ollama_health takes no arguments"
        return None

    if job_type == "restart_service":
        unit = args.get("unit")
        if set(args) != {"unit"} or not isinstance(unit, str) or unit not in RESTART_UNITS:
            return "REFUSED: service is not on the restart allowlist"
        return None

    if job_type == "s10_recording":
        action = args.get("action")
        if set(args) != {"action"} or not isinstance(action, str) or action not in {"start", "stop"}:
            return "REFUSED: action must be start or stop"
        return None

    if job_type == "s10_airplane":
        state = args.get("state")
        if state == "on" and set(args) == {"state"}:
            return None
        task = args.get("task")
        if (
            state == "off"
            and set(args) == {"state", "task"}
            and isinstance(task, str)
            and task.strip()
            and len(task) <= 120
        ):
            return None
        return "REFUSED: airplane off requires a task reason; valid states are on/off"

    return "REFUSED: not on allowlist"


def execute_job(job_type: Any, args: Any) -> tuple[int, str]:
    refusal = validate_job(job_type, args)
    if refusal:
        return (126 if refusal == "REFUSED: not on allowlist" else 2), refusal

    if job_type == "service_status":
        return run_command(["systemctl", "--user", "status", args["unit"], "--no-pager"])
    if job_type == "journal_tail":
        return run_command(
            ["journalctl", "--user", "-u", args["unit"], "-n", str(args["lines"]), "--no-pager"]
        )
    if job_type == "watchdog":
        return run_command([sys.executable, str(WATCHDOG)])
    if job_type == "disk_usage":
        return run_command(["df", "-h", "/"])
    if job_type == "list_dir":
        directory = safe_directory(args["path"])
        if directory is None:
            return 2, "REFUSED: path must be a directory under an approved root"
        return run_command(["ls", "-la", "--", str(directory)])
    if job_type == "start_service":
        return run_command(["systemctl", "--user", "start", args["unit"]])
    if job_type == "brain_embed_nomic":
        return run_command(["systemctl", "--user", args["action"], BRAIN_EMBED_UNIT])
    if job_type == "ollama_health":
        return ollama_health()
    if job_type == "restart_service":
        return run_command(["systemctl", "--user", "restart", args["unit"]])
    if job_type == "s10_recording":
        try:
            digest = hashlib.sha256(S10_SCRIPT.read_bytes()).hexdigest()
        except OSError:
            return 2, "REFUSED: S10 helper is unavailable"
        if S10_SCRIPT.is_symlink() or digest != S10_SHA256:
            return 2, "REFUSED: S10 helper does not match the reviewed version"
        env = {
            "HOME": "/home/taheed",
            "PATH": "/usr/bin:/bin",
            "ADB": str(ADB),
            "S10_REC_DIR": S10_RECORDINGS,
            "S10_REC_X": "540",
            "S10_REC_Y": "1972",
        }
        return run_command(["/bin/bash", str(S10_SCRIPT), args["action"]], env=env)
    if job_type == "s10_airplane":
        return set_s10_airplane(args["state"])
    return 126, "REFUSED: not on allowlist"


def load_job(job_path: Path) -> tuple[Any, Any, str | None]:
    if not ID_RE.fullmatch(job_path.stem):
        return None, None, "unsafe job filename"
    if job_path.is_symlink():
        return None, None, "REFUSED: job file must not be a symlink"
    try:
        data = json.loads(job_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None, None, "invalid or unreadable JSON"
    if (
        not isinstance(data, dict)
        or set(data) != {"id", "job", "args", "from"}
        or data.get("from") != "MUZI"
        or data.get("id") != job_path.stem
    ):
        return None, None, "REFUSED: job must have required fields, from=MUZI, and matching id"
    return data["job"], data["args"], None


def dry_run() -> int:
    if not JOBS_DIR.is_dir():
        print(f"DRY RUN: jobs directory does not exist: {JOBS_DIR}", file=sys.stderr)
        return 1

    print("DRY RUN: local validation only; no commands, Git/network access, writes, or pushes.")
    pending = 0
    invalid = 0
    for job_path in sorted(JOBS_DIR.glob("*.json")):
        result_path = JOBS_DIR / f"{job_path.stem}.result.md"
        if result_path.exists() or result_path.is_symlink():
            continue
        pending += 1
        job_type, args, error = load_job(job_path)
        error = error or validate_job(job_type, args)
        if error:
            invalid += 1
            print(f"{job_path.name}: INVALID ({error})")
        else:
            print(f"{job_path.name}: VALID ({job_type}); not executed")
    if not pending:
        print("No pending job files.")
    else:
        print(f"Checked {pending} pending job(s); invalid: {invalid}.")
    return 2 if invalid else 0


def write_result(path: Path, job_type: str, exit_code: int, output: str) -> None:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    safe_job = job_type.replace("|", "\\|").replace("\n", " ")[:100]
    safe_output = redact(output)
    body = (
        f"# MUZI job result\n\n"
        f"- Job: `{safe_job}`\n"
        f"- Time (UTC): `{timestamp}`\n"
        f"- Exit code: `{exit_code}`\n\n"
        f"## Output\n\n"
        + ("\n".join(f"    {line}" for line in safe_output.splitlines()) or "    (no output)")
        + "\n"
    )
    path.write_text(body, encoding="utf-8")


def publish_result(result_path: Path) -> tuple[bool, str]:
    relative_path = result_path.relative_to(REPO).as_posix()
    code, upstream = run_command(
        ["git", "-C", str(REPO), "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"]
    )
    if code != 0:
        return False, f"cannot determine upstream: {upstream}"
    upstream = upstream.strip()
    if "/" not in upstream:
        return False, "cannot determine upstream remote and branch"
    remote, branch = upstream.split("/", 1)

    code, ahead = run_command(
        ["git", "-C", str(REPO), "rev-list", "--count", f"{upstream}..HEAD"]
    )
    if code != 0 or ahead.strip() != "0":
        return False, "refusing to publish because the checkout has commits ahead of upstream"

    code, output = run_command(["git", "-C", str(REPO), "add", "--", relative_path])
    if code != 0:
        return False, f"git add failed: {output}"

    code, output = run_command(
        [
            "git",
            "-C",
            str(REPO),
            "commit",
            "--only",
            "-m",
            f"Add MUZI job result: {result_path.name}",
            "--",
            relative_path,
        ]
    )
    if code != 0:
        return False, f"git commit failed: {output}"

    code, output = run_command(
        ["git", "-C", str(REPO), "push", remote, f"HEAD:refs/heads/{branch}"]
    )
    return code == 0, output if code == 0 else f"git push failed: {output}"


def process_job(job_path: Path) -> None:
    result_path = JOBS_DIR / f"{job_path.stem}.result.md"
    if result_path.exists() or result_path.is_symlink():
        return
    job_type, args, error = load_job(job_path)
    if error:
        job_type, exit_code, output = "INVALID_JOB", 2, error
    else:
        exit_code, output = execute_job(job_type, args)

    try:
        write_result(result_path, str(job_type), exit_code, output)
    except OSError as error:
        print(f"Could not write result for {job_path.name}: {error}", file=sys.stderr)
        return

    published, message = publish_result(result_path)
    if not published:
        print(f"Could not publish {result_path.name}: {message}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validate local pending jobs without commands, Git/network access, or writes",
    )
    args = parser.parse_args()
    if args.dry_run:
        return dry_run()

    if not JOBS_DIR.is_dir():
        print(f"Jobs directory does not exist: {JOBS_DIR}", file=sys.stderr)
        return 1

    lock_path = JOBS_DIR / ".muzi_jobs.lock"
    try:
        lock_fd = os.open(
            lock_path,
            os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW,
            0o600,
        )
        with os.fdopen(lock_fd, "r+") as lock_file:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return 0

            code, output = run_command(["git", "-C", str(REPO), "pull", "--ff-only"])
            if code != 0:
                print(f"git pull failed; no jobs processed: {output}", file=sys.stderr)
                return 1

            for job_path in sorted(JOBS_DIR.glob("*.json")):
                try:
                    process_job(job_path)
                except Exception as error:
                    # A malformed or failing job must not prevent later jobs from running.
                    print(f"Job {job_path.name} failed: {error}", file=sys.stderr)
        return 0
    except OSError as error:
        print(f"Could not acquire mailbox lock: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
