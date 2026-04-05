"""Load cmkbar configuration from ~/.cmkbar.toml."""

import os
import sys
import tomllib


DEFAULT_PATH = os.path.expanduser("~/.cmkbar.toml")

DEFAULTS = {
    "interval": 60,
}


def load(path: str | None = None) -> dict:
    path = path or DEFAULT_PATH
    if not os.path.exists(path):
        print(f"Config not found: {path}", file=sys.stderr)
        print("Create ~/.cmkbar.toml with url, username, and password.", file=sys.stderr)
        sys.exit(1)

    with open(path, "rb") as f:
        cfg = tomllib.load(f)

    for key in ("url", "username", "password"):
        if key not in cfg:
            print(f"Missing required config key: {key}", file=sys.stderr)
            sys.exit(1)

    # Strip trailing slash from URL
    cfg["url"] = cfg["url"].rstrip("/")

    for k, v in DEFAULTS.items():
        cfg.setdefault(k, v)

    return cfg
