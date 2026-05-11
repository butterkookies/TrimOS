"""
Path utilities — PyInstaller-aware resource resolution.

When running from a PyInstaller bundle, bundled read-only assets
are extracted to a temp folder (sys._MEIPASS).  Writable user data
(whitelist, snapshots, analytics) must live outside the bundle in a
persistent directory.
"""

import os
import sys
from pathlib import Path


def _is_frozen() -> bool:
    """Return True when running inside a PyInstaller bundle."""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def get_bundle_dir() -> Path:
    """
    Root of the *bundled* data tree.

    • Frozen  → sys._MEIPASS  (temp extraction folder)
    • Dev     → project root  (repo checkout)
    """
    if _is_frozen():
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent.parent


def get_data_dir() -> Path:
    """
    Directory for *writable* user data (whitelist, analytics, snapshots).

    • Frozen  → %LOCALAPPDATA%/TrimOS/data
    • Dev     → <project_root>/data
    """
    if _is_frozen():
        appdata = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
        data = Path(appdata) / "TrimOS" / "data"
        data.mkdir(parents=True, exist_ok=True)
        return data
    return Path(__file__).resolve().parent.parent.parent / "data"


def get_bundled_data_dir() -> Path:
    """
    Directory for *read-only* bundled data (services.json).

    • Frozen  → sys._MEIPASS / data
    • Dev     → <project_root>/data
    """
    return get_bundle_dir() / "data"
