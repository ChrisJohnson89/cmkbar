# cmkview

A lightweight macOS menu bar app that monitors a [CheckMK](https://checkmk.com/) server and displays current problems in a floating popup table.

Inspired by [Nagstamon](https://github.com/henriwahl/nagstamon) but built from scratch — single backend (CheckMK), native macOS menu bar, minimal dependencies.

## Requirements

- macOS
- Python 3.11+
- A CheckMK user account with access to the `nagstamon_hosts` and `nagstamon_svc` views

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
2. Polls the `nagstamon_hosts` and `nagstamon_svc` Multisite views at the configured interval
3. Displays a problem count in the menu bar (✓ when clear, ⚠ N when problems exist)
4. Click **Show Problems** to open a floating table — rows are coloured red (CRIT), yellow (WARN), or orange (UNKNOWN)

## License

MIT
