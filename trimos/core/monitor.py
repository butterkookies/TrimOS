"""
Real-time system resource monitor.

Polls CPU, RAM, Disk, and Network usage at configurable intervals
and maintains rolling history for sparkline graph rendering.
"""

import psutil
import time
from dataclasses import dataclass, field
from collections import deque


# How many data points to keep for sparkline history
HISTORY_SIZE = 60


@dataclass
class ResourceSnapshot:
    """A single point-in-time snapshot of system resources."""
    cpu_percent: float = 0.0
    ram_used_gb: float = 0.0
    ram_total_gb: float = 0.0
    ram_percent: float = 0.0
    disk_percent: float = 0.0
    disk_read_mb_s: float = 0.0
    disk_write_mb_s: float = 0.0
    net_sent_kb_s: float = 0.0
    net_recv_kb_s: float = 0.0
    timestamp: float = 0.0


class Monitor:
    """Polls system resources and maintains history for graphs."""

    def __init__(self, history_size: int = HISTORY_SIZE):
        self._history_size = history_size

        # Rolling histories for sparkline graphs
        self.cpu_history: deque[float] = deque(maxlen=history_size)
        self.ram_history: deque[float] = deque(maxlen=history_size)
        self.disk_history: deque[float] = deque(maxlen=history_size)
        self.net_history: deque[float] = deque(maxlen=history_size)

        # Previous counters for calculating rates
        self._prev_disk_io = psutil.disk_io_counters()
        self._prev_net_io = psutil.net_io_counters()
        self._prev_time = time.time()

        # Initialize CPU percent (first call always returns 0)
        psutil.cpu_percent(interval=None)

    def poll(self) -> ResourceSnapshot:
        """
        Take a fresh snapshot of system resources.
        Call this every 1–2 seconds for smooth graphs.
        """
        now = time.time()
        elapsed = max(now - self._prev_time, 0.01)

        # CPU
        cpu = psutil.cpu_percent(interval=None)

        # RAM
        mem = psutil.virtual_memory()
        ram_used = mem.used / (1024 ** 3)
        ram_total = mem.total / (1024 ** 3)
        ram_pct = mem.percent

        # Disk I/O rate
        disk_io = psutil.disk_io_counters()
        disk_read_rate = 0.0
        disk_write_rate = 0.0
        if disk_io and self._prev_disk_io:
            read_delta = disk_io.read_bytes - self._prev_disk_io.read_bytes
            write_delta = disk_io.write_bytes - self._prev_disk_io.write_bytes
            disk_read_rate = (read_delta / elapsed) / (1024 * 1024)   # MB/s
            disk_write_rate = (write_delta / elapsed) / (1024 * 1024)  # MB/s
        disk_pct = (disk_read_rate + disk_write_rate)  # Combined activity

        # Network I/O rate
        net_io = psutil.net_io_counters()
        net_sent_rate = 0.0
        net_recv_rate = 0.0
        if net_io and self._prev_net_io:
            sent_delta = net_io.bytes_sent - self._prev_net_io.bytes_sent
            recv_delta = net_io.bytes_recv - self._prev_net_io.bytes_recv
            net_sent_rate = (sent_delta / elapsed) / 1024  # KB/s
            net_recv_rate = (recv_delta / elapsed) / 1024  # KB/s

        # Store for next delta calculation
        self._prev_disk_io = disk_io
        self._prev_net_io = net_io
        self._prev_time = now

        # Append to histories
        self.cpu_history.append(cpu)
        self.ram_history.append(ram_pct)
        self.disk_history.append(disk_pct)
        self.net_history.append(net_sent_rate + net_recv_rate)

        return ResourceSnapshot(
            cpu_percent=round(cpu, 1),
            ram_used_gb=round(ram_used, 1),
            ram_total_gb=round(ram_total, 1),
            ram_percent=round(ram_pct, 1),
            disk_percent=round(disk_pct, 1),
            disk_read_mb_s=round(disk_read_rate, 1),
            disk_write_mb_s=round(disk_write_rate, 1),
            net_sent_kb_s=round(net_sent_rate, 1),
            net_recv_kb_s=round(net_recv_rate, 1),
            timestamp=now,
        )

    def get_health_score(self, snapshot: ResourceSnapshot) -> int:
        """
        Calculate a system health score from 0–100.
        100 = totally idle, 0 = completely maxed out.
        """
        # Weighted formula
        cpu_score = max(0, 100 - snapshot.cpu_percent)
        ram_score = max(0, 100 - snapshot.ram_percent)
        disk_score = max(0, 100 - min(snapshot.disk_percent * 2, 100))

        score = int(cpu_score * 0.4 + ram_score * 0.45 + disk_score * 0.15)
        return max(0, min(100, score))
