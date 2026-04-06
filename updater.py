"""Silent GitHub release checker for cmkview."""

from __future__ import annotations

import requests


LATEST_RELEASE_URL = "https://api.github.com/repos/ChrisJohnson89/cmkview/releases/latest"


def _parse_version(version: str) -> tuple[int, ...]:
    normalized = version.strip().lstrip("vV")
    normalized = normalized.split("-", 1)[0].split("+", 1)[0]
    return tuple(int(part) for part in normalized.split("."))


def check_for_update(current_version: str) -> dict | None:
    try:
        response = requests.get(LATEST_RELEASE_URL, timeout=5)
        response.raise_for_status()
        release = response.json()

        latest_version = str(release.get("tag_name", "")).strip().lstrip("vV")
        if not latest_version:
            return None

        if _parse_version(latest_version) <= _parse_version(current_version):
            return None

        return {
            "version": latest_version,
            "url": release.get("html_url", ""),
            "notes": release.get("body", "") or "",
        }
    except Exception:
        return None
