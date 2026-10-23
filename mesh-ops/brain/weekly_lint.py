#!/usr/bin/env python3
"""Report-only candidate lint for stale claims, opposing status facts, and orphan notes.

Stale flags use dated status lines; contradiction flags require simple opposing states
for the same subject; orphans have no inbound internal link. These are candidates, not
semantic verdicts. The script never writes or repairs notes.
"""

from __future__ import annotations

import argparse
import os
import posixpath
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

SKIP_DIRS = {
    ".agents",
    ".claude",
    ".copilot",
    ".git",
    ".makemd",
    ".obsidian",
    ".opencode",
    ".smart-env",
    ".space",
    ".smtcmp_json_db",
    ".smtcmp_vector_db",
    ".vector_store",
    ".vault-operator",
    "_to_delete",
    "04-Archive",
    "archive",
}
FRONTMATTER_DATE_RE = re.compile(r"(?m)^(?:updated|modified):\s*['\"]?(\d{4}-\d{2}-\d{2})")
FRONTMATTER_ALIASES_RE = re.compile(r"(?m)^aliases:\s*\n((?:\s*-\s*.*\n)+)")
FRONTMATTER_INLINE_ALIASES_RE = re.compile(r"(?m)^aliases:\s*\[([^\]]*)\]")
AS_OF_RE = re.compile(r"\bas of\s+(20\d{2}-\d{2}-\d{2})\b", re.IGNORECASE)
STALE_STATUS_RE = re.compile(
    r"\b(?:currently|still\s+(?:active|running|enabled|live|online|offline)|"
    r"(?:is|are|remains)\s+(?:active|running|enabled|disabled|live|online|offline|"
    r"deployed|available|unavailable))\b",
    re.IGNORECASE,
)
FACT_RE = re.compile(
    r"^\s*(?:[-*]\s*)?(?P<entity>[A-Za-z0-9][A-Za-z0-9_./-]*(?:\s+[A-Za-z0-9][A-Za-z0-9_./-]*){0,4})"
    r"\s+(?:is|are|remains|stays)\s+(?P<state>active|inactive|enabled|disabled|running|stopped|"
    r"live|offline|online|available|unavailable|connected|disconnected|supported|unsupported|"
    r"present|missing|configured|unconfigured)\b",
    re.IGNORECASE,
)
WIKILINK_RE = re.compile(r"!?\[\[([^\]]+)\]\]")
MARKDOWN_LINK_RE = re.compile(r"!?\[([^\]]*)\]\(([^)]+)\)")
GENERIC_ENTITIES = {"i", "we", "you", "it", "this", "that", "service", "system", "the"}
CONFLICTING_STATES = {
    frozenset(("active", "inactive")),
    frozenset(("enabled", "disabled")),
    frozenset(("running", "stopped")),
    frozenset(("live", "offline")),
    frozenset(("online", "offline")),
    frozenset(("available", "unavailable")),
    frozenset(("connected", "disconnected")),
    frozenset(("supported", "unsupported")),
    frozenset(("present", "missing")),
    frozenset(("configured", "unconfigured")),
}


def active_markdown_files(root: Path) -> tuple[list[Path], int]:
    files = []
    skipped_symlinks = 0
    def raise_walk_error(error: OSError) -> None:
        raise error

    for current, dirs, names in os.walk(root, onerror=raise_walk_error):
        dirs[:] = sorted(name for name in dirs if name not in SKIP_DIRS)
        current_path = Path(current)
        for name in names:
            if not name.endswith(".md"):
                continue
            path = current_path / name
            if path.is_symlink():
                skipped_symlinks += 1
            elif path.is_file():
                files.append(path)
    return sorted(files), skipped_symlinks


def updated_date(path: Path, text: str) -> date:
    match = FRONTMATTER_DATE_RE.search(text[:4096])
    if match:
        try:
            metadata_date = date.fromisoformat(match.group(1))
        except ValueError:
            metadata_date = date.min
    else:
        metadata_date = date.min
    file_date = datetime.fromtimestamp(path.stat().st_mtime).date()
    return max(metadata_date, file_date)


def prose_lines(text: str):
    fenced = False
    for number, line in enumerate(text.splitlines(), 1):
        stripped = line.lstrip()
        if stripped.startswith(("```", "~~~")):
            fenced = not fenced
            continue
        if fenced or stripped.startswith(">"):
            continue
        cleaned = re.sub(r"`[^`]*`", "", line).strip()
        if cleaned:
            yield number, cleaned


def stale_claims(path: Path, text: str, cutoff: date) -> set[tuple[str, int]]:
    note_date = updated_date(path, text)
    candidates = set()
    for line_number, line in prose_lines(text):
        old_as_of = False
        for value in AS_OF_RE.findall(line):
            try:
                old_as_of = old_as_of or date.fromisoformat(value) < cutoff
            except ValueError:
                continue
        old_note = note_date < cutoff
        if old_as_of or (old_note and STALE_STATUS_RE.search(line)):
            candidates.add((path.as_posix(), line_number))
    return candidates


def contradiction_facts(path: Path, text: str) -> dict[str, list[tuple[str, int, str]]]:
    facts: dict[str, list[tuple[str, int, str]]] = defaultdict(list)
    for line_number, line in prose_lines(text):
        match = FACT_RE.match(line)
        if not match:
            continue
        entity = re.sub(r"\s+", " ", match.group("entity").strip().lower())
        entity = re.sub(r"^(?:a|an|the)\s+", "", entity)
        if entity in GENERIC_ENTITIES:
            continue
        facts[entity].append((path.as_posix(), line_number, match.group("state").lower()))
    return facts


