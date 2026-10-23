# MUZI job allowlist

Job arguments are strict JSON objects. Commands use fixed argument arrays, never a shell command assembled from job text.

| Tier | Job type | Arguments and fixed action | Limit |
|---|---|---|---|
| READ | `service_status` | `systemctl --user status <unit> --no-pager`; exact unit syntax `^[a-z0-9@._-]+\.(service\|timer)$`. | One unit; status only. |
| READ | `journal_tail` | `journalctl --user -u <unit> -n <lines> --no-pager`. | One valid unit; 1–200 lines. |
| READ | `watchdog` | Runs the fixed `mesh-ops/brain/freshness_watchdog.py`. | No caller-supplied arguments. |
| READ | `disk_usage` | `df -h /`. | Root filesystem only. |
| READ | `list_dir` | `ls -la -- <path>`. | Resolved path must be inside the repository or BRAIN vault; names/metadata only. |
| RUN | `start_service` | `systemctl --user start <unit>`. | Only `obsidian-sync.service`, `claude-sessions-import.service`, or `freshness-watchdog.service`. |
| RUN | `brain_embed_nomic` | `systemctl --user start|stop brain-embed-nomic.service`. | Exact unit; this may consume substantial CPU/network and evict the chat model. |
| RUN | `ollama_health` | GET `http://127.0.0.1:11434/api/tags`. | Fixed loopback endpoint; returns model names only. |
| OPERATE | `restart_service` | `systemctl --user restart <unit>`. | Exact units: `hermes-gateway.service`, `hermes-dashboard.service`, `cr8mor-blackboard-bridge.service`, `claude-always-open.service`, `network-watch.service`. |
| DEVICES | `s10_airplane` | Fixed ADB settings write + airplane-mode broadcast. | Only one authorized Samsung S10-family device; `off` requires a non-empty task reason, and must be turned back on when that task no longer needs network. |
| DEVICES | `s10_recording` | Runs the pinned S10 helper with `start` or `stop`. | Fixed script path and SHA-256; only these two subcommands are accepted. |

Unknown job types and invalid arguments are refused. Secrets/credential files, deletes, arbitrary shell, n8n/Zeabur changes, other Git pushes, and speaker playback are not exposed.
