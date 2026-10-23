"""Build the Knowledge Portal workbook from rclone lsjson dumps (one per PARA root)."""
import json, os, re, sys
from collections import Counter
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

S = sys.argv[1]
OUT = sys.argv[2]
PARA = {"01_Projects": "Projects", "02_Areas": "Areas", "03_Resources": "Resources", "04_Archives": "Archives"}
JUNK = re.compile(r"(^|/)(\.DS_Store|\._|\.Trash|\.cache|\.musicapps-project-folder|desktop\.ini)", re.I)

# Skill batches: first match wins, order = priority.
BATCHES = [
    ("Linux CLI & Shell", re.compile(r"\b(cli|linux|bash|shell|terminal|apt|nmap|ubuntu|debian|man[_ -]?learn)|\.sh$", re.I)),
    ("n8n & Automation Flows", re.compile(r"n8n|workflow|zap|webhook", re.I)),
    ("JavaScript (Scripter)", re.compile(r"javascript|\.js$", re.I)),
    ("Python & Script Launchers", re.compile(r"python|\.py$|script|launcher|cron|systemd", re.I)),
    ("Logic Pro & Audio Production", re.compile(r"logic.?pro|scripter|midi|pro.?tools|\bptx\b|\bmix(ing|down)?\b|mastering|bounce|plug-?in|\bdaw\b|audio|acoustic", re.I)),
    ("Agent Skills & Prompts", re.compile(r"skill|prompt|agent|claude|grok|gemini|copilot|hermes|mcp|llm|rag\b", re.I)),
]
VIDEOS = [
    ("Logic Pro & Audio Production", "Can you create custom MIDI FX in Logic Pro with ChatGPT? (Oliver Codd)", "https://youtube.com/shorts/XNMM44rBAVw"),
    ("Logic Pro & Audio Production", "Logic Pro Scripter Hack: Control 10+ Parameters with the Mod Wheel (MusicTechHelpGuy)", "https://youtu.be/nJPP82qxNJw"),
    ("Logic Pro & Audio Production", "The Most Important FREE Script Ever | Logic Pro 11 (Logic Pro Life)", "https://youtu.be/g6lvDz5gzwc"),
    ("Python & Script Launchers", "The Entire History of Programming Languages, Machine Code to Python (Night Shift Professor)", "https://youtu.be/x5V3OB5FJkA"),
    ("Agent Skills & Prompts", "You Need to Learn MCP RIGHT NOW (Cyb3rMaddy)", ""),
]


def link(item):
    mt, i = item.get("MimeType", ""), item.get("ID", "")
    kind = {"document": "document", "spreadsheet": "spreadsheets", "presentation": "presentation"}
    for k, v in kind.items():
        if mt == f"application/vnd.google-apps.{k}":
            return f"https://docs.google.com/{v}/d/{i}/edit"
    if mt == "application/vnd.google-apps.folder":
        return f"https://drive.google.com/drive/folders/{i}"
    return f"https://drive.google.com/file/d/{i}/view"


def load(root):
    p = os.path.join(S, f"ls_{root}.json")
    try:
        with open(p) as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


rows = []
for root, bucket in PARA.items():
    if bucket == "Archives":
        continue
    for it in load(root):
        if JUNK.search(it["Path"]):
            continue
        sub = it["Path"].split("/")
        rows.append([bucket, root, "/".join(sub[:-1]) or "(top)", it["Name"],
                     os.path.splitext(it["Name"])[1].lstrip(".").lower() or it.get("MimeType", "").rsplit(".", 1)[-1],
                     round(it.get("Size", 0) / 1024, 1) if it.get("Size", -1) >= 0 else "", link(it)])
for it in load("root"):
    if not JUNK.search(it["Path"]):
        rows.append(["(Drive root, unfiled)", "", "(top)", it["Name"],
                     os.path.splitext(it["Name"])[1].lstrip(".").lower(), round(it.get("Size", 0) / 1024, 1), link(it)])

batched = []
for r in rows:
    hay = f"{r[2]}/{r[3]}"
    for name, rx in BATCHES:
        if rx.search(hay) and r[4] not in ("wav", "aif", "aiff", "mp3", "flac", "png", "jpg", "jpeg", "mov", "mp4", "tfx"):
            batched.append([name, r[0], r[3], r[2], r[6]])
            break
for b, title, url in VIDEOS:
    batched.append([b, "Video (YouTube)", title, "", url])
batched.sort(key=lambda x: ([n for n, _ in BATCHES].index(x[0]), x[1], x[2]))

arch = Counter()
for it in load("04_Archives"):
    if not it.get("IsDir") and not JUNK.search(it["Path"]):
        arch[os.path.dirname(it["Path"]) or "(top)"] += 1

wb = Workbook()
bold, head = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="2F3B52")


def sheet(ws, header, data, widths):
    ws.append(header)
    for c in ws[1]:
        c.font, c.fill = bold, head
    for d in data:
        ws.append(d)
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions


ws = wb.active
ws.title = "Start Here"
for line in [
    ["CR8MOR Knowledge Portal"],
    ["Central index of Taheed's Drive, organized by PARA (Projects / Areas / Resources / Archives)."],
    ["Built 2026-10-22 by Claude from a live Drive listing. Re-run the builder to refresh; nothing here is edited by hand."],
    [],
    ["Tab", "What it holds"],
    ["Index", "Every file in 01_Projects, 02_Areas, 03_Resources and the Drive root, with a link. Use the filter arrows."],
    ["Skill Batches", "Skill, CLI, script, Logic and agent material grouped into learnable batches, plus saved videos."],
    ["Archives", "File counts per 04_Archives subfolder, top 2 levels only (not listed file by file: backups would drown the index)."],
    [],
    ["Batch", "Items"],
] + [[n, sum(1 for b in batched if b[0] == n)] for n, _ in BATCHES] + [[], ["Index rows", len(rows)]]:
    ws.append(line)
ws["A1"].font = Font(bold=True, size=16)
ws.column_dimensions["A"].width = 32
ws.column_dimensions["B"].width = 100

sheet(wb.create_sheet("Index"), ["PARA", "Root", "Folder", "File", "Type", "KB", "Link"], rows, [14, 14, 50, 50, 8, 9, 60])
sheet(wb.create_sheet("Skill Batches"), ["Batch", "PARA", "Item", "Folder", "Link"], batched, [28, 16, 60, 45, 60])
sheet(wb.create_sheet("Archives"), ["04_Archives subfolder", "Files"], sorted(arch.items()), [70, 10])
wb.save(OUT)
print(f"index={len(rows)} batched={len(batched)} archive_groups={len(arch)}")
