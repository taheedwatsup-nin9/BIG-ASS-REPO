#!/usr/bin/env python3
"""
Triage walk — use the map as a debugging roadmap.

Start at the symptom node, walk upstream edges, stop at the first broken
or unprobed edge/node. That stop point is the work item — everything
downstream of it is a symptom, not a cause.

Usage:
    python3 triage.py mesh-context-v2.json n8n
    python3 triage.py mesh-context-v2.json lenovo
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mesh_logic import load, upstream_walk  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="Walk upstream from a symptom node")
    ap.add_argument("file")
    ap.add_argument("node", help="symptom node id, e.g. n8n")
    args = ap.parse_args()

    result = upstream_walk(load(args.file), args.node)
    if "error" in result:
        print(result["error"])
        sys.exit(1)
    print(f"symptom: {result['symptom']}")
    for step in result["path"]:
        if "node" in step:
            print(f"  node {step['node']}: {step['observed_status']}")
        else:
            print(f"  edge {step['edge']}: {step['status']}")
    stop = result["stop"]
    if stop:
        print(f"\nSTOP — {result['verdict']}: {stop['reason']}")
        if stop.get("probe_command"):
            print(f"probe to run: {stop['probe_command']}")
        print("flow: observe -> fix -> re-probe (probe_runner.py)")
    else:
        print(f"\n{result['verdict']} — no upstream break found")


if __name__ == "__main__":
    main()
