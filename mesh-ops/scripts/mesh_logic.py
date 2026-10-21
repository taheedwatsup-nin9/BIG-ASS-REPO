#!/usr/bin/env python3
"""
CR8 Mesh — core logic (Schema v2)

Implements the rules MUZI x Copilot agreed on 2026-10-20:
  1. No node/edge is "live" without fresh probe evidence, else it decays
     to `unprobed`. Status and confidence are separate fields.
  2. Counts are COMPUTED from the arrays, never hand-typed.
  3. Alerts are work items (owner lane + unblock condition), not labels.
  4. Troubleshooting = start at the symptom node, walk upstream edges,
     stop at the first broken or unprobed edge.

Pure stdlib. Imported by the other scripts in this folder; also runnable:

    python3 mesh_logic.py summary mesh-context-v2.json
    python3 mesh_logic.py decay   mesh-context-v2.json --now 2026-10-21T07:00:00Z
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

# Freshness defaults by node kind (seconds). A node whose last verification
# is older than this decays. The 2h mesh watcher tightens service values
# in live operation; these defaults are the offline/VS Code session values.
FRESHNESS_DEFAULTS = {
    "host": 86_400,              # 24h
    "service": 86_400,           # 24h
    "network_segment": 86_400,   # 24h
    "cloud_project": 259_200,    # 72h
    "external_dependency": 259_200,
    "agent": 259_200,
    "storage": 604_800,          # 7d
    "workspace": 604_800,
    "folder": 604_800,
    "mount": 604_800,
    "asset": 604_800,
}
FRESHNESS_FALLBACK = 86_400

VALID_NODE_STATUS = {"live", "degraded", "down", "unprobed"}
VALID_CONFIDENCE = {"verified", "indirect", "unknown"}
VALID_EDGE_STATUS = {"verified", "broken", "blocked", "unprobed"}
VALID_ALERT_STATUS = {"open", "blocked", "fixed"}
ALERT_REQUIRED = [
    "alert_id", "entity_id", "severity", "issue",
    "owner_lane", "unblock_condition", "status", "last_updated_at",
]


def parse_ts(value):
    """Parse an ISO-8601 timestamp (or bare date) to an aware datetime."""
    if not value:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def iso_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def freshness_for(node):
    policy = node.get("freshness_policy") or {}
    if policy.get("stale_after_seconds"):
        return int(policy["stale_after_seconds"])
    return FRESHNESS_DEFAULTS.get(node.get("kind"), FRESHNESS_FALLBACK)


def decay_node(node, now):
    """Apply the decay rule to one node in place. Returns True if it changed.

    A node claiming live/degraded/down needs evidence (last_verified_at +
    evidence_ref) that is still fresh. Anything else becomes `unprobed`
    with confidence `unknown`. Nodes already unprobed are untouched.
    """
    status = node.get("observed_status", "unprobed")
    if status == "unprobed":
        return False
    last = parse_ts(node.get("last_verified_at"))
    stale_after = freshness_for(node)
    expired = last is None or (now - last).total_seconds() > stale_after
    if expired or not node.get("evidence_ref"):
        node["observed_status"] = (node.get("freshness_policy") or {}).get(
            "decay_to", "unprobed"
        )
        node["status_confidence"] = "unknown"
        node["decayed_at"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        return True
    return False


def decay_edge(edge, now):
    """Edges decay the same way: verified needs fresh evidence."""
    if edge.get("status") != "verified":
        return False
    last = parse_ts(edge.get("last_verified_at"))
    # Edges inherit a 24h freshness window unless they carry their own.
    stale_after = int(edge.get("stale_after_seconds", 86_400))
    if last is None or (now - last).total_seconds() > stale_after or not edge.get("evidence_ref"):
        edge["status"] = "unprobed"
        edge["decayed_at"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        return True
    return False


def apply_decay(dataset, now=None):
    """Decay every node and edge in a v2 dataset. Returns change counts."""
    now = now or datetime.now(timezone.utc)
    changed_nodes = sum(1 for n in dataset.get("nodes", []) if decay_node(n, now))
    changed_edges = sum(1 for e in dataset.get("edges", []) if decay_edge(e, now))
    return {"nodes_decayed": changed_nodes, "edges_decayed": changed_edges}


def compute_counts(dataset):
    """The ONLY source of header counts. Derived, never stored by hand."""
    nodes = dataset.get("nodes", [])
    edges = dataset.get("edges", [])
    alerts = dataset.get("alerts", [])
    by_status = {}
    for n in nodes:
        by_status[n.get("observed_status", "unprobed")] = (
            by_status.get(n.get("observed_status", "unprobed"), 0) + 1
        )
    return {
        "node_count": len(nodes),
        "edge_count": len(edges),
        "alert_count": len(alerts),
        "alerts_open": sum(1 for a in alerts if a.get("status") == "open"),
        "alerts_blocked": sum(1 for a in alerts if a.get("status") == "blocked"),
        "alerts_fixed": sum(1 for a in alerts if a.get("status") == "fixed"),
        "nodes_by_status": by_status,
    }


def refresh_lineage(dataset, now=None):
    """Recompute lineage counts from the data. Kills the 125/295 problem."""
    now = now or datetime.now(timezone.utc)
    lineage = dataset.setdefault("lineage", {})
    counts = compute_counts(dataset)
    lineage["node_count"] = counts["node_count"]
    lineage["edge_count"] = counts["edge_count"]
    lineage["counts_computed_at"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    lineage["source_status"] = "fresh" if counts["nodes_by_status"].get(
        "unprobed", 0
    ) < counts["node_count"] else "stale"
    return lineage


def validate(dataset):
    """Return a list of problems. Empty list = the dataset is honest."""
    problems = []
    nodes = dataset.get("nodes", [])
    edges = dataset.get("edges", [])
    alerts = dataset.get("alerts", [])

    ids = [n.get("id") for n in nodes]
    if len(ids) != len(set(ids)):
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        problems.append(f"duplicate node ids: {dupes}")
    idset = set(ids)

    for n in nodes:
        if n.get("observed_status") not in VALID_NODE_STATUS:
            problems.append(f"node {n.get('id')}: bad observed_status {n.get('observed_status')!r}")
        if n.get("status_confidence") not in VALID_CONFIDENCE:
            problems.append(f"node {n.get('id')}: bad status_confidence {n.get('status_confidence')!r}")
        # The core rule: a claimed state without evidence is a lie.
        if n.get("observed_status") in ("live", "degraded", "down"):
            if not n.get("last_verified_at") or not n.get("evidence_ref"):
                problems.append(
                    f"node {n.get('id')}: claims '{n.get('observed_status')}' "
                    "without last_verified_at + evidence_ref"
                )

    for e in edges:
        for endpoint in ("from", "to"):
            if e.get(endpoint) not in idset:
                problems.append(f"edge {e.get('id')}: {endpoint}={e.get(endpoint)!r} is not a node")
        if e.get("status") not in VALID_EDGE_STATUS:
            problems.append(f"edge {e.get('id')}: bad status {e.get('status')!r}")
        if e.get("status") == "verified" and not e.get("evidence_ref"):
            problems.append(f"edge {e.get('id')}: verified without evidence_ref")

    for a in alerts:
        for field in ALERT_REQUIRED:
            if not a.get(field):
                problems.append(f"alert {a.get('alert_id')}: missing {field}")

    # Hand-typed counts anywhere in lineage must match the computed counts.
    lineage = dataset.get("lineage") or {}
    counts = compute_counts(dataset)
    for key in ("node_count", "edge_count"):
        if key in lineage and lineage[key] != counts[key]:
            problems.append(
                f"lineage {key}={lineage[key]} but arrays hold {counts[key]} "
                "(hand-typed count mismatch)"
            )
    if dataset.get("header_claim"):
        problems.append("v1 'header_claim' present in a v2 dataset — remove it; counts are computed")

    return problems


def upstream_walk(dataset, symptom_id):
    """Troubleshooting walk: from the symptom node, walk upstream edges
    (edge.from -> edge.to means `from` feeds/supports `to`; upstream of a
    node = the nodes pointing INTO it). Returns the ordered path and the
    first broken/unprobed edge or node — where the work actually is.
    """
    nodes = {n["id"]: n for n in dataset.get("nodes", [])}
    if symptom_id not in nodes:
        return {"error": f"unknown node: {symptom_id}"}
    incoming = {}
    for e in dataset.get("edges", []):
        incoming.setdefault(e["to"], []).append(e)

    path, visited, stop = [], set(), None
    # If the symptom itself is unprobed, its own state is the unknown —
    # probe it first before walking anywhere.
    if nodes[symptom_id].get("observed_status") == "unprobed":
        return {
            "symptom": symptom_id,
            "path": [{"node": symptom_id, "observed_status": "unprobed"}],
            "stop": {"at_node": symptom_id,
                     "reason": "symptom node itself is unprobed — probe it first"},
            "verdict": "stop point found",
        }
    queue = [symptom_id]
    while queue and stop is None:
        current = queue.pop(0)
        if current in visited:
            continue
        visited.add(current)
        node = nodes[current]
        path.append({"node": current, "observed_status": node.get("observed_status")})
        if node.get("observed_status") in ("down", "unprobed") and current != symptom_id:
            stop = {"at_node": current, "reason": f"upstream node is {node.get('observed_status')}"}
            break
        for edge in sorted(incoming.get(current, []), key=lambda e: e.get("triage_order", 99)):
            if edge.get("status") in ("broken", "blocked", "unprobed"):
                stop = {
                    "at_edge": edge.get("id"),
                    "from": edge.get("from"),
                    "to": edge.get("to"),
                    "reason": f"edge is {edge.get('status')}",
                    "probe_command": edge.get("probe_command"),
                }
                path.append({"edge": edge.get("id"), "status": edge.get("status")})
                break
            queue.append(edge["from"])
    return {"symptom": symptom_id, "path": path, "stop": stop,
            "verdict": "stop point found" if stop else "upstream chain fully verified"}


def load(path):
    with open(path) as fh:
        return json.load(fh)


def save(dataset, path):
    refresh_lineage(dataset)
    with open(path, "w") as fh:
        json.dump(dataset, fh, indent=2)
        fh.write("\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="CR8 mesh core logic")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("summary", "decay", "validate"):
        p = sub.add_parser(name)
        p.add_argument("file")
        p.add_argument("--now", help="ISO timestamp to evaluate decay at (default: now)")
        p.add_argument("--write", action="store_true", help="decay: write changes back")
    args = ap.parse_args()
    data = load(args.file)
    now = parse_ts(args.now) if getattr(args, "now", None) else datetime.now(timezone.utc)

    if args.cmd == "summary":
        print(json.dumps(compute_counts(data), indent=2))
    elif args.cmd == "decay":
        result = apply_decay(data, now)
        print(json.dumps(result, indent=2))
        if args.write:
            save(data, args.file)
            print(f"written: {args.file}")
    elif args.cmd == "validate":
        problems = validate(data)
        if problems:
            print("INVALID:")
            for prob in problems:
                print(f"  - {prob}")
            sys.exit(1)
        print("valid — counts:", json.dumps(compute_counts(data)))
