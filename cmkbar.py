"""cmkbar - macOS app for monitoring CheckMK problems."""

from __future__ import annotations

import json
import os
import threading

import AppKit
import Foundation
import WebKit
import objc

import checkmk
import config


POPUP_HTML_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "popup.html")
STATE_PRIORITY = {
    "DOWN": 0,
    "UNREACHABLE": 0,
    "CRITICAL": 1,
    "WARNING": 2,
    "UNKNOWN": 3,
    "PENDING": 4,
}

STATE_BADGES = {
    "CRITICAL": "CRIT",
    "DOWN": "DOWN",
    "WARNING": "WARN",
    "UNKNOWN": "UNKN",
    "UNREACHABLE": "DOWN",
    "PENDING": "PEND",
}

CATEGORY_META = {
    "host-down": {"label": "Hosts Down", "icon": "DOWN"},
    "memory": {"label": "Memory", "icon": "MEM"},
    "disk": {"label": "Disk", "icon": "DSK"},
    "network": {"label": "Network", "icon": "NET"},
    "hardware": {"label": "Hardware", "icon": "HW"},
    "services": {"label": "Services", "icon": "SVC"},
    "system": {"label": "System", "icon": "SYS"},
    "other": {"label": "Other", "icon": "ETC"},
}


class AppDelegate(AppKit.NSObject):
    def init(self):
        self = objc.super(AppDelegate, self).init()
        if self is None:
            return None
        self._problems = []
        self._main_window = None
        self._wk_view = None
        self._bar_item = None
        self._cmk_client = None
        self._app_cfg = None
        return self

    def applicationDidFinishLaunching_(self, notification):
        self._app_cfg = config.load()
        self._cmk_client = checkmk.CheckMKClient(
            self._app_cfg["url"], self._app_cfg["username"], self._app_cfg["password"]
        )

        self._bar_item = AppKit.NSStatusBar.systemStatusBar().statusItemWithLength_(
            AppKit.NSVariableStatusItemLength
        )
        self._bar_item.button().setTitle_("cmkbar ✓")

        bar_menu = AppKit.NSMenu.alloc().init()
        for label, sel in [
            ("Show Dashboard", self.cmdShowDash_),
            ("Refresh Now", self.cmdRefresh_),
        ]:
            mi = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(label, sel, "")
            mi.setTarget_(self)
            bar_menu.addItem_(mi)
        bar_menu.addItem_(AppKit.NSMenuItem.separatorItem())
        qi = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Quit", self.cmdQuit_, "q")
        qi.setTarget_(self)
        bar_menu.addItem_(qi)
        self._bar_item.setMenu_(bar_menu)

        self._setup_main_window()

        interval = self._app_cfg.get("interval", 60)
        Foundation.NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            interval, self, self.onPollTimer_, None, True
        )
        threading.Thread(target=self._do_poll, daemon=True).start()

    def _setup_main_window(self):
        screen = AppKit.NSScreen.mainScreen().frame()
        w, h = 440, 720
        x = (screen.size.width - w) / 2
        y = (screen.size.height - h) / 2
        rect = Foundation.NSMakeRect(x, y, w, h)

        style = (
            AppKit.NSTitledWindowMask
            | AppKit.NSClosableWindowMask
            | AppKit.NSResizableWindowMask
            | AppKit.NSMiniaturizableWindowMask
        )
        self._main_window = AppKit.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            rect, style, AppKit.NSBackingStoreBuffered, False
        )
        self._main_window.setTitle_("cmkbar - CheckMK Monitor")
        self._main_window.setMinSize_(Foundation.NSMakeSize(360, 360))
        self._main_window.setReleasedWhenClosed_(False)

        wk_conf = WebKit.WKWebViewConfiguration.alloc().init()
        content_rect = Foundation.NSMakeRect(0, 0, w, h)
        self._wk_view = WebKit.WKWebView.alloc().initWithFrame_configuration_(
            content_rect, wk_conf
        )
        self._wk_view.setAutoresizingMask_(
            AppKit.NSViewWidthSizable | AppKit.NSViewHeightSizable
        )

        # Load HTML once — subsequent updates go via JS
        self._page_loaded = False
        self._pending_payload = None
        self._load_initial_html()

        self._main_window.contentView().addSubview_(self._wk_view)
        self._main_window.makeKeyAndOrderFront_(None)
        AppKit.NSApp.activateIgnoringOtherApps_(True)

    def _load_initial_html(self):
        """Load the HTML template once into the WebView."""
        with open(POPUP_HTML_PATH, "r", encoding="utf-8") as f:
            html = f.read()
        base_url = Foundation.NSURL.fileURLWithPath_(os.path.dirname(POPUP_HTML_PATH) + "/")
        self._wk_view.loadHTMLString_baseURL_(html, base_url)

        # Use a short timer to detect when the page is ready
        Foundation.NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            0.3, self, self.checkPageReady_, None, True
        )

    @objc.typedSelector(b"v@:@")
    def checkPageReady_(self, timer):
        """Poll until the page has loaded and updateProblems is defined."""
        def callback(result, error):
            if result and not self._page_loaded:
                self._page_loaded = True
                timer.invalidate()
                if self._pending_payload is not None:
                    self._push_payload(self._pending_payload)
        self._wk_view.evaluateJavaScript_completionHandler_(
            "typeof updateProblems === 'function'", callback
        )

    def _push_payload(self, payload):
        """Send data to the WebView via JS — preserves UI state."""
        data_json = json.dumps(payload).replace("</", "<\\/")
        js = f"updateProblems({data_json})"
        self._wk_view.evaluateJavaScript_completionHandler_(js, None)

    @objc.typedSelector(b"v@:@")
    def cmdShowDash_(self, sender):
        self._main_window.makeKeyAndOrderFront_(None)
        AppKit.NSApp.activateIgnoringOtherApps_(True)

    @objc.typedSelector(b"v@:@")
    def cmdRefresh_(self, sender):
        threading.Thread(target=self._do_poll, daemon=True).start()

    @objc.typedSelector(b"v@:@")
    def cmdQuit_(self, sender):
        AppKit.NSApp.terminate_(None)

    @objc.typedSelector(b"v@:@")
    def onPollTimer_(self, timer):
        threading.Thread(target=self._do_poll, daemon=True).start()

    def _do_poll(self):
        try:
            self._problems = self._cmk_client.fetch_all_problems()
            self.performSelectorOnMainThread_withObject_waitUntilDone_(
                self.onPollSuccess_, None, False
            )
        except Exception as e:
            print(f"Poll error: {e}")
            self.performSelectorOnMainThread_withObject_waitUntilDone_(
                self.onPollError_, None, False
            )

    @objc.typedSelector(b"v@:@")
    def onPollSuccess_(self, _obj):
        problem_count = len(self._problems)
        self._bar_item.button().setTitle_(
            "cmkbar ✓" if problem_count == 0 else f"cmkbar ⚠ {problem_count}"
        )
        payload = build_popup_payload(self._problems)
        if self._page_loaded:
            self._push_payload(payload)
        else:
            self._pending_payload = payload

    @objc.typedSelector(b"v@:@")
    def onPollError_(self, _obj):
        self._bar_item.button().setTitle_("cmkbar ✗")


