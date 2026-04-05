# cmkview

A lightweight macOS app that monitors a [CheckMK](https://checkmk.com/) server and displays current problems in a grouped incident dashboard.

Built from scratch — single backend (CheckMK), native macOS app, minimal dependencies. No custom CheckMK views required.

## Requirements

- macOS
- Python 3.11+
- A CheckMK user account (any user that can see problems in the web UI)

## Configuration

Create `~/.cmkview.toml`:

```toml
url = "https://mon.example.com/mysite"
username = "myuser"
password = "mypassword"
interval = 60
```

| Key        | Required | Default | Description                          |
|------------|----------|---------|--------------------------------------|
| `url`      | yes      |         | CheckMK site URL (no trailing slash) |
| `username` | yes      |         | CheckMK username                     |
| `password` | yes      |         | CheckMK password                     |
| `interval` | no       | 60      | Poll interval in seconds             |

## Run from source

```bash
pip install -r requirements.txt
python cmkview.py
```

## Build the .app

```bash
pip install -r requirements.txt
python setup.py py2app
```

The app bundle is created at `dist/cmkview.app`. Drag it to `/Applications` and add it to **System Settings → General → Login Items** to start on boot.

## How it works

1. Logs into CheckMK via cookie auth (`/check_mk/login.py`)
2. Polls the built-in `hostproblems` and `svcproblems` Multisite views at the configured interval
3. Displays a problem count in the menu bar (✓ when clear, ⚠ N when problems exist)
4. Opens a dashboard window with problems grouped by category (memory, disk, network, services, etc.)
5. Click state badges (DOWN/CRIT/WARN/UNKN) to filter by severity, toggle Hide Ack to filter acknowledged problems

## License

MIT
