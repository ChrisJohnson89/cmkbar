# cmkview

macOS app for monitoring a CheckMK server. A lightweight, CheckMK-focused alternative to Nagstamon.

## Stack

- **PyObjC** (AppKit + WebKit) — native macOS window, menu bar icon, WKWebView dashboard
- **requests** — HTTP session for CheckMK polling
- **tomllib** (stdlib, Python 3.11+) — config parsing

## CheckMK integration

- Cookie-based auth: `POST /check_mk/login.py` with `_username`, `_password`, `_login=1`
- Poll two built-in Multisite views with `output_format=python`:
  - `view.py?view_name=hostproblems` — host problems
  - `view.py?view_name=svcproblems` — service problems
- No REST API key needed — regular user login
- No custom views required — uses CheckMK's built-in views

## Config

Single file at `~/.cmkview.toml`:

```toml
url = "https://mon.example.com/mysite"
username = "myuser"
password = "mypassword"
interval = 60
```

## UI behaviour

- Menu bar icon shows problem count (✓ when clear, ⚠ N when issues exist)
- Full app window with grouped incident dashboard
- Problems grouped by category (memory, disk, network, hardware, services, system)
- Clickable state badges (DOWN/CRIT/WARN/UNKN) to filter by severity
- Hide Ack toggle to filter acknowledged problems
- Expand groups → hosts → individual services
- UI state (collapsed groups, filters) persists across poll refreshes

## Packaging

- `py2app` to build a standalone `.app` bundle
- Distribute as a zipped `.app` via GitHub Releases

## What we are NOT doing

- No Qt / PyQt
- No other monitoring backends
- No cross-platform support
- No sound alerts, RDP/VNC launchers, or settings GUI
