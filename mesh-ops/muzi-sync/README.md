# MUZI job mailbox

`muzi_jobs.py` polls `mesh-ops/muzi-sync/jobs/` in the repository for JSON jobs, executes only the commands in [ALLOWLIST.md](ALLOWLIST.md), writes a redacted result Markdown file beside each job, and pushes that result file. It is intended to run as the local Linux user's systemd user service; MUZI only needs to submit a job commit through GitHub HTTPS.

## Submit a job

Commit a UTF-8 JSON file such as `mesh-ops/muzi-sync/jobs/status-001.json`:

```json
{
  "id": "status-001",
  "job": "service_status",
  "args": {
    "unit": "example.service"
  },
  "from": "MUZI"
}
```

`id` must match the JSON filename without `.json` and contain only letters, digits, dots, underscores, or hyphens (starting with a letter or digit). The poller pulls with `git pull --ff-only`. It processes JSON files with no corresponding `<id>.result.md`, then commits and pushes each result. Do not reuse IDs after a result file exists.

Supported jobs and argument constraints are listed in [ALLOWLIST.md](ALLOWLIST.md). Extra or malformed fields are refused. Results include the job name, UTC time, exit code, and redacted output.

## Dry run

Run `python3 mesh-ops/muzi-sync/muzi_jobs.py --dry-run` to validate local queued JSON files. It does not run commands, acquire the worker lock, access Git/network, write files, or push results. The fixed actions and per-tier restrictions are listed in `ALLOWLIST.md`.

## Install the user timer

Save the following as `~/.config/systemd/user/muzi-jobs.service`:

```ini
[Unit]
Description=Process allowlisted MUZI mailbox jobs

[Service]
Type=oneshot
WorkingDirectory=/home/taheed/Workspaces/sys/BIG-ASS-REPO
ExecStart=/usr/bin/python3 /home/taheed/Workspaces/sys/BIG-ASS-REPO/mesh-ops/muzi-sync/muzi_jobs.py
```

Save the following as `~/.config/systemd/user/muzi-jobs.timer`:

```ini
[Unit]
Description=Poll the MUZI job mailbox every minute

[Timer]
OnBootSec=30s
OnUnitActiveSec=60s
Persistent=true
Unit=muzi-jobs.service

[Install]
WantedBy=timers.target
```

Do not enable the timer until MUZI has verified the installation and given the separate go-ahead. When authorized, the Git checkout must have a configured upstream and usable Git credentials; its remote must support HTTPS access. The local user also needs permission to query the named user services and journal.

## Limits

- A nonblocking file lock prevents overlapping poller runs.
- The mailbox is not a general command runner: there is no shell, arbitrary executable, or arbitrary script argument.
- Service names and journal line counts are validated; directory listing is limited to the two approved roots and does not show file contents.
- S10 actions require a single authorized device matching a Galaxy S10 model; the recording helper is pinned by SHA-256. Turn airplane mode back on as soon as a task no longer needs network.
- Output is redacted for common token, key, password, JWT, and Telegram-token formats, then capped at 4,000 characters. Redaction is best-effort and must not be treated as a guarantee against every secret format.
- Each command has a 120-second timeout. A failed individual job is reported and does not halt processing of later jobs. A failed initial pull aborts that poll.
- Each result is staged and committed with path restriction, then pushed to the configured upstream branch. Before committing, the poller refuses to publish if the checkout already has commits ahead of upstream, preventing unrelated local commits from being pushed. Git commit hooks, repository configuration, and credentials remain under the local user's control. If publishing fails after the result file is written, it requires local operator recovery.
