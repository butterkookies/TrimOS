# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for TrimOS.

Builds a single-folder distribution (--onedir) with:
  • All Python source bundled via Analysis
  • data/  directory added as read-only data files
  • Textual CSS added alongside the trimos package
  • Windows UAC manifest requesting admin at launch (optional)
"""

import os
from pathlib import Path

block_cipher = None
ROOT = os.path.abspath(".")

a = Analysis(
    ["main.py"],
    pathex=[ROOT],
    binaries=[],
    datas=[
        # Bundle the data directory (services.json, whitelist.json, analytics.json)
        (os.path.join(ROOT, "data"), "data"),
        # Bundle the Textual CSS file alongside the package
        (os.path.join(ROOT, "trimos", "styles", "trimos.tcss"),
         os.path.join("trimos", "styles")),
    ],
    hiddenimports=[
        # Textual internals that PyInstaller sometimes misses
        "textual",
        "textual.app",
        "textual.css",
        "textual.css.query",
        "textual.widgets",
        "textual._xterm_parser",
        "textual._animator",
        "textual.drivers",
        "textual.drivers.win32",
        "textual.drivers._writer_thread",
        "rich",
        "rich.text",
        "rich.markup",
        "rich.traceback",
        "rich.console",
        "psutil",
        "plotext",
        # Our own sub-packages
        "trimos",
        "trimos.app",
        "trimos.core",
        "trimos.core.paths",
        "trimos.core.scanner",
        "trimos.core.monitor",
        "trimos.core.optimizer",
        "trimos.core.snapshots",
        "trimos.core.whitelist",
        "trimos.core.analytics",
        "trimos.core.intelligence",
        "trimos.core.cleaner",
        "trimos.core.startup",
        "trimos.core.elevation",
        "trimos.widgets",
        "trimos.widgets.mascot",
        "trimos.widgets.perf_graphs",
        "trimos.widgets.service_table",
        "trimos.widgets.detail_panel",
        "trimos.screens",
        "trimos.screens.confirm_screen",
        "trimos.screens.startup_screen",
        "trimos.screens.analytics_screen",
        "trimos.screens.deep_clean_screen",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="TrimOS",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,           # TUI app — needs a real console
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # Uncomment below to embed a custom icon:
    # icon="assets/trimos.ico",
    uac_admin=False,        # Don't force admin — app handles elevation itself
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="TrimOS",
)
