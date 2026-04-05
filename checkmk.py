"""CheckMK Multisite cookie-auth client.

Polls the nagstamon_hosts / nagstamon_svc views via output_format=python.
"""

import ast
import html as html_mod
import re

import requests


# States that count as "problems"
HOST_PROBLEM_STATES = {"DOWN", "UNREACH", "UNREACHABLE"}
SVC_PROBLEM_STATES = {"WARN", "WARNING", "CRIT", "CRITICAL", "UNKN", "UNKNOWN"}

# Display labels
STATEMAP = {
    "UNREACH": "UNREACHABLE",
    "CRIT": "CRITICAL",
    "WARN": "WARNING",
    "UNKN": "UNKNOWN",
    "PEND": "PENDING",
}


class CheckMKClient:
    def __init__(self, url: str, username: str, password: str):
        self.url = url.rstrip("/")
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
                "_origtarget": "",
            },
        )
        r.raise_for_status()
        cookies = self.session.cookies.get_dict()
        has_auth = any(k.startswith("auth_") or k == "sid" for k in cookies)
        if not has_auth and "_username" not in r.text:
            raise RuntimeError("Login failed — check credentials")
        self._logged_in = True

    def _ensure_login(self):
        if not self._logged_in:
            self.login()

    def _fetch_view(self, view_name: str, extra_params: dict | None = None) -> list[dict]:
        self._ensure_login()
        params = {
            "view_name": view_name,
            "output_format": "python",
            "lang": "",
            "limit": "hard",
        }
        if extra_params:
            params.update(extra_params)

        r = self.session.get(f"{self.url}/check_mk/view.py", params=params)
        if r.status_code == 401 or "login" in r.url:
            self.login()
            r = self.session.get(f"{self.url}/check_mk/view.py", params=params)
        r.raise_for_status()

        try:
            rows = ast.literal_eval(r.text)
        except (ValueError, SyntaxError):
            rows = r.json()

        if not rows:
            return []
        headers = rows[0]
        return [dict(zip(headers, row)) for row in rows[1:]]

    def fetch_all_problems(self) -> list[dict]:
        """Return combined host + service problems with normalised fields."""
        problems = []

        # --- Host problems ---
        for row in self._fetch_view("nagstamon_hosts"):
            state_raw = row.get("host_state", "")
            if state_raw.upper() not in HOST_PROBLEM_STATES:
                continue
            state = STATEMAP.get(state_raw, state_raw)
            problems.append({
                "host": row.get("host", ""),
                "service": "",
                "state": state,
                "last_check": row.get("host_check_age", ""),
                "duration": row.get("host_state_age", ""),
                "attempt": row.get("host_attempt", ""),
                "message": _clean_output(row.get("host_plugin_output", "")),
                "acknowledged": row.get("host_acknowledged", "") == "yes",
                "downtime": row.get("host_in_downtime", "") == "yes",
                "site": row.get("sitename_plain", ""),
            })

        # --- Service problems ---
        for row in self._fetch_view("nagstamon_svc", {"hst0": "On", "hst1": "On"}):
            state_raw = row.get("service_state", row.get("state", ""))
            if state_raw.upper() not in SVC_PROBLEM_STATES:
                continue
            state = STATEMAP.get(state_raw, state_raw)

            # Ack can also be indicated by 'ack' in service_icons list
            icons = row.get("service_icons", [])
            if isinstance(icons, str):
                icons = []
            ack_flag = row.get("svc_acknowledged", "") == "yes" or "ack" in icons

            problems.append({
                "host": row.get("host", ""),
                "service": row.get("service_description", ""),
                "state": state,
                "last_check": row.get("svc_check_age", ""),
                "duration": row.get("svc_state_age", ""),
                "attempt": row.get("svc_attempt", ""),
                "message": _clean_output(row.get("svc_plugin_output", "")),
                "acknowledged": ack_flag,
                "downtime": row.get("svc_in_downtime", "") == "yes"
                    or row.get("host_in_downtime", "") == "yes",
                "site": row.get("sitename_plain", ""),
            })

        return problems


def _clean_output(text: str) -> str:
    """Unescape HTML entities and collapse whitespace in plugin output."""
    if not text:
        return ""
    text = html_mod.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text
