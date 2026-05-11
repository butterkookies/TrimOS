"""
Advanced Analytics Screen — system health trend analysis.

Shows CPU, RAM, and Health sparklines over the last hour and last 24 hours,
with computed statistics (average, peak, minimum) for each window.
"""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Footer
from textual.binding import Binding
from textual.containers import Vertical, Horizontal
from rich.text import Text

from ..core.analytics import AnalyticsStore, MetricPoint, MetricStats
from ..widgets.perf_graphs import make_sparkline, SPARK_CHARS


def _health_color(score: float) -> str:
    if score >= 70:
        return "#00cc66"
    elif score >= 40:
        return "#ffaa00"
    return "#ff4466"


def _pct_color(pct: float) -> str:
    if pct < 35:
        return "#00cc66"
    elif pct < 65:
        return "#ffaa00"
    return "#ff4466"


def _render_trend_block(
    title: str,
    points: list[MetricPoint],
    stats: MetricStats | None,
    graph_width: int,
    window_label: str,
) -> Text:
    """Render one trend block: title, three sparklines, stats row."""
    text = Text()

    cpu_vals  = [p.cpu    for p in points]
    ram_vals  = [p.ram    for p in points]
    hlth_vals = [float(p.health) for p in points]

    # ── Window label ──
    text.append(f" {window_label}\n", style="bold #888888")

    # ── CPU sparkline ──
    text.append(" CPU    ", style="bold #00d4ff")
    text.append_text(make_sparkline(cpu_vals, graph_width, max_val=100.0))
    if stats:
        text.append(
            f"  avg {stats.avg_cpu:5.1f}%  peak {stats.peak_cpu:5.1f}%\n",
            style=f"bold {_pct_color(stats.avg_cpu)}",
        )
    else:
        text.append("  no data\n", style="dim")

    # ── RAM sparkline ──
    text.append(" RAM    ", style="bold #00cc66")
    text.append_text(make_sparkline(ram_vals, graph_width, max_val=100.0,
                                    color_low="#00cc66", color_mid="#ffaa00", color_high="#ff4466"))
    if stats:
        text.append(
            f"  avg {stats.avg_ram:5.1f}%  peak {stats.peak_ram:5.1f}%\n",
            style=f"bold {_pct_color(stats.avg_ram)}",
        )
    else:
        text.append("  no data\n", style="dim")

    # ── Health sparkline ──
    text.append(" HEALTH ", style="bold #cc66ff")
    text.append_text(make_sparkline(hlth_vals, graph_width, max_val=100.0,
                                    color_low="#ff4466", color_mid="#ffaa00", color_high="#00cc66"))
    if stats:
        hc = _health_color(stats.avg_health)
        text.append(
            f"  avg {stats.avg_health:5.1f}   low  {stats.low_health:5d}\n",
            style=f"bold {hc}",
        )
    else:
        text.append("  no data\n", style="dim")

    return text


class AnalyticsScreen(Screen):
    """Advanced trend analysis — last hour and last 24 hours."""

    BINDINGS = [
        Binding("r", "refresh", "Refresh", show=True),
        Binding("escape", "dismiss", "Close", show=True),
        Binding("q", "dismiss", "Close", show=False),
    ]

    DEFAULT_CSS = """
    AnalyticsScreen {
        background: $background;
    }
    #analytics-header {
        padding: 1 2;
        background: $panel;
        border-bottom: solid $primary-darken-2;
    }
    #analytics-meta {
        padding: 0 2;
        height: 1;
        background: $panel;
    }
    #analytics-body {
        padding: 1 0;
        height: 1fr;
    }
    #hour-block {
        height: auto;
        padding: 0 1;
        border-bottom: solid $panel-lighten-1;
    }
    #day-block {
        height: auto;
        padding: 0 1;
    }
    """

    def __init__(self, store: AnalyticsStore):
        super().__init__()
        self._store = store

    def compose(self) -> ComposeResult:
        yield Static(
            "[bold #00d4ff]  Advanced Analytics[/]  "
            "[dim]│  System health trend analysis  │  "
            "[bold]R[/][dim]=Refresh  [bold]Esc[/][dim]=Close[/]",
            id="analytics-header",
        )
        yield Static("", id="analytics-meta")
        with Vertical(id="analytics-body"):
            yield Static("", id="hour-block")
            yield Static("", id="day-block")
        yield Footer()

    def on_mount(self) -> None:
        self._render_analytics()

    def _render_analytics(self) -> None:
        total = self._store.total_samples
        oldest_str = "—"
        if total > 0:
            pts_all = self._store.get_last_n_minutes(MAX_POINTS := 1440)
            if pts_all:
                import time as _time
                age_min = (_time.time() - pts_all[0].timestamp) / 60
                if age_min >= 60:
                    oldest_str = f"{age_min / 60:.1f}h of data"
                else:
                    oldest_str = f"{age_min:.0f}m of data"

        self.query_one("#analytics-meta", Static).update(
            f"[dim]  {total} samples stored  │  {oldest_str}[/]"
        )

        # Determine graph width from screen
        graph_width = max(self.size.width - 40, 20)

        # ── Last 60 minutes ──
        hour_pts = self._store.get_last_n_minutes(60)
        hour_stats = self._store.get_stats(hour_pts)

        if hour_pts:
            hour_text = _render_trend_block(
                "Last Hour", hour_pts, hour_stats, graph_width, "── Last 60 minutes ──"
            )
        else:
            hour_text = Text(" ── Last 60 minutes ──\n [dim]No data yet — check back after one minute.[/]")

        self.query_one("#hour-block", Static).update(hour_text)

        # ── Last 24 hours (downsample to graph_width points) ──
        day_pts = self._store.get_last_n_minutes(1440)
        day_stats = self._store.get_stats(day_pts)

        if day_pts:
            # Downsample: bucket into graph_width buckets
            downsampled = _downsample(day_pts, graph_width)
            day_text = _render_trend_block(
                "Last 24h", downsampled, day_stats, graph_width, "── Last 24 hours ──"
            )
        else:
            day_text = Text(" ── Last 24 hours ──\n [dim]No data yet.[/]")

        self.query_one("#day-block", Static).update(day_text)

    def action_refresh(self) -> None:
        self._render_analytics()
        self.notify("Refreshed", severity="information")

    def on_resize(self) -> None:
        self._render_analytics()


def _downsample(points: list[MetricPoint], target: int) -> list[MetricPoint]:
    """Average-downsample a list of MetricPoints to at most `target` entries."""
    if len(points) <= target:
        return points

    bucket_size = len(points) / target
    result: list[MetricPoint] = []

    for i in range(target):
        start = int(i * bucket_size)
        end = int((i + 1) * bucket_size)
        bucket = points[start:end]
        if not bucket:
            continue
        avg_cpu  = sum(p.cpu    for p in bucket) / len(bucket)
        avg_ram  = sum(p.ram    for p in bucket) / len(bucket)
        avg_disk = sum(p.disk   for p in bucket) / len(bucket)
        avg_net  = sum(p.net_kb_s for p in bucket) / len(bucket)
        avg_h    = int(sum(p.health for p in bucket) / len(bucket))
        result.append(MetricPoint(
            timestamp=bucket[-1].timestamp,
            cpu=round(avg_cpu, 1),
            ram=round(avg_ram, 1),
            disk=round(avg_disk, 1),
            net_kb_s=round(avg_net, 1),
            health=avg_h,
        ))

    return result
