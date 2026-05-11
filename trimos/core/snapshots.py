"""
Snapshot system — save and restore service/process states.

Creates JSON snapshots before any optimization so the user
can always roll back to a known good state.
"""

import json
import os
import time
from datetime import datetime
from typing import Optional

from .scanner import SystemItem, ItemType, SafetyLevel


SNAPSHOTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "data", "snapshots"
)


class SnapshotManager:
    """Manages service state snapshots for restore functionality."""

    def __init__(self, snapshots_dir: Optional[str] = None):
        self._dir = snapshots_dir or SNAPSHOTS_DIR
        os.makedirs(self._dir, exist_ok=True)

    def save(self, items: list[SystemItem], label: str = "auto") -> str:
        """
        Save a snapshot of current service/process states.
        Returns the snapshot filename.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"snapshot_{label}_{timestamp}.json"
        filepath = os.path.join(self._dir, filename)

        data = {
            "label": label,
            "timestamp": timestamp,
            "created_at": datetime.now().isoformat(),
            "items": [
                {
                    "name": item.name,
                    "display_name": item.display_name,
                    "item_type": item.item_type.value,
                    "status": item.status,
                    "safety": item.safety.value,
                }
                for item in items
                if item.item_type == ItemType.SERVICE  # Only snapshot services (can be restarted)
            ]
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        # Keep only the last 10 snapshots
        self._cleanup()

        return filename

    def list_snapshots(self) -> list[dict]:
        """List all available snapshots, newest first."""
        snapshots = []
        try:
            for fname in os.listdir(self._dir):
                if fname.endswith(".json"):
                    filepath = os.path.join(self._dir, fname)
                    try:
                        with open(filepath, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        snapshots.append({
                            "filename": fname,
                            "label": data.get("label", ""),
                            "created_at": data.get("created_at", ""),
                            "item_count": len(data.get("items", [])),
                        })
                    except (json.JSONDecodeError, KeyError):
                        continue
        except FileNotFoundError:
            pass

        snapshots.sort(key=lambda x: x["created_at"], reverse=True)
        return snapshots

    def load(self, filename: str) -> list[dict]:
        """Load a snapshot file and return its service items."""
        filepath = os.path.join(self._dir, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("items", [])

    def get_latest(self) -> Optional[str]:
        """Get the filename of the most recent snapshot."""
        snapshots = self.list_snapshots()
        if snapshots:
            return snapshots[0]["filename"]
        return None

    def _cleanup(self, keep: int = 10) -> None:
        """Remove old snapshots, keeping only the most recent N."""
        snapshots = self.list_snapshots()
        for snap in snapshots[keep:]:
            try:
                os.remove(os.path.join(self._dir, snap["filename"]))
            except OSError:
                pass
