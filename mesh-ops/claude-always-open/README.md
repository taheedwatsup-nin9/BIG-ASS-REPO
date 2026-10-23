# Claude Always Open — v2 (built to Taheed's walkthrough, 2026-10-22)

## The model (how the path actually works)
- The Lenovo has Claude Desktop + the Claude CLI.
- In a terminal, Taheed ran `claude --remote-control`, authenticated
  through his Claude subscription in the browser, got redirected back
  to the CLI, and the CLI printed a **session URL**
  (https://claude.ai/code/session_...).
- **That URL is the comm path into that live CLI terminal on the
  Lenovo.** MUZI opens it (with MUZI's own claude.ai viewer login) and
  talks to Claude there; Claude works the machine.
- Taheed's end state: he just turns the computer on. The session comes
  up by itself, and MUZI gets alerted that the machine booted.

## What this package does (basic config, no AI in the loop)
- `claude_always_open.py` — a Python daemon that:
  1. launches `claude --remote-control` as a child process,
  2. captures the session URL from the CLI's output into
     `~/.local/state/claude-always-open/status.json` (with boot time),
  3. sends a boot alert ping to the MUZI bridge webhook
     (`MUZI_BRIDGE_URL` + `MUZI_BRIDGE_SECRET`, read from the canonical
     env file `~/.config/cr8mor/env` — values placed there by the
     Claude lane; **no values in this code, ever**),
  4. restarts the CLI with backoff if it dies; if no URL appears within
     120 s (CLI wants an interactive re-login), it reports
     `needs-login` honestly instead of faking "up".
- `claude-always-open.service` — systemd USER unit running the daemon,
  restarting it if it exits. With linger enabled once, the chain starts
  at boot before any desktop login.

## Credentials & exposure (Taheed's constraints)
- The CLI's subscription sign-in already lives on the machine from his
  one interactive login (`~/.claude`); the daemon inherits it by running
  as his user. Nothing is embedded, copied, or printed.
- The daemon opens NO listening sockets. The only outbound call is the
  boot alert to his own n8n bridge. Session URL travels only in that
  alert and the local status file — never in this repo.

## Install (Lenovo side, e.g. by Claude in the lane)
```bash
mkdir -p ~/.local/share/claude-always-open ~/.config/systemd/user
cp claude_always_open.py ~/.local/share/claude-always-open/
cp claude-always-open.service ~/.config/systemd/user/
chmod 700 ~/.local/share/claude-always-open/claude_always_open.py
# if `claude` isn't at ~/.local/bin/claude, set CLAUDE_BIN in the env file
systemctl --user daemon-reload
systemctl --user enable --now claude-always-open.service
sudo loginctl enable-linger taheed   # one-time: start at boot, pre-login
```

## Verify
```bash
systemctl --user status claude-always-open.service
cat ~/.local/state/claude-always-open/status.json
# expect: state "up", a session_url, and the boot alert received MUZI-side.
# Full test: reboot, touch nothing, confirm status.json refreshes with a
# new boot_ts and MUZI gets the ping.
```

Supersedes v1 (which wrongly assumed a pre-existing remote-control unit
to supervise; the real source of the session is the CLI command itself).
