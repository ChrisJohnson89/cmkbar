"""CheckMK Multisite cookie-auth client."""

import time
import requests


class CheckMKClient:
    def __init__(self, url: str, username: str, password: str):
        self.url = url
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.session.verify = True
        self._logged_in = False

    def login(self):
        r = self.session.post(
            f"{self.url}/check_mk/login.py",
            data={
                "_username": self.username,
                "_password": self.password,
                "_login": "1",
                "_origtarget": "index.py",
            },
        )
        r.raise_for_status()
        if "sid" not in self.session.cookies.get_dict() and "_username" not in r.text:
            raise RuntimeError("Login failed — check credentials")
        self._logged_in = True

    def _ensure_login(self):
        if not self._logged_in:
            self.login()

    def _fetch_view(self, view_name: str) -> list[dict]:
        self._ensure_login()
        params = {
            "view_name": view_name,
            "output_format": "json",
            "lang": "",
            "limit": "hard",
        }
        r = self.session.get(f"{self.url}/check_mk/view.py", params=params)
        if r.status_code == 401 or "login" in r.url:
            # Session expired, re-login and retry once
            self.login()
            r = self.session.get(f"{self.url}/check_mk/view.py", params=params)
        r.raise_for_status()
        rows = r.json()
        if not rows:
            return []
        headers = rows[0]
        return [dict(zip(headers, row)) for row in rows[1:]]

    def fetch_host_problems(self) -> list[dict]:
        return self._fetch_view("nagstamon_hosts")

    def fetch_service_problems(self) -> list[dict]:
        return self._fetch_view("nagstamon_svc")

    def fetch_all_problems(self) -> list[dict]:
        """Return combined host + service problems with normalised fields."""
        problems = []

        for row in self.fetch_host_problems():
            problems.append({
                "host": row.get("host", row.get("name", "")),
                "service": "",
                "state": row.get("host_state", row.get("state", "DOWN")),
                "duration": _duration(row.get("host_last_state_change", row.get("last_state_change", ""))),
                "attempt": row.get("host_attempt", row.get("current_attempt", "")),
                "message": row.get("host_plugin_output", row.get("plugin_output", "")),
            })

        for row in self.fetch_service_problems():
            problems.append({
                "host": row.get("host", ""),
                "service": row.get("service_description", row.get("description", "")),
                "state": row.get("service_state", row.get("state", "")),
                "duration": _duration(row.get("svc_last_state_change", row.get("last_state_change", ""))),
                "attempt": row.get("svc_attempt", row.get("current_attempt", "")),
                "message": row.get("svc_plugin_output", row.get("plugin_output", "")),
            })

        return problems


def _duration(timestamp_str: str) -> str:
    """Convert a unix timestamp string to a human-readable duration."""
    if not timestamp_str:
        return ""
    try:
        ts = int(timestamp_str)
    except (ValueError, TypeError):
        return str(timestamp_str)
    delta = int(time.time()) - ts
    if delta < 0:
        return "0s"
    days, rem = divmod(delta, 86400)
    hours, rem = divmod(rem, 3600)
    mins, secs = divmod(rem, 60)
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {mins}m"
    if mins:
        return f"{mins}m {secs}s"
    return f"{secs}s"
