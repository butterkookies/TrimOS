"""
Elevation utilities — admin detection and UAC re-launch.
"""

import ctypes
import shutil
import sys
import os


def is_admin() -> bool:
    """Return True if the current process has admin privileges."""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def enable_vt_mode() -> None:
    """
    Enable VT100 processing on the Windows console.
    Required for correct Textual rendering in conhost (CMD, plain PS).
    Safe to call in any context — silently ignored if not applicable.
    """
    try:
        k32 = ctypes.windll.kernel32
        handle = k32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_ulong()
        k32.GetConsoleMode(handle, ctypes.byref(mode))
        # ENABLE_PROCESSED_OUTPUT | ENABLE_VIRTUAL_TERMINAL_PROCESSING
        k32.SetConsoleMode(handle, mode.value | 0x0001 | 0x0004)
    except Exception:
        pass


def restart_as_admin() -> None:
    """
    Re-launch the current process elevated via UAC (runas verb).

    Prefers Windows Terminal (wt.exe) so that Textual's VT rendering is
    preserved after elevation. Falls back to launching python.exe directly
    (opens in conhost — VT mode will be enabled by enable_vt_mode on startup).

    The caller is responsible for calling sys.exit() after this returns.
    """
    script = os.path.abspath(sys.argv[0])
    extra = " ".join(f'"{a}"' for a in sys.argv[1:])
    py_cmd = f'"{sys.executable}" "{script}" {extra}'.strip()

    wt = shutil.which("wt")
    if wt:
        # Elevated Windows Terminal — preserves VT rendering
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", wt, f"-- {py_cmd}", None, 1
        )
    else:
        # Fallback: plain conhost window; enable_vt_mode() covers rendering
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable,
            f'"{script}" {extra}'.strip(), None, 1
        )
