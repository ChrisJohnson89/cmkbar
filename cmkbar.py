"""cmkbar — macOS app for monitoring CheckMK problems."""

import json
import os
import threading
import urllib.parse

import AppKit
import Foundation
import WebKit
import objc

import checkmk
import config


POPUP_HTML_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "popup.html")


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

        # --- Menu bar status item ---
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

        # --- Main app window with WebView ---
        self._setup_main_window()

        # --- Poll timer ---
        interval = self._app_cfg.get("interval", 60)
        Foundation.NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            interval, self, self.onPollTimer_, None, True
        )
        threading.Thread(target=self._do_poll, daemon=True).start()

    def _setup_main_window(self):
        screen = AppKit.NSScreen.mainScreen().frame()
        w, h = 1200, 700
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
        self._main_window.setTitle_("cmkbar — CheckMK Monitor")
        self._main_window.setMinSize_(Foundation.NSMakeSize(600, 300))
        self._main_window.setReleasedWhenClosed_(False)

        wk_conf = WebKit.WKWebViewConfiguration.alloc().init()
        content_rect = Foundation.NSMakeRect(0, 0, w, h)
        self._wk_view = WebKit.WKWebView.alloc().initWithFrame_configuration_(
            content_rect, wk_conf
        )
        self._wk_view.setAutoresizingMask_(
            AppKit.NSViewWidthSizable | AppKit.NSViewHeightSizable
        )

        # Load a blank page initially
        self._load_html_with_data([])

        self._main_window.contentView().addSubview_(self._wk_view)
        self._main_window.makeKeyAndOrderFront_(None)
        AppKit.NSApp.activateIgnoringOtherApps_(True)

    def _load_html_with_data(self, problems):
        """Read the HTML template, inject problem data, and load it into the WebView."""
        with open(POPUP_HTML_PATH, "r") as f:
            html = f.read()

        # Inject data by replacing the placeholder script call
        data_json = json.dumps(problems)
        inject = f"<script>document.addEventListener('DOMContentLoaded', function() {{ updateProblems({data_json}); }});</script>"
        html = html.replace("</body>", f"{inject}</body>")

        base_url = Foundation.NSURL.fileURLWithPath_(os.path.dirname(POPUP_HTML_PATH) + "/")
        self._wk_view.loadHTMLString_baseURL_(html, base_url)

    # -- Menu actions --

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

    # -- Polling --

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
        n = len(self._problems)
        self._bar_item.button().setTitle_("cmkbar ✓" if n == 0 else f"cmkbar ⚠ {n}")
        self._load_html_with_data(self._problems)

    @objc.typedSelector(b"v@:@")
    def onPollError_(self, _obj):
        self._bar_item.button().setTitle_("cmkbar ✗")


def main():
    app = AppKit.NSApplication.sharedApplication()
    app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyRegular)
    delegate = AppDelegate.alloc().init()
    app.setDelegate_(delegate)
    app.run()


if __name__ == "__main__":
    main()
