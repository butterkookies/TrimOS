"""
Performance graph widgets — sparkline rows + helper functions for analytics.

PerfGraphs renders 4 inline sparkline rows (CPU/RAM/DISK/NET).
make_sparkline / make_bar retained for analytics_screen.py.
"""

from textual.widget import Widget
from rich.text import Text
from collections import deque


# Braille-style sparkline chars (8 levels) — renders cleanly in most terminals
SPARK_CHARS = "▁▂▃▄▅▆▇█"


def make_sparkline(
    values: list[float] | deque[float],
    width: int = 40,
    max_val: float | None = None,
    color_low: str = "#00cc66",
    color_mid: str = "#ffaa00",
    color_high: str = "#ff4466",
) -> Text:
    """
    Render a sparkline from a list of values.
    Returns a Rich Text object with gradient coloring.
    If max_val is None, auto-scales to the window's peak value.
    """
    text = Text()

    if not values:
        text.append("▁" * width, style="bright_black")
        return text

    # Take the last `width` values, pad left with zeros
    data = list(values)[-width:]
    while len(data) < width:
        data.insert(0, 0.0)

    scale = max_val if max_val is not None else max(max(data), 0.01)

    for val in data:
        normalized = max(0.0, min(val / max(scale, 0.01), 1.0))
        idx = int(normalized * (len(SPARK_CHARS) - 1))
        char = SPARK_CHARS[idx]

        # Color gradient based on value
        if normalized < 0.35:
            style = color_low
        elif normalized < 0.65:
            style = color_mid
        else:
            style = color_high

        text.append(char, style=style)

    return text


def make_bar(
    percent: float,
    width: int = 40,
    color_low: str = "#00cc66",
    color_mid: str = "#ffaa00",
    color_high: str = "#ff4466",
) -> Text:
    """Render a percentage bar with filled/empty segments."""
    text = Text()
    filled = int((percent / 100.0) * width)
    empty = width - filled

    # Pick color based on percent
    if percent < 55:
        bar_color = color_low
    elif percent < 80:
        bar_color = color_mid
    else:
        bar_color = color_high

    text.append("█" * filled, style=bar_color)
    text.append("▒" * empty, style="bright_black")
    return text


class PerfGraphs(Widget):
    """
    Real-time performance panel — 4 inline sparkline rows.
    CPU / RAM / DISK / NET, each label + sparkline on one line.
    """

    DEFAULT_CSS = """
    PerfGraphs {
        height: auto;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cpu_history: deque[float] = deque(maxlen=60)
        self.ram_history: deque[float] = deque(maxlen=60)
        self.disk_history: deque[float] = deque(maxlen=60)
        self.net_history: deque[float] = deque(maxlen=60)
        self.cpu_percent: float = 0.0
        self.ram_percent: float = 0.0
        self.ram_used: float = 0.0
        self.ram_total: float = 0.0
        self.disk_rate: float = 0.0
        self.net_rate: float = 0.0

    def update_data(
        self,
        cpu_hist: deque[float],
        ram_hist: deque[float],
        disk_hist: deque[float],
        net_hist: deque[float],
        cpu_pct: float,
        ram_pct: float,
        ram_used: float,
        ram_total: float,
        disk_rate: float,
        net_rate: float,
    ) -> None:
        """Push new data and trigger re-render."""
        self.cpu_history = cpu_hist
        self.ram_history = ram_hist
        self.disk_history = disk_hist
        self.net_history = net_hist
        self.cpu_percent = cpu_pct
        self.ram_percent = ram_pct
        self.ram_used = ram_used
        self.ram_total = ram_total
        self.disk_rate = disk_rate
        self.net_rate = net_rate
        self.refresh()

    def render(self) -> Text:
        """Render 4 inline sparkline rows: CPU / RAM / DISK / NET."""
        w = max(self.size.width - 2, 20)

        cpu_data  = list(self.cpu_history)  or [0.0]
        ram_data  = list(self.ram_history)  or [0.0]
        disk_data = list(self.disk_history) or [0.0]
        net_data  = list(self.net_history)  or [0.0]

        label_w = 26
        spark_w = max(w - label_w, 10)

        text = Text()

        # CPU
        cpu_label = f" CPU   {self.cpu_percent:5.1f}%"
        text.append(f"{cpu_label:<{label_w}}", style="bold #00d4ff")
        text.append(make_sparkline(cpu_data, width=spark_w, max_val=100))
        text.append("\n")

        # RAM
        ram_label = f" RAM   {self.ram_used:.1f}/{self.ram_total:.0f}G ({self.ram_percent:.0f}%)"
        text.append(f"{ram_label:<{label_w}}", style="bold #00cc66")
        text.append(make_sparkline(ram_data, width=spark_w, max_val=100))
        text.append("\n")

        # DISK (auto-scale)
        disk_peak = max(max(disk_data), 0.1)
        disk_label = f" DISK  {self.disk_rate:.1f} M/s"
        text.append(f"{disk_label:<{label_w}}", style="bold #ffaa00")
        text.append(make_sparkline(disk_data, width=spark_w, max_val=disk_peak))
        text.append("\n")

        # NET (auto-scale)
        net_val = self.net_rate
        net_str = f"{net_val / 1024:.1f} M/s" if net_val > 1024 else f"{net_val:.1f} K/s"
        net_label = f" NET   ↑↓ {net_str}"
        net_peak = max(max(net_data), 0.1)
        text.append(f"{net_label:<{label_w}}", style="bold #cc66ff")
        text.append(make_sparkline(net_data, width=spark_w, max_val=net_peak))

        return text