def build_popup_payload(problems: list[dict]) -> dict:
    groups_by_key = {}
    unique_hosts = set()
    state_totals = {"DOWN": 0, "CRIT": 0, "WARN": 0, "UNKN": 0, "PEND": 0}

    for problem in problems:
        category = problem.get("category") or "other"
        state = problem.get("state") or "UNKNOWN"
        badge = STATE_BADGES.get(state, state[:4].upper())

        # DOWN/UNREACHABLE hosts get their own top-level group
        if state in ("DOWN", "UNREACHABLE"):
            category = "host-down"

        meta = CATEGORY_META.get(category, CATEGORY_META["other"])
        group_key = (category, state)
        unique_hosts.add((problem.get("site", ""), problem.get("host", "")))
        state_totals[badge] = state_totals.get(badge, 0) + 1

        group = groups_by_key.setdefault(
            group_key,
            {
                "id": f"{category}-{state.lower()}",
                "category": category,
                "category_label": meta["label"],
                "category_icon": meta["icon"],
                "state": state,
                "state_badge": badge,
                "problem_count": 0,
                "host_count": 0,
                "worst_duration": "0s",
                "worst_duration_seconds": 0,
                "hosts": {},
            },
        )

        host_key = (problem.get("site", ""), problem.get("host", ""))
        host_entry = group["hosts"].setdefault(
            host_key,
            {
                "host": problem.get("host", ""),
                "site": problem.get("site", ""),
                "problem_count": 0,
                "worst_duration": "0s",
                "worst_duration_seconds": 0,
                "acknowledged_count": 0,
                "downtime_count": 0,
                "items": [],
            },
        )

        item = {
            "host": problem.get("host", ""),
            "site": problem.get("site", ""),
            "service": problem.get("service", ""),
            "service_label": problem.get("service_label") or problem.get("service") or "Host State",
            "state": state,
            "state_badge": badge,
            "message": problem.get("message", ""),
            "duration": problem.get("duration", ""),
            "duration_raw": problem.get("duration_raw", ""),
            "duration_seconds": int(problem.get("duration_seconds", 0) or 0),
            "last_check": problem.get("last_check", ""),
            "attempt": problem.get("attempt", ""),
            "acknowledged": bool(problem.get("acknowledged")),
            "downtime": bool(problem.get("downtime")),
        }

        host_entry["items"].append(item)
        host_entry["problem_count"] += 1
        host_entry["acknowledged_count"] += int(item["acknowledged"])
        host_entry["downtime_count"] += int(item["downtime"])
        if item["duration_seconds"] >= host_entry["worst_duration_seconds"]:
            host_entry["worst_duration_seconds"] = item["duration_seconds"]
            host_entry["worst_duration"] = item["duration"] or host_entry["worst_duration"]

        group["problem_count"] += 1
        if item["duration_seconds"] >= group["worst_duration_seconds"]:
            group["worst_duration_seconds"] = item["duration_seconds"]
            group["worst_duration"] = item["duration"] or group["worst_duration"]

    groups = []
    for group in groups_by_key.values():
        hosts = []
        for host_entry in group["hosts"].values():
            host_entry["items"].sort(
                key=lambda item: (
                    -item["duration_seconds"],
                    item["service_label"].lower(),
                    item["message"].lower(),
                )
            )
            hosts.append(host_entry)

        hosts.sort(
            key=lambda host: (
                -host["worst_duration_seconds"],
                host["host"].lower(),
            )
        )

        group["hosts"] = hosts
        group["host_count"] = len(hosts)
        groups.append(group)

    groups.sort(
        key=lambda group: (
            STATE_PRIORITY.get(group["state"], 9),
            -group["host_count"],
            -group["worst_duration_seconds"],
            group["category_label"].lower(),
        )
    )

    return {
        "summary": {
            "problem_count": len(problems),
            "group_count": len(groups),
            "host_count": len(unique_hosts),
            "down_count": state_totals.get("DOWN", 0),
            "critical_count": state_totals.get("CRIT", 0),
            "warning_count": state_totals.get("WARN", 0),
            "unknown_count": state_totals.get("UNKN", 0),
        },
        "groups": groups,
    }


def main():
    app = AppKit.NSApplication.sharedApplication()
    app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyRegular)
    delegate = AppDelegate.alloc().init()
    app.setDelegate_(delegate)
    app.run()


if __name__ == "__main__":
    main()
