import os
import re
import signal
import sys
import time
import json
import requests

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".watcher_state.json")

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_state(active_file, offset):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump({"active_file": active_file, "offset": offset}, f)
    except Exception:
        pass

# Supabase configuration (to be provided by Muse)
SUPABASE_URL = os.getenv("CONNECTOR_SUPABASE_URL", "TODO")
SUPABASE_KEY = os.getenv("CONNECTOR_SUPABASE_KEY", "TODO")

CHAT_RE = re.compile(r"^BIG ASS CHAT #(\d+)\.md$")
POLL_SECONDS = 1
MAX_READ_BYTES = 1024 * 1024
MAX_BACKOFF_SECONDS = 60

_running = True


def _stop(signum, frame):
    global _running
    _running = False


def get_active_chat_file(directory):
    """Finds the active BIG ASS CHAT #NNNN.md file (highest number, top level only)."""
    best = None
    best_num = -1
    try:
        names = os.listdir(directory)
    except OSError as e:
        print(f"Cannot list {directory}: {e}", file=sys.stderr)
        return None
    for name in names:
        m = CHAT_RE.match(name)
        if m and int(m.group(1)) > best_num:
            best_num = int(m.group(1))
            best = name
    return os.path.join(directory, best) if best else None



WEBHOOK_URL = "https://cr8mor-n8n.zeabur.app/webhook/bac-message"
HEADER_RE = re.compile(r"^(.) \[\d{4}-\d{2}-\d{2} \d{2}:\d{2} [A-Z]+\] (SIGN-IN|UPDATE|SIGN-OUT|message) (.*?)(?: @| RESULT|$)")

def push_to_supabase(entry_text):
    """
    Pushes a new entry to the Supabase bac_messages table via n8n Webhook.
    Must raise on failure so the watcher retries instead of dropping the entry.
    """
    entries = []
    current_entry = None
    
    for line in entry_text.split("\n"):
        m = HEADER_RE.match(line)
        if m:
            if current_entry:
                entries.append(current_entry)
            emoji, kind, author = m.groups()
            current_entry = {
                "author": author.strip(),
                "author_emoji": emoji,
                "author_color": "",
                "kind": kind.lower().replace("-", "_"),
                "body": line + "\n"
            }
        else:
            if current_entry:
                current_entry["body"] += line + "\n"
                if not current_entry["author_color"]:
                    color_m = re.search(r'background:(#[0-9A-Fa-f]{6})', line)
                    if color_m:
                        current_entry["author_color"] = color_m.group(1)
            else:
                if line.strip():
                    entries.append({
                        "author": "System",
                        "author_emoji": "🤖",
                        "author_color": "#CCCCCC",
                        "kind": "message",
                        "body": line + "\n"
                    })
    if current_entry:
        entries.append(current_entry)
        
    for payload in entries:
        payload["body"] = payload["body"].strip()
        print(f"Pushing to Supabase (via Webhook): {payload['author']} - {payload['kind']}")
        response = requests.post(WEBHOOK_URL, json=payload, timeout=10)
        response.raise_for_status()



def read_new_lines(path, offset, flush_partial=False):
    """
    Reads from byte `offset` and returns (text, new_offset, size).

    Only complete lines are returned, so a writer that is mid-append never
    gets a half line (or half a multibyte character) pushed. With
    flush_partial=True the trailing incomplete line is returned too; used
    when this file is being abandoned and no more bytes will arrive.
    If the file is now shorter than `offset` it was truncated or replaced,
    and reading restarts from 0.
    """
    with open(path, "rb") as f:
        size = os.fstat(f.fileno()).st_size
        if size < offset:
            print(f"{os.path.basename(path)} shrank ({offset} -> {size}); rereading from start")
            offset = 0
        if size == offset:
            return "", offset, size
        f.seek(offset)
        data = f.read(min(size - offset, MAX_READ_BYTES))
    if flush_partial and offset + len(data) >= size:
        end = len(data)  # abandoning this file: take the unterminated tail too
    else:
        end = data.rfind(b"\n") + 1
        if end == 0:
            if len(data) < MAX_READ_BYTES:
                return "", offset, size  # no full line yet; wait for the writer
            end = len(data)  # one absurdly long line: don't stall forever
    chunk = data[:end]
    return chunk.decode("utf-8", errors="replace"), offset + end, size


def watch_chat_file(directory):
    """
    Tails the active BAC board.
    When new content is appended, it extracts it and triggers push_to_supabase.
    The offset only advances after a successful push, so nothing is lost on errors.
    """
    state = load_state()
    active_file = state.get("active_file")
    offset = state.get("offset")

    if active_file and not os.path.exists(active_file):
        active_file = None

    while _running and not active_file:
        active_file = get_active_chat_file(directory)
        if not active_file:
            print("No active chat file found; waiting...")
            time.sleep(POLL_SECONDS * 5)
        else:
            try:
                offset = os.path.getsize(active_file)  # start at the end
            except OSError:
                offset = 0

    if not active_file:
        return

    if offset is None:
        try:
            offset = os.path.getsize(active_file)
        except OSError:
            offset = 0

    print(f"Watching file: {active_file} from offset {offset}")
    save_state(active_file, offset)

    backoff = POLL_SECONDS
    while _running:
        try:
            newest = get_active_chat_file(directory)
            rotating = bool(newest) and newest != active_file
            # A vanished active file (moved/deleted) is handled by the OSError path below.

            text, new_offset, _ = read_new_lines(active_file, offset, flush_partial=rotating)
            if text.strip():
                push_to_supabase(text.strip())
            offset = new_offset
            save_state(active_file, offset)
            backoff = POLL_SECONDS

            if rotating and not text:
                # Old file fully drained; the new file is read from byte 0
                # so the handoff entry written at creation is not skipped.
                print(f"Active file changed to {newest}. Rotating watcher...")
                active_file, offset = newest, 0
                continue
            if text:
                continue  # more may be waiting (read is capped); skip the sleep
        except FileNotFoundError:
            newest = get_active_chat_file(directory)
            if newest and newest != active_file:
                print(f"{active_file} vanished; switching to {newest}")
                active_file, offset = newest, 0
            else:
                time.sleep(POLL_SECONDS)
            continue
        except Exception as e:  # push failure, permission error, etc.
            print(f"Watcher error ({type(e).__name__}): {e}; retrying in {backoff}s", file=sys.stderr)
            time.sleep(backoff)
            backoff = min(backoff * 2, MAX_BACKOFF_SECONDS)
            continue

        time.sleep(POLL_SECONDS)

    print("Watcher stopped.")


def default_chat_dir():
    """BAC_CHAT_DIR wins; else the first candidate that actually holds a chat file."""
    env = os.getenv("BAC_CHAT_DIR")
    if env:
        return os.path.abspath(os.path.expanduser(env))
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, ".."),
        os.path.expanduser("~/Desktop/BAC-GROUP"),
    ]
    for c in candidates:
        if get_active_chat_file(c):
            return os.path.abspath(c)
    return os.path.abspath(candidates[0])


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    watch_chat_file(default_chat_dir())
