"""
Service & process scanner.

Enumerates all running Windows services and background processes,
combining them into a unified list with resource usage data.
"""

import psutil
import subprocess
import json
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ItemType(str, Enum):
    """Whether the item is a Windows service or a user process."""
    SERVICE = "service"
    PROCESS = "process"


class SafetyLevel(str, Enum):
    """How safe it is to stop/kill this item."""
    ESSENTIAL = "essential"      # 🟢 Never touch — Windows will break
    RECOMMENDED = "recommended"  # 🟡 Keep running, but user can override
    TRIMMABLE = "trimmable"      # 🔴 Safe to stop — free resources
    APP = "app"                  # ⚪ User application — user decides
    UNKNOWN = "unknown"          # ❓ Not in database — needs review


# Labels and colors for each safety level (used in the TUI)
SAFETY_DISPLAY = {
    SafetyLevel.ESSENTIAL:    ("🟢 Safe",   "green"),
    SafetyLevel.RECOMMENDED:  ("🟡 Keep",   "yellow"),
    SafetyLevel.TRIMMABLE:    ("🔴 Trim",   "red"),
    SafetyLevel.APP:          ("⚪ App",     "white"),
    SafetyLevel.UNKNOWN:      ("❓ Unknown", "dim"),
}


@dataclass
class SystemItem:
    """A single service or process on the system."""
    name: str
    display_name: str
    item_type: ItemType
    safety: SafetyLevel
    status: str                    # "running", "stopped", "suspended"
    pid: Optional[int] = None
    ram_mb: float = 0.0
    cpu_percent: float = 0.0
    description: str = ""
    category: str = ""             # e.g., "gaming", "telemetry", "networking"
    children_count: int = 0        # For grouped processes (e.g., Chrome tabs)
    bloatware: bool = False        # Identified as bloatware/unnecessary
    is_protected: bool = False     # User-protected from bulk operations


class Scanner:
    """Scans and enumerates Windows services and processes."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "data", "services.json"
            )
        self._service_db: dict = {}
        self._load_service_db(db_path)

    def _load_service_db(self, path: str) -> None:
        """Load the service intelligence database."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Index by service name (lowercase) for fast lookup
            for entry in data.get("services", []):
                key = entry["name"].lower()
                self._service_db[key] = entry
        except (FileNotFoundError, json.JSONDecodeError):
            self._service_db = {}

    def classify(self, name: str) -> tuple[SafetyLevel, str, str, bool]:
        """
        Look up a service/process name in the database.
        Returns (safety_level, description, category, is_bloatware).
        """
        entry = self._service_db.get(name.lower())
        if entry:
            safety = SafetyLevel(entry.get("safety", "unknown"))
            desc = entry.get("description", "")
            cat = entry.get("category", "")
            bloat = entry.get("bloatware", False)
            return safety, desc, cat, bloat
        return SafetyLevel.UNKNOWN, "", "", False

    def scan_services(self) -> tuple[list[SystemItem], set[int]]:
        """
        Enumerate all Windows services with status and resource usage.
        Returns (items, service_pids) so scan_all() can pass PIDs to
        scan_processes() without a second win_service_iter() call.
        """
        items: list[SystemItem] = []
        service_pids: set[int] = set()

        try:
            for svc in psutil.win_service_iter():
                try:
                    info = svc.as_dict()
                    name = info.get("name", "")
                    display = info.get("display_name", name)
                    status_raw = info.get("status", "stopped")
                    pid = info.get("pid")

                    status = "running" if status_raw == "running" else "stopped"
                    ram_mb = 0.0
                    cpu_pct = 0.0

                    if pid and pid > 0:
                        service_pids.add(pid)

                    # Get resource usage if the service is running
                    if pid and pid > 0 and status == "running":
                        try:
                            proc = psutil.Process(pid)
                            mem = proc.memory_info()
                            ram_mb = mem.rss / (1024 * 1024)
                            cpu_pct = proc.cpu_percent(interval=0)
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass

                    safety, desc, cat, bloat = self.classify(name)

                    items.append(SystemItem(
                        name=name,
                        display_name=display,
                        item_type=ItemType.SERVICE,
                        safety=safety,
                        status=status,
                        pid=pid if pid and pid > 0 else None,
                        ram_mb=round(ram_mb, 1),
                        cpu_percent=round(cpu_pct, 1),
                        description=desc,
                        category=cat,
                        bloatware=bloat,
                    ))
                except Exception:
                    continue
        except Exception:
            pass

        return items, service_pids

    def scan_processes(self, service_pids: set[int] | None = None) -> list[SystemItem]:
        """
        Enumerate user-level background processes (not services).
        Groups multi-instance processes (e.g., Chrome) by name.

        Pass service_pids from scan_services() to avoid a second full
        win_service_iter() enumeration (expensive on Windows).
        """
        # Collect all service PIDs so we can exclude them
        if service_pids is None:
            service_pids = set()
            try:
                for svc in psutil.win_service_iter():
                    try:
                        info = svc.as_dict()
                        pid = info.get("pid")
                        if pid and pid > 0:
                            service_pids.add(pid)
                    except Exception:
                        continue
            except Exception:
                pass

        # System processes to always skip
        skip_names = {
            "system", "system idle process", "registry", "secure system",
            "memory compression", "idle", "",
        }

        # Group processes by name
        grouped: dict[str, dict] = {}

        for proc in psutil.process_iter(["pid", "name", "status"]):
            try:
                info = proc.info
                pid = info["pid"]
                name = info["name"] or ""
                proc_status = info.get("status", "")

                # Skip: system PIDs, service PIDs, skip list
                if pid in (0, 4) or pid in service_pids:
                    continue
                if name.lower().replace(".exe", "") in skip_names:
                    continue

                try:
                    mem = proc.memory_info()
                    ram_mb = mem.rss / (1024 * 1024)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    ram_mb = 0.0

                try:
                    cpu_pct = proc.cpu_percent(interval=0)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    cpu_pct = 0.0

                base_name = name.replace(".exe", "")

                if base_name not in grouped:
                    grouped[base_name] = {
                        "name": base_name,
                        "ram_mb": 0.0,
                        "cpu_percent": 0.0,
                        "count": 0,
                        "pid": pid,
                        "status": "running" if proc_status == psutil.STATUS_RUNNING else "stopped",
                    }

                grouped[base_name]["ram_mb"] += ram_mb
                grouped[base_name]["cpu_percent"] += cpu_pct
                grouped[base_name]["count"] += 1

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # Convert to SystemItem list
        items: list[SystemItem] = []
        for base_name, data in grouped.items():
            safety, desc, cat, bloat = self.classify(base_name)
            # If not in service DB, mark as user app
            if safety == SafetyLevel.UNKNOWN:
                safety = SafetyLevel.APP

            count = data["count"]
            display = f"{base_name} ({count})" if count > 1 else base_name

            items.append(SystemItem(
                name=base_name,
                display_name=display,
                item_type=ItemType.PROCESS,
                safety=safety,
                status=data["status"],
                pid=data["pid"],
                ram_mb=round(data["ram_mb"], 1),
                cpu_percent=round(data["cpu_percent"], 1),
                description=desc,
                category=cat,
                children_count=count,
                bloatware=bloat,
            ))

        return items

    def scan_all(self) -> list[SystemItem]:
        """
        Full system scan — services + processes combined.
        Sorted by RAM usage descending.
        """
        service_items, service_pids = self.scan_services()
        process_items = self.scan_processes(service_pids=service_pids)
        items = service_items + process_items
        items.sort(key=lambda x: x.ram_mb, reverse=True)
        return items
