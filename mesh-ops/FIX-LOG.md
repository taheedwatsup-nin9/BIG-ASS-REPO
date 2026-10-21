# Mesh Fix Log — Pass 1 (2026-10-20)

Only safe, reversible fixes inside MUZI's reach were applied. Each entry records before/after and how the fix was verified. Everything else found by the audit lives in [ALERT-LEGEND.md](sandbox://workspace/mesh-ops/ALERT-LEGEND.md) with its status — nothing was silently skipped.

## Fix #1 — Zeabur connector CLI: broken helper path

- **File:** `~/workspace/custom-connectors/custom.legacy-zeabur/bin/zeabur`, line 5.
- **Before:** `sys.path.insert(0, "/opt/muse/skills/custom-connector-setup/templates/skill/bin")` — that directory does not exist, so every run died with `ModuleNotFoundError: No module named 'dynamic_credentials'` before any API call. The connector has been unusable regardless of credential state.
- **After:** `sys.path.insert(0, "/opt/muse/skills/custom-connector-setup/bin")` — where `dynamic_credentials.py` actually lives (verified present).
- **Verification:** `./bin/zeabur projects` now imports cleanly and issues the GraphQL request to api.zeabur.com. The remaining failure is `HTTP Error 401: Unauthorized` from the API itself — a rejected stored credential, **not** a code problem. Per the hard constraints, no re-authentication was attempted and no credential was opened, read, or changed. Cataloged as legend row 16 (needs-taheed-decision).
- **Reversible:** one-line edit; the old value is recorded above.

## Fix #2 — mesh-context.json: two service statuses contradicted by live checks

- **File:** `~/workspace/user/files/mesh-context.json` (`services` array + `note` field). The `snapshot` field was deliberately left at `2026-09-17` — that is the scan date, and changing it would falsify provenance.
- **Google Drive:** `down` → `live`. Evidence: Drive connector `files list` at 2026-10-20T10:45:51Z returned current files, including one dated today ("CR8 network gaps 2026-10-20").
- **Supabase:** `degraded` → `live`. Evidence: `GET /rest/v1/bac_messages` (public anon key from the BAC viewer) returned HTTP 200; newest row 2026-10-19T19:11:10Z, author "hollemu" — healthy read path, current data.
- **Note field:** appended a dated partial-verification sentence stating exactly which statuses were re-checked on 2026-10-20 and that all other figures remain the Sep 17 snapshot / Oct 1 probes until a full re-scan.
- **Verification:** `python3 json.load` parses the edited file cleanly; statuses read back as `live`; `punch_list` intact (9 items); snapshot field unchanged.
- **Reversible:** prior values recorded above; the dashboard's own punch list already documents that the page ignores this data until a newer scan lands.

## Explicitly NOT applied (and where they're tracked)

- **All Lenovo-local items** (gcloud SDK, empty mirror, Workspaces dedupe, rclone mounts, SKILL.md sprawl, Grok CLI, Chrome Remote Desktop, agent draining): the Lenovo is powered on and tailnet-joined, but SSH is not answering (port 22 probed via the tailnet proxy: empty reply, no banner), so none can be verified or worked yet — and most fixes would be destructive anyway. Legend rows 1–3, 5–10, 13, 14, 18, status `blocked-on-lenovo`.
- **Zeabur re-authentication:** credential action, Taheed's only — legend row 16.
- **Google Cloud / Vertex:** waits on Taheed's project ID + service-account key in Zeabur env vars — legend row 11.
- **n8n:** verified live (HTTP 200); no workflow issue was found, so nothing was edited — and per standing rules n8n is never restarted/redeployed and its credentials are never touched.
- **No deletions, no sharing changes, no external sends** were made anywhere in this pass.
