#!/usr/bin/env python3
"""
Probe runner — the observation layer.

Runs each probe_command defined on v2 nodes/edges, records the result as
evidence (JSONL next to the dataset), and updates the node's observation
fields. This is the ONLY way a status becomes "live": a probe ran, it
exited 0, and the evidence is on file.

Safety shape:
  - --dry-run lists every probe without executing anything (default when
    no mode flag is given).
  - Commands come from the dataset file YOU pass in — never from the network.
  - Each probe has a hard timeout (default 15s). Output is truncated.

Usage:
    python3 probe_runner.py mesh-context-v2.json --dry-run
    python3 probe_runner.py mesh-context-v2.json --run --only n8n,supabase
    python3 probe_runner.py mesh-context-v2.json --run   # all defined probes
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mesh_logic import iso_now, load, save  # noqa: E402


def iter_probes(dataset):
    for node in dataset.get("nodes", []):
        for probe in node.get("probes", []):
            if probe.get("command"):
                yield ("node", node["id"], node, probe)
    for edge in dataset.get("edges", []):
        if edge.get("probe_command"):
            yield ("edge", edge["id"], edge, {"command": edge["probe_command"]})


def run_probe(command, timeout):
    started = iso_now()
    try:
        proc = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return {
            "command": command, "started_at": started,
            "exit_code": proc.returncode,
            "stdout_tail": proc.stdout.strip()[-500:],
            "stderr_tail": proc.stderr.strip()[-500:],
            "ok": proc.returncode == 0,
        }
    except subprocess.TimeoutExpired:
        return {"command": command, "started_at": started, "exit_code": None,
                "stdout_tail": "", "stderr_tail": f"timeout after {timeout}s", "ok": False}


def main():
    ap = argparse.ArgumentParser(description="Run mesh probes, record evidence")
    ap.add_argument("file")
    ap.add_argument("--run", action="store_true", help="actually execute probes")
    ap.add_argument("--dry-run", action="store_true", help="list probes only (default)")
    ap.add_argument("--only", help="comma-separated node/edge ids to probe")
    ap.add_argument("--timeout", type=int, default=15)
    ap.add_argument("--evidence", help="evidence JSONL path (default: <file>.evidence.jsonl)")
    args = ap.parse_args()

    dataset = load(args.file)
    only = set(args.only.split(",")) if args.only else None
    probes = [p for p in iter_probes(dataset) if only is None or p[1] in only]

    if not probes:
        print("no probes defined in this dataset yet — add probe commands in the "
              "VS Code session (nodes[].probes[].command / edges[].probe_command)")
        return
    if not args.run:
        print(f"{len(probes)} probe(s) defined (dry run — nothing executed):")
        for kind, pid, _owner, probe in probes:
            print(f"  [{kind} {pid}] {probe['command']}")
        return

    evidence_path = Path(args.evidence or (args.file + ".evidence.jsonl"))
    results = []
    with open(evidence_path, "a") as ev:
        for kind, pid, owner, probe in probes:
            result = run_probe(probe["command"], args.timeout)
            result.update({"target_kind": kind, "target_id": pid})
            ev.write(json.dumps(result) + "\n")
            results.append(result)
            now = iso_now()
            ref = f"{evidence_path.name} @ {now}"
            if kind == "node":
                if result["ok"]:
                    owner["observed_status"] = "live"
                    owner["status_confidence"] = "verified"
                    owner["last_verified_at"] = now
                    owner["verified_by"] = "probe_runner"
                    owner["evidence_ref"] = ref
                else:
                    owner["observed_status"] = "down"
                    owner["status_confidence"] = "verified"
                    owner["last_verified_at"] = now
                    owner["verified_by"] = "probe_runner"
                    owner["evidence_ref"] = ref
                probe["last_success_at"] = now if result["ok"] else probe.get("last_success_at")
                probe["last_failure_at"] = probe.get("last_failure_at") if result["ok"] else now
                probe["exit_code"] = result["exit_code"]
            else:  # edge
                owner["status"] = "verified" if result["ok"] else "broken"
                owner["last_verified_at"] = now
                owner["evidence_ref"] = ref
            print(f"  [{'OK ' if result['ok'] else 'FAIL'}] {kind} {pid}: exit={result['exit_code']}")

    save(dataset, args.file)
    ok = sum(1 for r in results if r["ok"])
    print(f"\n{ok}/{len(results)} probes passed. Evidence: {evidence_path}")
    print(f"dataset updated in place: {args.file}")


if __name__ == "__main__":
    main()
