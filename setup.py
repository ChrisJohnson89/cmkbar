"""py2app build configuration for cmkbar."""

from setuptools import setup

APP = ["cmkbar.py"]
DATA_FILES = [("", ["popup.html"])]

OPTIONS = {
    "argv_emulation": False,
    "iconfile": None,  # Replace with "cmkbar.icns" if you have an icon
    "plist": {
        "CFBundleName": "cmkbar",
        "CFBundleDisplayName": "cmkbar",
        "CFBundleIdentifier": "com.cmkbar.app",
        "CFBundleVersion": "0.1.0",
        "CFBundleShortVersionString": "0.1.0",
        "LSUIElement": True,  # Hide from Dock, menu bar only
    },
    "packages": ["rumps", "webview", "requests", "certifi"],
}

setup(
    name="cmkbar",
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
