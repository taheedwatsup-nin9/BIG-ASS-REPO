#!/usr/bin/env python3
"""
Migrate the v1 mesh snapshot (mesh-context.json, baked 2026-09-17) into
Schema v2 — without letting stale claims survive as facts.

Rules (from MESH-SCHEMA-V2.md):
  - Only states MUZI actually re-verified on 2026-10-20 keep a status.
    Everything else migrates as `unprobed` / confidence `unknown`, with
    the v1 claim preserved in `v1_claim` for lineage.
  - v1 punch_list items + the 18 ALERT-LEGEND rows become alert work items.
  - v1 conduit figures move to lineage as history, not current state.
  - Counts are computed by mesh_logic at write time — never copied across.

Verified-live on 2026-10-20 (evidence: mesh-ops/ALERT-LEGEND.md):
  n8n, GitHub, Google Drive, Supabase — plus Tailscale via `tailscale status`
  (indirect confidence: device list read, not a service probe).

Usage:
    python3 migrate_v1_to_v2.py \
        --v1 ~/workspace/user/files/mesh-context.json \
        --legend ~/workspace/mesh-ops/ALERT-LEGEND.md \
        --out mesh-context-v2.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mesh_logic import FRESHNESS_DEFAULTS, FRESHNESS_FALLBACK, save  # noqa: E402

AUDIT_TS = "2026-10-20T19:00:00Z"  # mesh-ops pass-1 audit window, 2026-10-20
EVIDENCE = "mesh-ops/ALERT-LEGEND.md (pass 1, 2026-10-20)"

# node id -> (observed_status, confidence, evidence note)
VERIFIED = {
    "n8n": ("live", "verified", "HTTP 200 cr8mor-n8n.zeabur.app"),
    "gh": ("live", "verified", "BIG-ASS-REPO answers 200"),
    "gdrive": ("live", "verified", "Drive connector listed files 2026-10-20T10:45:51Z"),
    "supabase": ("live", "verified", "REST 200; newest bac_messages row 2026-10-19T19:11:10Z"),
    "tailscale": ("live", "indirect", "tailscale status device list read 2026-10-20"),
}

SERVICE_TO_NODE = {
    "Claude": "claude", "Docker": "docker", "n8n": "n8n", "GitHub": "gh",
    "Google Cloud": "gcloud", "Google Drive": "gdrive", "Supabase": "supabase",
    "Tailscale": "tailscale", "Ollama": "ollama", "Hermes Agent": "hermes",
    "Grok CLI": "grok", "Aider": "aider", "Figma": "figma", "Vercel": "vercel",
}

KIND_MAP = {  # v1 kinds that are not in the v2 kind vocabulary
    "folder": "workspace", "dead": "service", "skill": "agent",
    "script": "service", "cred": "external_dependency", "mcp": "service",
    "agentdoc": "asset",
}
OWNER_LANE = {  # by v1 kind / id — honest best assignment, editable in v2
    "host": "lenovo", "workspace": "lenovo",
}
LANE_BY_ID = {
    "zeabur": "cloud", "cloud": "cloud", "n8n": "cloud", "supabase": "cloud",
    "gdrive": "cloud", "gcloud": "cloud", "gh": "cloud", "vercel": "cloud",
    "tailscale": "cloud", "hermes": "cloud", "ollama": "cloud", "docker": "cloud",
}


def lane_for(node):
    if node["id"] in LANE_BY_ID:
        return LANE_BY_ID[node["id"]]
    return OWNER_LANE.get(node.get("kind"), "lenovo")


def migrate_nodes(v1):
    nodes = []
    for raw in v1.get("nodes", []):
        kind = KIND_MAP.get(raw.get("kind"), raw.get("kind", "service"))
        node = {
            "id": raw["id"],
            "kind": kind,
            "name": raw.get("label", raw["id"]),
            "owner_lane": lane_for({**raw, "kind": kind}),
            "observed_status": "unprobed",
            "status_confidence": "unknown",
            "last_verified_at": None,
            "verified_by": None,
            "evidence_ref": None,
            "freshness_policy": {
                "stale_after_seconds": FRESHNESS_DEFAULTS.get(kind, FRESHNESS_FALLBACK),
                "decay_to": "unprobed",
            },
            "probes": [],
            "v1_kind": raw.get("kind"),
        }
        if raw["id"] in VERIFIED:
            status, confidence, note = VERIFIED[raw["id"]]
            node.update({
                "observed_status": status,
                "status_confidence": confidence,
                "last_verified_at": AUDIT_TS,
                "verified_by": "muzi-pass1-audit",
                "evidence_ref": f"{EVIDENCE} — {note}",
            })
        nodes.append(node)
    return nodes


def migrate_edges(v1):
    edges = []
    for i, raw in enumerate(v1.get("edges", []), start=1):
        edges.append({
            "id": f"e-{i:03d}",
            "from": raw["from"],
            "to": raw["to"],
            "type": "depends_on",  # v1 edges were untyped; refine in VS Code session
            "status": "unprobed",
            "probe_command": None,
            "last_verified_at": None,
            "evidence_ref": None,
            "triage_order": 99,
        })
    return edges


STATUS_MAP = {
    "fixable-now — **FIXED**": ("fixed", "cloud"),
    "blocked-on-lenovo": ("blocked", "lenovo"),
    "needs-taheed-decision": ("open", "taheed"),
    "leave-no-action": ("fixed", "lenovo"),
}
SEVERITY_MAP = {"High": "high", "Medium": "medium", "Low": "low", "Resolved": "low", "—": "low"}

# Keyword -> entity node id, so alerts point at a real node where one exists.
ENTITY_HINTS = [
    ("gcloud", "gcloud"), ("Google Drive", "gdrive"), ("Supabase", "supabase"),
    ("Docker", "docker"), ("Grok CLI", "grok"), ("rclone", "rclone"),
    ("SKILL.md", "skillmd"), ("mirror", "mirror"), ("Workspaces", "workspaces"),
    ("BRAIN", "brain"), ("Zeabur", "zeabur"), ("Hermes", "hermes"),
]


def entity_for(issue):
    for hint, entity in ENTITY_HINTS:
        if hint.lower() in issue.lower():
            return entity
    return "lenovo" if issue else "mesh"


def migrate_alerts_from_legend(legend_path):
    """Parse the 18-row ALERT-LEGEND.md table into alert work items."""
    if not legend_path or not Path(legend_path).exists():
        return []
    alerts = []
    for line in Path(legend_path).read_text().splitlines():
        m = re.match(r"\| (\d+) \| \*\*(.+?)\*\*.*?\| (.*?) \| (.*?) \| (.*?) \| (.*?) \|", line)
        if not m:
            continue
        num, issue, _verified, severity, fix_target, status_raw = m.groups()
        status, lane = STATUS_MAP.get(status_raw.strip(), ("open", "unknown"))
        alerts.append({
            "alert_id": f"alert-{int(num):03d}",
            "entity_id": entity_for(issue),
            "severity": SEVERITY_MAP.get(severity.strip(), "medium"),
            "issue": issue.strip(),
            "root_cause_hint": None,
            "fix_target": fix_target.strip(),
            "owner_lane": lane,
            "unblock_condition": (
                "sshd answers on Lenovo port 22" if status == "blocked"
                else "none — ruled no-action (divergent snapshot, not a dupe)"
                if status_raw.strip() == "leave-no-action"
                else "Taheed decision" if lane == "taheed"
                else "re-probe confirms the fix"
            ),
            "status": status,
            "evidence_ref": "mesh-ops/ALERT-LEGEND.md",
            "last_updated_at": "2026-10-20",
        })
    return alerts


def main():
    ap = argparse.ArgumentParser(description="Migrate mesh-context v1 -> v2")
    ap.add_argument("--v1", required=True)
    ap.add_argument("--legend")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    v1 = json.loads(Path(args.v1).read_text())
    dataset = {
        "lineage": {
            "snapshot_id": "cr8mesh-2026-10-20-v2",
            "base_snapshot_id": f"cr8mesh-{v1.get('snapshot', 'unknown')}-v1",
            "generated_at": AUDIT_TS,
            "scanner": {"name": "muzi-migrate_v1_to_v2", "version": "1.0", "ran_on": "muzi-vm"},
            "source_status": "stale",
            "v1_header_claim": v1.get("header_claim"),
            "v1_note": v1.get("note"),
            "v1_conduit_history": v1.get("conduit"),
            "migration_rule": "Unverified v1 statuses land as unprobed; only the "
                              "2026-10-20 pass-1 verified set keeps a status.",
        },
        "nodes": migrate_nodes(v1),
        "edges": migrate_edges(v1),
        "alerts": migrate_alerts_from_legend(args.legend),
    }
    # Service claims preserved as lineage, never as node state.
    dataset["lineage"]["v1_service_claims"] = {
        SERVICE_TO_NODE.get(s["name"], s["name"]): s["status"]
        for s in v1.get("services", [])
    }
    save(dataset, args.out)
    counts = dataset["lineage"]
    print(f"wrote {args.out}: {counts['node_count']} nodes, "
          f"{counts['edge_count']} edges, {len(dataset['alerts'])} alerts")
    live = [n["id"] for n in dataset["nodes"] if n["observed_status"] == "live"]
    print(f"kept verified-live: {live}")
    print(f"all other nodes: unprobed (v1 claims preserved in lineage)")


if __name__ == "__main__":
    main()
