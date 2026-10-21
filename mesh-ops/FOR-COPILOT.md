# For Copilot — start here

Pushed by MUZI on 2026-10-21 at Taheed's direction, following the
MUZI × Copilot mesh-map discussion (`COPILOT-DISCUSSION-2026-10-20.md`).

## What's here

- `scripts/` — the logic scripts implementing schema v2: decay,
  computed counts, validation, probe runner, triage walk, gate-zero.
  Read `scripts/README.md` first.
- `scripts/mesh-context-v2.json` — the migrated dataset: 36 nodes,
  34 edges, 18 alert work items. Only the 5 nodes verified live on
  2026-10-20 carry a status; everything else is honestly `unprobed`.
- `MESH-SCHEMA-V2.md` — the merged schema you and MUZI agreed on.
- `ALERT-LEGEND.md` / `FIX-LOG.md` — the pass-1 audit and its evidence.
- `data/mesh-context.json` — the original v1 snapshot (2026-09-17).
- `data/cr8mor-mesh.html` — the current mesh page.

## First moves in VS Code

1. Open this `mesh-ops/` folder as (part of) the workspace.
2. In the terminal, on the Lenovo: `bash scripts/gate_zero_sshd.sh`
   — read-only sshd check. Gate zero gates 12 of 18 alert rows.
3. Then: `bash scripts/run_session.sh data/mesh-context.json`
   — runs migrate → decay → validate → summary → triage and drops a
   timestamped session folder under `session-output/`.
4. Add real probe commands to nodes/edges in the v2 dataset, then run
   `scripts/probe_runner.py` to turn claims into evidence.
5. Commit results back here. MUZI re-verifies cloud-side and updates
   the legend.
