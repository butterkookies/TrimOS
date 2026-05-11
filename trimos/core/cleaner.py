"""
Deep cleaning engine — scans and removes temp files, browser caches, and junk.

Targets: user/system temp, Windows prefetch, Windows Update cache,
browser caches (Chrome, Edge, Firefox), thumbnail cache.
"""

import os
import shutil
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class CleanTarget:
    """A single cleanup target directory."""
    name: str
    path: Path
    category: str          # "System" | "Browser"
    size_bytes: int = 0
    file_count: int = 0
    selected: bool = True
    accessible: bool = True
    error: str = ""


@dataclass
class CleanResult:
    freed_bytes: int = 0
    files_deleted: int = 0
    errors: list[str] = field(default_factory=list)


# ── Helpers ────────────────────────────────────────────────────────────────


def _dir_size(path: Path) -> tuple[int, int]:
    """Return (total_bytes, file_count) for a directory tree."""
    total = 0
    count = 0
    try:
        for entry in os.scandir(path):
            try:
                if entry.is_file(follow_symlinks=False):
                    total += entry.stat().st_size
                    count += 1
                elif entry.is_dir(follow_symlinks=False):
                    sub_bytes, sub_count = _dir_size(Path(entry.path))
                    total += sub_bytes
                    count += sub_count
            except (PermissionError, OSError):
                pass
    except (PermissionError, OSError):
        pass
    return total, count


def _env_path(*parts: str) -> Path | None:
    """Resolve an env-var-based path, return None if missing."""
    first = os.environ.get(parts[0])
    if not first:
        return None
    p = Path(first, *parts[1:])
    return p if p.exists() else None


# ── Cleaner ────────────────────────────────────────────────────────────────


class DiskCleaner:
    """Scans and cleans common junk file locations."""

    def get_targets(self) -> list[CleanTarget]:
        """Return list of CleanTarget with sizes populated."""
        targets: list[CleanTarget] = []

        # User temp (%TEMP%)
        user_temp = _env_path("TEMP") or _env_path("TMP")
        if user_temp:
            targets.append(CleanTarget("User Temp Files", user_temp, "System"))

        # AppData\Local\Temp (sometimes differs from %TEMP%)
        local_temp = _env_path("LOCALAPPDATA", "Temp")
        if local_temp and local_temp != user_temp:
            targets.append(CleanTarget("AppData Temp", local_temp, "System"))

        # Windows system temp
        win_temp = Path(r"C:\Windows\Temp")
        if win_temp.exists():
            targets.append(CleanTarget("Windows Temp Files", win_temp, "System"))

        # Windows Prefetch
        prefetch = Path(r"C:\Windows\Prefetch")
        if prefetch.exists():
            targets.append(CleanTarget("Windows Prefetch", prefetch, "System"))

        # Windows Update download cache
        wu_cache = Path(r"C:\Windows\SoftwareDistribution\Download")
        if wu_cache.exists():
            targets.append(CleanTarget("Windows Update Cache", wu_cache, "System"))

        # Thumbnail cache (only thumbcache_*.db files inside Explorer dir)
        thumb_dir = _env_path("LOCALAPPDATA", "Microsoft", "Windows", "Explorer")
        if thumb_dir:
            targets.append(CleanTarget("Thumbnail Cache", thumb_dir, "System"))

        # Chrome cache
        chrome = _env_path("LOCALAPPDATA", "Google", "Chrome", "User Data", "Default", "Cache")
        if chrome:
            targets.append(CleanTarget("Chrome Cache", chrome, "Browser"))

        # Edge cache
        edge = _env_path("LOCALAPPDATA", "Microsoft", "Edge", "User Data", "Default", "Cache")
        if edge:
            targets.append(CleanTarget("Edge Cache", edge, "Browser"))

        # Firefox cache (first profile found)
        ff_profiles = _env_path("LOCALAPPDATA", "Mozilla", "Firefox", "Profiles")
        if ff_profiles:
            try:
                for profile_dir in ff_profiles.iterdir():
                    cache2 = profile_dir / "cache2"
                    if cache2.exists():
                        targets.append(CleanTarget("Firefox Cache", cache2, "Browser"))
                        break
            except (PermissionError, OSError):
                pass

        # Populate sizes
        for t in targets:
            try:
                t.size_bytes, t.file_count = _dir_size(t.path)
                t.accessible = True
            except Exception as exc:
                t.accessible = False
                t.error = str(exc)

        return targets

    def clean(self, targets: list[CleanTarget]) -> CleanResult:
        """Delete files in all selected, accessible targets."""
        result = CleanResult()
        for target in targets:
            if not target.selected or not target.accessible:
                continue
            freed, deleted, errors = self._clean_dir(target)
            result.freed_bytes += freed
            result.files_deleted += deleted
            result.errors.extend(errors)
        return result

    def _clean_dir(self, target: CleanTarget) -> tuple[int, int, list[str]]:
        freed = 0
        deleted = 0
        errors: list[str] = []

        # Thumbnail cache: only delete thumbcache_*.db, not other Explorer files
        thumb_only = (
            target.name == "Thumbnail Cache"
            and "Explorer" in str(target.path)
        )

        try:
            for entry in os.scandir(target.path):
                try:
                    ep = Path(entry.path)

                    if thumb_only:
                        if not (entry.is_file() and entry.name.startswith("thumbcache_")):
                            continue

                    if entry.is_file(follow_symlinks=False):
                        size = entry.stat().st_size
                        ep.unlink(missing_ok=True)
                        freed += size
                        deleted += 1
                    elif entry.is_dir(follow_symlinks=False):
                        size, count = _dir_size(ep)
                        shutil.rmtree(ep, ignore_errors=True)
                        freed += size
                        deleted += count
                except (PermissionError, OSError) as exc:
                    errors.append(f"{entry.name}: {exc}")
        except (PermissionError, OSError) as exc:
            errors.append(f"Cannot access {target.path}: {exc}")

        return freed, deleted, errors
