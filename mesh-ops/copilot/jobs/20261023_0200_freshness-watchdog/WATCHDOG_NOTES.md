# Freshness watchdog

To install as a systemd **user** timer, copy `freshness_watchdog.py` to
`~/.local/bin/`. Create `~/.config/systemd/user/freshness-watchdog.service`:

```ini
[Unit]
Description=Report connector and Claude Sessions freshness

[Service]
Type=oneshot
ExecStart=/usr/bin/python3 %h/.local/bin/freshness_watchdog.py
```

Create `~/.config/systemd/user/freshness-watchdog.timer`:

```ini
[Unit]
Description=Daily freshness watchdog

[Timer]
OnCalendar=*-*-* 06:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

Then run `systemctl --user daemon-reload` and
`systemctl --user enable --now freshness-watchdog.timer`. Reports are available
with `journalctl --user -u freshness-watchdog.service`.

**Limits:** Checks only immediate `.md` files and their mtimes, not contents or
subdirectories. Uses systemd's last exit timestamp/result and local wall-clock
time; it does not verify sync correctness or account for clock skew.
