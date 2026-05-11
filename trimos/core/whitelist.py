"""
Whitelist system — protect services from bulk optimization.

Persists protected service names to a JSON file so they
survive app restarts. Protected services are excluded from
all bulk-close operations.
"""

import json
import os
from typing import Set


class Whitelist:
    """Manages a persistent set of protected service names."""

    def __init__(self, path: str | None = None):
        if path is None:
            from .paths import get_data_dir
            path = str(get_data_dir() / "whitelist.json")
        self._path = path
        self._protected: Set[str] = set()
        self._load()

    def _load(self) -> None:
        """Load protected names from disk."""
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._protected = set(data.get("protected", []))
        except (FileNotFoundError, json.JSONDecodeError):
            self._protected = set()

    def _save(self) -> None:
        """Persist protected names to disk."""
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump({"protected": sorted(self._protected)}, f, indent=2)

    def toggle(self, name: str) -> bool:
        """
        Toggle protection on a service.
        Returns True if the service is now protected, False if unprotected.
        """
        key = name.lower()
        if key in self._protected:
            self._protected.discard(key)
            self._save()
            return False
        else:
            self._protected.add(key)
            self._save()
            return True

    def protect(self, name: str) -> None:
        """Add a service to the protected list."""
        self._protected.add(name.lower())
        self._save()

    def unprotect(self, name: str) -> None:
        """Remove a service from the protected list."""
        self._protected.discard(name.lower())
        self._save()

    def is_protected(self, name: str) -> bool:
        """Check if a service is protected."""
        return name.lower() in self._protected

    @property
    def protected_names(self) -> Set[str]:
        """Get a copy of all protected service names."""
        return self._protected.copy()

    @property
    def count(self) -> int:
        """Number of protected services."""
        return len(self._protected)
