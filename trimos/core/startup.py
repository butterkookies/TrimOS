"""
Startup Manager — read and toggle Windows startup registry entries.

Reads from HKCU and HKLM Run keys, toggles via StartupApproved
(same mechanism Task Manager uses — no entries are deleted by default).
"""

import winreg
from dataclasses import dataclass


@dataclass
class StartupEntry:
    """A single Windows startup entry."""
    name: str
    command: str
    scope: str    # "user" or "system"
    enabled: bool


_RUN_PATHS: dict[str, tuple] = {
    "user":   (winreg.HKEY_CURRENT_USER,  r"Software\Microsoft\Windows\CurrentVersion\Run"),
    "system": (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run"),
}

_APPROVED_PATHS: dict[str, tuple] = {
    "user":   (winreg.HKEY_CURRENT_USER,  r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"),
    "system": (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"),
}


class StartupManager:
    """Read and toggle Windows startup entries via registry."""

    def get_entries(self) -> list[StartupEntry]:
        """Return all startup entries from both user and system hives."""
        entries: list[StartupEntry] = []
        for scope, (hive, path) in _RUN_PATHS.items():
            try:
                key = winreg.OpenKey(hive, path, 0, winreg.KEY_READ)
                i = 0
                while True:
                    try:
                        name, value, _ = winreg.EnumValue(key, i)
                        entries.append(StartupEntry(
                            name=name,
                            command=str(value),
                            scope=scope,
                            enabled=self._is_enabled(scope, name),
                        ))
                        i += 1
                    except OSError:
                        break
                winreg.CloseKey(key)
            except OSError:
                continue
        return entries

    def _is_enabled(self, scope: str, name: str) -> bool:
        """
        Check StartupApproved registry key for enabled state.
        First byte of binary value: 0x02 = enabled, 0x03 = disabled.
        Missing entry = enabled by default.
        """
        hive, path = _APPROVED_PATHS[scope]
        try:
            key = winreg.OpenKey(hive, path, 0, winreg.KEY_READ)
            try:
                data, _ = winreg.QueryValueEx(key, name)
                if isinstance(data, bytes) and len(data) >= 1:
                    return data[0] == 0x02
            except OSError:
                pass
            finally:
                winreg.CloseKey(key)
        except OSError:
            pass
        return True

    def toggle(self, entry: StartupEntry) -> tuple[bool, str]:
        """
        Toggle startup entry enabled/disabled using StartupApproved key.
        Returns (new_enabled_state, error_message).
        """
        new_enabled = not entry.enabled
        hive, path = _APPROVED_PATHS[entry.scope]
        try:
            key = winreg.OpenKey(hive, path, 0, winreg.KEY_SET_VALUE | winreg.KEY_CREATE_SUB_KEY)
            # 12-byte binary value: first 4 bytes = status flags, rest = timestamp
            status_byte = 0x02 if new_enabled else 0x03
            data = bytes([status_byte, 0x00, 0x00, 0x00]) + bytes(8)
            winreg.SetValueEx(key, entry.name, 0, winreg.REG_BINARY, data)
            winreg.CloseKey(key)
            return new_enabled, ""
        except OSError as e:
            return entry.enabled, str(e)

    def delete_entry(self, entry: StartupEntry) -> tuple[bool, str]:
        """Permanently remove a startup entry from the Run key."""
        hive, path = _RUN_PATHS[entry.scope]
        try:
            key = winreg.OpenKey(hive, path, 0, winreg.KEY_SET_VALUE)
            winreg.DeleteValue(key, entry.name)
            winreg.CloseKey(key)
            # Also remove from StartupApproved if present
            try:
                hive2, path2 = _APPROVED_PATHS[entry.scope]
                akey = winreg.OpenKey(hive2, path2, 0, winreg.KEY_SET_VALUE)
                winreg.DeleteValue(akey, entry.name)
                winreg.CloseKey(akey)
            except OSError:
                pass
            return True, ""
        except OSError as e:
            return False, str(e)
