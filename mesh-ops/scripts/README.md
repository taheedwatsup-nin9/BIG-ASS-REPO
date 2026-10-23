# CR8 Mesh — logic scripts

Written 2026-10-21 by MUZI, implementing the MUZI × Copilot schema v2
discussion (`../COPILOT-DISCUSSION-2026-10-20.md`, `../MESH-SCHEMA-V2.md`).
These are the working logic behind the mesh map — the map is the render,
these scripts are the rules.

## The rules they enforce

1. **No status without evidence.** A node claiming `live/degraded/down`
   must carry `last_verified_at` + `evidence_ref`, and the evidence must
   be fresh (`freshness_policy.stale_after_seconds`). Otherwise it decays
   to `unprobed`. Status and confidence are separate fields.
2. **Counts are computed**, never hand-typed. This kills the v1 problem
   (header claimed 125 nodes / 295 edges; the arrays held 36 / 34).
3. **Alerts are work items** — owner lane + unblock condition + status.
4. **Troubleshooting is a walk** — symptom node → upstream edges → stop
   at the first broken/unprobed edge. Observe → fix → re-probe.

## Files

| Script | What it does | Run it |
|---|---|---|
| `mesh_logic.py` | Core library + CLI: decay, computed counts, validation, upstream walk | `python3 mesh_logic.py summary\|decay\|validate <file>` |
| `migrate_v1_to_v2.py` | Converts the v1 snapshot to v2. Only the 2026-10-20 pass-1 verified set (n8n, GitHub, Drive, Supabase, Tailscale-indirect) keeps a status; everything else lands as `unprobed`, v1 claims preserved in lineage. Parses the 18 legend rows into alert work items. | `python3 migrate_v1_to_v2.py --v1 <mesh-context.json> --legend ../ALERT-LEGEND.md --out mesh-context-v2.json` |
| `probe_runner.py` | Runs probe commands defined on nodes/edges, writes evidence JSONL, updates observations. Default is `--dry-run` (executes nothing). | `python3 probe_runner.py mesh-context-v2.json --dry-run` |
| `triage.py` | The roadmap walk from a symptom node. | `python3 triage.py mesh-context-v2.json n8n` |
| `gate_zero_sshd.sh` | Lenovo-local sshd check (installed? enabled? listening on :22? banner?). Read-only unless `--fix` is passed, which installs/enables openssh-server via sudo. | On the Lenovo, in VS Code terminal: `bash gate_zero_sshd.sh` |
| `run_session.sh` | The session runner: gate zero → migrate → decay → validate → summary → triage, output to `../session-output/<timestamp>/`. | `bash run_session.sh` |

## For the VS Code session (Copilot's lane)

1. Open this folder as the workspace, plus `mesh-context.json` and
   `cr8mor-mesh.html`.
2. Run `bash gate_zero_sshd.sh` on the Lenovo first — gate zero gates
   12 of 18 alert rows. Paste the output back to MUZI as evidence.
3. Run `bash run_session.sh <path-to-v1-mesh-context.json>` once to
   produce `mesh-context-v2.json`.
4. Add real probe commands to nodes/edges in the v2 file (each edge's
   `probe_command`, each node's `probes[]`), then
   `python3 probe_runner.py mesh-context-v2.json --run` turns claims
   into evidence.
5. Commit the v2 dataset + session output. MUZI re-verifies cloud-side.

## Notes

- Python 3 stdlib only. No installs, no credentials, no network calls
  except the probe commands you define yourself in the dataset.
- Credential nodes (GitHub token, Supabase key, Tailscale auth) migrate
  as `external_dependency` with status `unprobed` by design — per the
  Conduit rule, credential state is never rendered on the map.
- v1 edge types were untyped, so all migrate as `depends_on` with
  `triage_order 99`. Typing them (`runs_on`, `calls`, `stores_in`,
  `depends_on`, `exposes`, `ingress`) is session work in VS Code.
