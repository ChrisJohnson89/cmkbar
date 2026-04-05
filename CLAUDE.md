# cmkbar

macOS menu bar app for monitoring a CheckMK server. Not a Nagstamon fork — a fresh rewrite focused solely on CheckMK.

## Stack

- **rumps** — macOS menu bar icon and status display
- **pywebview** — floating HTML popup window for the problem table
- **requests** — HTTP session for CheckMK polling
- **tomllib** (stdlib, Python 3.11+) — config parsing

## CheckMK integration

- Cookie-based auth: `POST /check_mk/login.py` with `_username`, `_password`, `_login=1`
- Poll two Multisite views with `output_format=json`:
  - `view.py?view_name=nagstamon_hosts` — host problems
  - `view.py?view_name=nagstamon_svc` — service problems
- No REST API key needed — regular user login
- The user's CheckMK account must have permission to see the nagstamon views

## Config

Single file at `~/.cmkbar.toml`:

```toml
url = "https://mon.example.com/mysite"
username = "myuser"
password = "mypassword"
interval = 60
```

## UI behaviour

- Menu bar shows a check mark when clean, warning icon + problem count when issues exist
- Clicking the icon opens a pywebview popup with a scrollable HTML table
- Table columns: Host, Service, State, Duration, Attempt, Message
- Rows coloured red (CRIT/DOWN), yellow (WARN), or orange (UNKNOWN/UNREACH)
- Click away or close to dismiss

## Packaging

- `py2app` to build a standalone `.app` bundle
- Distribute as a zipped `.app` via GitHub Releases

## What we are NOT doing

- No Qt / PyQt
- No other monitoring backends
- No cross-platform support
- No sound alerts, RDP/VNC launchers, or settings GUI