def contradiction_pair_count(
    facts_by_entity: dict[str, list[tuple[str, int, str]]]
) -> int:
    count = 0
    for facts in facts_by_entity.values():
        locations_by_state: dict[str, set[tuple[str, int]]] = defaultdict(set)
        for path, line, state in facts:
            locations_by_state[state].add((path, line))
        for first, second in CONFLICTING_STATES:
            count += len(locations_by_state[first]) * len(locations_by_state[second])
    return count


def frontmatter_aliases(text: str) -> list[str]:
    if not text.startswith("---"):
        return []
    sections = text.split("---", 2)
    if len(sections) < 3:
        return []
    frontmatter = sections[1]
    match = FRONTMATTER_ALIASES_RE.search(frontmatter)
    if match:
        return [
            re.sub(r"^\s*-\s*", "", line).strip().strip("'\"")
            for line in match.group(1).splitlines()
            if line.strip()
        ]
    match = FRONTMATTER_INLINE_ALIASES_RE.search(frontmatter)
    if match:
        return [item.strip().strip("'\"") for item in match.group(1).split(",") if item.strip()]
    return []


def add_note_keys(index: dict[str, set[str]], rel_path: str, text: str) -> None:
    path = Path(rel_path)
    keys = {rel_path, rel_path[:-3], path.name, path.stem}
    keys.update(frontmatter_aliases(text))
    for key in keys:
        index[key.casefold()].add(rel_path)


def resolve_note_target(source: str, raw_target: str, index: dict[str, set[str]]) -> set[str]:
    target = raw_target.split("|", 1)[0].split("#", 1)[0].strip().replace("\\", "/")
    if not target:
        return {source}
    relative = posixpath.normpath(posixpath.join(posixpath.dirname(source), target))
    candidates = {
        target,
        target.removesuffix(".md"),
        relative,
        relative.removesuffix(".md"),
        f"{relative}.md",
        posixpath.basename(target),
        posixpath.basename(target).removesuffix(".md"),
    }
    resolved = set()
    for candidate in candidates:
        resolved.update(index.get(candidate.casefold(), set()))
    return resolved


def link_audit(
    contents: dict[str, str], index: dict[str, set[str]]
) -> tuple[int, int, int, int, int]:
    incoming = set()
    total = resolved_count = ambiguous_count = 0

    def record(source: str, raw_target: str) -> None:
        nonlocal total, resolved_count, ambiguous_count
        total += 1
        targets = resolve_note_target(source, raw_target, index)
        if not targets:
            return
        resolved_count += 1
        if len(targets) > 1:
            ambiguous_count += 1
        incoming.update(target for target in targets if target != source)

    for source, text in contents.items():
        for match in WIKILINK_RE.finditer(text):
            record(source, match.group(1))
        for match in MARKDOWN_LINK_RE.finditer(text):
            target = match.group(2).strip()
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            record(source, target.split("#", 1)[0])
    return len(set(contents) - incoming), total, resolved_count, total - resolved_count, ambiguous_count


def lint(vault_dir: Path, as_of: date, stale_days: int) -> dict[str, int]:
    if not vault_dir.is_dir():
        raise NotADirectoryError(f"vault directory not found: {vault_dir}")
    files, skipped_symlinks = active_markdown_files(vault_dir)
    cutoff = as_of - timedelta(days=stale_days)
    stale = set()
    facts_by_entity: dict[str, list[tuple[str, int, str]]] = defaultdict(list)
    contents = {}
    note_index: dict[str, set[str]] = defaultdict(set)
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        rel_path = path.relative_to(vault_dir).as_posix()
        contents[rel_path] = text
        add_note_keys(note_index, rel_path, text)
        stale.update(stale_claims(path, text, cutoff))
        for entity, facts in contradiction_facts(path.relative_to(vault_dir), text).items():
            facts_by_entity[entity].extend(facts)

    orphan_count, links_seen, links_resolved, links_unresolved, links_ambiguous = link_audit(
        contents, note_index
    )
    return {
        "notes_scanned": len(files),
        "symlink_notes_skipped": skipped_symlinks,
        "internal_links_seen": links_seen,
        "internal_links_resolved": links_resolved,
        "internal_links_unresolved": links_unresolved,
        "ambiguous_internal_links": links_ambiguous,
        "orphan_candidates": orphan_count,
        "stale_claim_candidates": len(stale),
        "contradiction_pairs": contradiction_pair_count(facts_by_entity),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault-dir", type=Path, required=True, help="Read-only vault copy to scan")
    parser.add_argument("--stale-days", type=int, default=90)
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    parser.add_argument("--dry-run", action="store_true", help="Required; report only, never edit notes")
    args = parser.parse_args()
    if not args.dry_run:
        parser.error("this linter is report-only; pass --dry-run")
    if args.stale_days < 1:
        parser.error("--stale-days must be a positive integer")

    try:
        counts = lint(args.vault_dir.resolve(), args.as_of, args.stale_days)
    except (OSError, RuntimeError, ValueError, TypeError) as error:
        print(f"LINT ERROR: {error}", file=sys.stderr)
        return 2

    print("REPORT-ONLY DRY RUN; no vault files changed.")
    print(f"as_of={args.as_of.isoformat()} stale_days={args.stale_days}")
    for key, value in counts.items():
        print(f"{key}={value}")
    print("Contradictions and stale claims are heuristic candidates for human review.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
