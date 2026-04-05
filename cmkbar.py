"""cmkbar — macOS menu bar monitor for CheckMK."""

import json
import os
import threading
import time

import rumps
import webview

import checkmk
import config


POPUP_HTML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "popup.html")


class CmkBarApp(rumps.App):
    def __init__(self, cfg: dict):
        super().__init__("✓", quit_button=None)
        self.cfg = cfg
        self.client = checkmk.CheckMKClient(cfg["url"], cfg["username"], cfg["password"])
        self.problems: list[dict] = []
        self.window = None
        self._window_lock = threading.Lock()

        self.menu = [
            rumps.MenuItem("Show Problems", callback=self.show_popup),
            rumps.MenuItem("Refresh Now", callback=self.manual_refresh),
            None,  # separator
            rumps.MenuItem("Quit", callback=self.quit_app),
        ]

        self.timer = rumps.Timer(self.poll, cfg["interval"])
        self.timer.start()
        # Initial poll in background
        threading.Thread(target=self._do_poll, daemon=True).start()

    def poll(self, _sender):
        threading.Thread(target=self._do_poll, daemon=True).start()

    def _do_poll(self):
        try:
            self.problems = self.client.fetch_all_problems()
            self._update_title()
            self._push_to_popup()
        except Exception as e:
            self.title = "✗"
            print(f"Poll error: {e}")

    def _update_title(self):
        n = len(self.problems)
        if n == 0:
            self.title = "✓"
        else:
            self.title = f"⚠ {n}"

    def _push_to_popup(self):
        with self._window_lock:
            if self.window is not None:
                js = f"updateProblems({json.dumps(self.problems)})"
                try:
                    self.window.evaluate_js(js)
                except Exception:
                    pass

    def show_popup(self, _sender=None):
        threading.Thread(target=self._open_popup, daemon=True).start()

    def _open_popup(self):
        with self._window_lock:
            if self.window is not None:
                try:
                    self.window.show()
                    return
                except Exception:
                    self.window = None

        win = webview.create_window(
            "cmkbar",
            POPUP_HTML,
            width=900,
            height=500,
            resizable=True,
            on_top=True,
        )
        self.window = win

        def on_loaded():
            js = f"updateProblems({json.dumps(self.problems)})"
            win.evaluate_js(js)

        win.events.loaded += on_loaded
        webview.start()
        # webview.start() blocks until all windows close
        with self._window_lock:
            self.window = None

    def manual_refresh(self, _sender):
        threading.Thread(target=self._do_poll, daemon=True).start()

    def quit_app(self, _sender):
        with self._window_lock:
            if self.window is not None:
                try:
                    self.window.destroy()
                except Exception:
                    pass
        rumps.quit_application()


def main():
    cfg = config.load()
    app = CmkBarApp(cfg)
    app.run()


if __name__ == "__main__":
    main()
