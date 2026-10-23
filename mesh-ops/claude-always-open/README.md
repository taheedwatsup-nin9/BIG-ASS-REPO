# Claude Always Open — install notes (Lenovo side)

Purpose (Taheed, 2026-10-22): when the Lenovo reboots, Claude comes back on
its own — no login from Taheed, ever — so MUZI can reach the Claude lane
whenever the machine is on.

## What it is
- `claude_always_open.py` — a watchdog that supervises the existing
  `claude-remote-control` user service: if the unit or the claude process
  dies (or never starts after a reboot), it restarts it, with backoff.
- `claude-always-open.service` — a systemd USER unit that runs the
  watchdog and restarts the watchdog itself if it ever exits.
- Health lands at `~/.local/state/claude-always-open/status.json`.

## Credentials & exposure (Taheed's constraints, 2026-10-22)
- **No credentials in the script, the unit, or this folder.** The watchdog
  runs as Taheed's user; Claude Code's own sign-in already lives in
  `~/.claude` on the machine and is picked up from there. Nothing to log
  into after a reboot — the session he already has just stays alive.
  (This matches the approved secrets standard: values live in the one
  protected place on the machine, never pasted into code.)
- **Nothing public-facing.** The watchdog opens NO sockets. It talks only
  to the local systemd user manager. The Claude lane itself stays
  reachable the same ways as today (Claude Remote session; tailnet-only
  services) — no new ports, no public exposure.

## Install (run on the Lenovo, e.g. by Claude in the lane)
```bash
mkdir -p ~/.local/share/claude-always-open ~/.config/systemd/user
cp claude_always_open.py ~/.local/share/claude-always-open/
cp claude-always-open.service ~/.config/systemd/user/
chmod 700 ~/.local/share/claude-always-open/claude_always_open.py
systemctl --user daemon-reload
systemctl --user enable --now claude-always-open.service
# one-time, so user services start at boot even before a desktop login:
sudo loginctl enable-linger taheed
```

## Verify
```bash
systemctl --user status claude-always-open.service
cat ~/.local/state/claude-always-open/status.json   # state should read "up"
# reboot test: restart the machine, touch nothing, then re-check both —
# the Claude lane should be back with zero logins.
```

Transport note: this folder reaches the Lenovo the same way as the other
mesh-ops work — via BIG-ASS-REPO (mesh-ops/claude-always-open/) and a
pull on the Lenovo side; sha256 the files before installing.
