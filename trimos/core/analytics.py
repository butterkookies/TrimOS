"""
Analytics store — persistent time-series metrics for trend analysis.

Records one data point per minute (aggregated from real-time polls),
keeps up to 24 hours of history, persists to JSON on disk.
"""

import json
import os
import time
from dataclasses import dataclass, asdict
from collections import deque
from typing import Optional


# 24 hours at one sample per minute
MAX_POINTS = 1440
# Seconds between persisted samples
SAMPLE_INTERVAL = 60


@dataclass
class MetricPoint:
    """One minute of system metrics (averaged from real-time polls)."""
    timestamp: float
    cpu: float
    ram: float
    disk: float
    net_kb_s: float
    health: int


@dataclass
class MetricStats:
    """Computed statistics over a slice of MetricPoints."""
    avg_cpu: float
    peak_cpu: float
    avg_ram: float
    peak_ram: float
    avg_health: float
    low_health: int
    avg_net_kb_s: float
    peak_net_kb_s: float
    sample_count: int


class AnalyticsStore:
    """
    Accumulates real-time poll data, aggregates into per-minute samples,
    persists to disk, and provides stats for the analytics screen.
    """

    def __init__(self, path: str):
        self._path = path
        self._points: deque[MetricPoint] = deque(maxlen=MAX_POINTS)

        # Accumulator for current minute
        self._acc: list[tuple[float, float, float, float, int]] = []  # cpu, ram, disk, net, health
        self._last_sample_time: float = time.time()

        self._load()

    # ── Recording ────────────────────────────────────────────

    def record(self, cpu: float, ram: float, disk: float, net_kb_s: float, health: int) -> None:
        """
        Called on every real-time poll (~1.5s).
        Accumulates data; flushes a sample once per minute.
        """
        self._acc.append((cpu, ram, disk, net_kb_s, health))

        now = time.time()
        if now - self._last_sample_time >= SAMPLE_INTERVAL:
            self._flush_sample(now)

    def _flush_sample(self, now: float) -> None:
        """Average accumulator into a single MetricPoint and store it."""
        if not self._acc:
            return

        count = len(self._acc)
        avg_cpu   = sum(x[0] for x in self._acc) / count
        avg_ram   = sum(x[1] for x in self._acc) / count
        avg_disk  = sum(x[2] for x in self._acc) / count
        avg_net   = sum(x[3] for x in self._acc) / count
        avg_health = int(sum(x[4] for x in self._acc) / count)

        self._points.append(MetricPoint(
            timestamp=now,
            cpu=round(avg_cpu, 1),
            ram=round(avg_ram, 1),
            disk=round(avg_disk, 1),
            net_kb_s=round(avg_net, 1),
            health=avg_health,
        ))

        self._acc.clear()
        self._last_sample_time = now
        self._save()

    # ── Queries ──────────────────────────────────────────────

    def get_last_n_minutes(self, n: int) -> list[MetricPoint]:
        """Return up to the last n MetricPoints (one per minute)."""
        pts = list(self._points)
        return pts[-n:] if len(pts) >= n else pts

    def get_stats(self, points: list[MetricPoint]) -> Optional[MetricStats]:
        """Compute aggregate statistics over a list of MetricPoints."""
        if not points:
            return None
        return MetricStats(
            avg_cpu=round(sum(p.cpu for p in points) / len(points), 1),
            peak_cpu=round(max(p.cpu for p in points), 1),
            avg_ram=round(sum(p.ram for p in points) / len(points), 1),
            peak_ram=round(max(p.ram for p in points), 1),
            avg_health=round(sum(p.health for p in points) / len(points), 1),
            low_health=min(p.health for p in points),
            avg_net_kb_s=round(sum(p.net_kb_s for p in points) / len(points), 1),
            peak_net_kb_s=round(max(p.net_kb_s for p in points), 1),
            sample_count=len(points),
        )

    @property
    def total_samples(self) -> int:
        return len(self._points)

    # ── Persistence ──────────────────────────────────────────

    def _save(self) -> None:
        """Persist all points to JSON."""
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(
                    [asdict(p) for p in self._points],
                    f,
                    separators=(",", ":"),
                )
        except OSError:
            pass

    def _load(self) -> None:
        """Load persisted points from JSON."""
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            for item in raw[-MAX_POINTS:]:
                self._points.append(MetricPoint(**item))
        except (FileNotFoundError, json.JSONDecodeError, TypeError):
            pass
