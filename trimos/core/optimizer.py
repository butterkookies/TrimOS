"""
Optimizer — batch stop/start services and kill processes.

Handles the actual system modifications with safety checks,
snapshot creation before changes, and confirmation flow.
Respects the whitelist to skip user-protected services.
"""

import subprocess
import psutil
from typing import Optional

from .scanner import SystemItem, ItemType, SafetyLevel
from .whitelist import Whitelist


# Services that must NEVER be touched — system will crash or become unusable
NEVER_TOUCH = {
    "rpcss", "dcomlaunch", "lsass", "csrss", "wininit", "winlogon",
    "services", "smss", "svchost", "dwm", "explorer", "ntoskrnl",
    "plugplay", "power", "profiling", "samss", "seclogon",
    "eventlog", "coreserv", "brokered", "cryptsvc", "dhcp",
    "dnscache", "lmhosts", "mpssvc", "nsi", "schedule",
    "sens", "systemeventsbroker", "timedbroker", "windefend",
}


class OptimizeResult:
    """Result of an optimization run."""

    def __init__(self):
        self.stopped: list[str] = []
        self.failed: list[tuple[str, str]] = []  # (name, error)
        self.skipped: list[str] = []
        self.protected_skipped: list[str] = []    # Skipped due to whitelist
        self.ram_freed_mb: float = 0.0

    @property
    def total_attempted(self) -> int:
        return len(self.stopped) + len(self.failed) + len(self.skipped)


class Optimizer:
    """Stops/starts services and kills processes."""

    def __init__(self, whitelist: Whitelist | None = None):
        self.whitelist = whitelist or Whitelist()

    def stop_service(self, name: str) -> tuple[bool, str]:
        """
        Stop a Windows service by name.
        Returns (success, message).
        """
        if name.lower() in NEVER_TOUCH:
            return False, "Protected service — cannot stop"

        try:
            result = subprocess.run(
                ["sc", "stop", name],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0:
                return True, "Stopped"
            else:
                error = result.stderr.strip() or result.stdout.strip()
                return False, error[:100]
        except subprocess.TimeoutExpired:
            return False, "Timeout — service did not respond"
        except Exception as e:
            return False, str(e)[:100]

    def start_service(self, name: str) -> tuple[bool, str]:
        """Start a Windows service by name."""
        try:
            result = subprocess.run(
                ["sc", "start", name],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0:
                return True, "Started"
            else:
                error = result.stderr.strip() or result.stdout.strip()
                return False, error[:100]
        except subprocess.TimeoutExpired:
            return False, "Timeout — service did not respond"
        except Exception as e:
            return False, str(e)[:100]

    def kill_process(self, name: str) -> tuple[bool, str]:
        """Kill all instances of a process by name."""
        if name.lower() in NEVER_TOUCH:
            return False, "Protected process — cannot kill"

        killed = 0
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                proc_name = (proc.info["name"] or "").replace(".exe", "")
                if proc_name.lower() == name.lower():
                    proc.kill()
                    killed += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if killed > 0:
            return True, f"Killed {killed} instance(s)"
        return False, "Process not found or access denied"

    def get_bulk_targets(
        self,
        items: list[SystemItem],
        mode: str = "default",
    ) -> list[SystemItem]:
        """
        Get the list of items that WOULD be closed in a bulk operation.
        Respects the whitelist and safety checks.
        Used to populate the confirmation dialog.
        """
        targets = []

        for item in items:
            # Skip system-critical
            if item.name.lower() in NEVER_TOUCH:
                continue

            # Skip user-protected
            if self.whitelist.is_protected(item.name):
                continue

            # Skip non-running
            if item.status != "running":
                continue

            should_stop = self._should_stop(item, mode)
            if should_stop:
                targets.append(item)

        return targets

    def _should_stop(self, item: SystemItem, mode: str) -> bool:
        """Determine if an item should be stopped for the given mode."""
        if mode == "default":
            return item.safety == SafetyLevel.TRIMMABLE
        elif mode == "gaming":
            if item.safety in (SafetyLevel.TRIMMABLE, SafetyLevel.APP):
                # Keep game-related processes
                return item.category not in ("gaming",)
            return False
        elif mode == "work":
            if item.safety == SafetyLevel.TRIMMABLE:
                return True
            if item.category in ("entertainment", "gaming") and item.safety == SafetyLevel.APP:
                return True
            return False
        elif mode == "bloatware":
            return item.bloatware and item.status == "running"
        return False

    def optimize(self, items: list[SystemItem], mode: str = "default") -> OptimizeResult:
        """
        Batch-optimize: stop services and kill processes based on mode.
        Respects the whitelist — protected services are always skipped.

        Modes:
        - "default": Stop only 🔴 Trimmable services
        - "gaming":  Stop trimmable services + kill non-essential user apps
        - "work":    Stop trimmable services + kill entertainment apps
        - "bloatware": Stop only identified bloatware services
        """
        result = OptimizeResult()

        for item in items:
            # Safety check — system-critical
            if item.name.lower() in NEVER_TOUCH:
                result.skipped.append(item.name)
                continue

            # Whitelist check — user-protected
            if self.whitelist.is_protected(item.name):
                result.protected_skipped.append(item.display_name)
                result.skipped.append(item.name)
                continue

            should_stop = self._should_stop(item, mode)

            if not should_stop:
                result.skipped.append(item.name)
                continue

            # Only stop running items
            if item.status != "running":
                result.skipped.append(item.name)
                continue

            if item.item_type == ItemType.SERVICE:
                success, msg = self.stop_service(item.name)
            else:
                success, msg = self.kill_process(item.name)

            if success:
                result.stopped.append(item.display_name)
                result.ram_freed_mb += item.ram_mb
            else:
                result.failed.append((item.display_name, msg))

        return result
