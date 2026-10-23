# MUZI job allowlist

This installed draft implements only the read-only job types listed below.

| Job type | What it runs | Why it is safe |
|---|---|---|
| `service_status` | `systemctl --user status <unit> --no-pager`; the unit must match `^[a-z0-9@._-]+\.(service\|timer)$`. | Reads status for one named user service or timer; no state-changing systemctl operation is available. |
| `journal_tail` | `journalctl --user -u <unit> -n <lines> --no-pager`; uses the same unit check and restricts `lines` to 1–200. | Reads a bounded tail of one user unit's journal; no journal modification is available. |
| `watchdog` | Runs the fixed script `mesh-ops/brain/freshness_watchdog.py` with the current Python interpreter. | The caller cannot select a script or provide arguments. |
| `disk_usage` | `df -h /`. | Reads filesystem capacity for the root filesystem only. |
| `list_dir` | `ls -la -- <path>`; the resolved directory must be inside `/home/taheed/Workspaces/sys/BIG-ASS-REPO` or `/home/taheed/02_Areas/BRAIN`. | Lists names and metadata only; it does not read file contents or follow paths outside the approved roots. |

Unknown job types and invalid arguments are refused. Commands are invoked as argument arrays, never through a shell.
