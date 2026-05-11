"""
TrimOS — Main Textual Application.

The central app that composes all widgets, handles input,
and orchestrates the scanner, monitor, optimizer, and intelligence.

Features:
  - Real-time performance monitoring with sparkline graphs
  - Smart service intelligence (what it does, why, should you close it)
  - Bulk close all trimmable services with confirmation
  - Whitelist/protect services from bulk operations
  - Bloatware identification and cleanup
"""

import os
import shutil
import sys
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Static, Footer
from textual.reactive import reactive
from textual import work

from .widgets.mascot import Mascot
from .widgets.perf_graphs import PerfGraphs
from .widgets.service_table import ServiceTable
from .widgets.detail_panel import DetailPanel
from .core.scanner import Scanner, SystemItem, SafetyLevel
from .core.monitor import Monitor
from .core.optimizer import Optimizer, OptimizeResult
from .core.snapshots import SnapshotManager
from .core.whitelist import Whitelist
from .screens.confirm_screen import ConfirmBulkClose
from .screens.startup_screen import StartupScreen
from .screens.analytics_screen import AnalyticsScreen
from .screens.deep_clean_screen import DeepCleanScreen
from .core.analytics import AnalyticsStore
from .core.elevation import is_admin, restart_as_admin, enable_vt_mode
from .core.paths import get_data_dir, get_bundled_data_dir


# Writable user data (whitelist, analytics, snapshots)
DATA_DIR = get_data_dir()
# Read-only bundled data (services.json)
BUNDLED_DATA_DIR = get_bundled_data_dir()


class TrimOS(App):
    """TrimOS — Your friendly Windows optimizer."""

    TITLE = "TrimOS"
    SUB_TITLE = "System Optimizer"

    CSS_PATH = "styles/trimos.tcss"

    BINDINGS = [
        Binding("x", "bulk_close", "Bulk Close", show=True),
        Binding("p", "toggle_protect", "Protect", show=True),
        Binding("e", "stop_selected", "Stop/Start", show=True),
        Binding("o", "optimize", "Optimize", show=True),
        Binding("g", "gaming_mode", "Gaming", show=False),
        Binding("w", "work_mode", "Work", show=False),
        Binding("r", "restore", "Restore", show=True),
        Binding("s", "scan", "Rescan", show=True),
        Binding("f", "cycle_filter", "Filter", show=True),
        Binding("1", "sort_ram", "Sort:RAM", show=False),
        Binding("2", "sort_cpu", "Sort:CPU", show=False),
        Binding("3", "sort_name", "Sort:Name", show=False),
        Binding("4", "sort_safety", "Sort:Safety", show=False),
        Binding("u", "startup_manager", "Startup", show=True),
        Binding("a", "analytics", "Analytics", show=True),
        Binding("d", "deep_clean", "Deep Clean", show=True),
        Binding("q", "quit", "Quit", show=True),
        Binding("ctrl+r", "restart_admin", "↑ Run as Admin", show=True),
    ]

    # Current state
    filter_mode = reactive("all")
    health_score = reactive(100)
    trimmable_count = reactive(0)
    trimmable_ram = reactive(0.0)

    def __init__(self):
        super().__init__()
        self._is_admin = is_admin()
        self._seed_writable_data()
        self.whitelist = Whitelist(str(DATA_DIR / "whitelist.json"))
        self.scanner = Scanner(str(BUNDLED_DATA_DIR / "services.json"))
        self.monitor = Monitor()
        self.optimizer = Optimizer(whitelist=self.whitelist)
        self.snapshots = SnapshotManager(str(DATA_DIR / "snapshots"))
        self.analytics = AnalyticsStore(str(DATA_DIR / "analytics.json"))
        self._items: list[SystemItem] = []
        self._monitor_timer = None
        self._filter_options = [
            "all", "trimmable", "bloatware", "running",
            "services", "processes", "protected",
        ]
        self._filter_index = 0

    def _seed_writable_data(self) -> None:
        """
        On first launch from a frozen build, copy bundled default data
        (whitelist.json, analytics.json) into the writable user-data dir
        so they can be modified at runtime.
        """
        from .core.paths import _is_frozen
        if not _is_frozen():
            return
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        (DATA_DIR / "snapshots").mkdir(parents=True, exist_ok=True)
        for fname in ("whitelist.json", "analytics.json"):
            dest = DATA_DIR / fname
            src = BUNDLED_DATA_DIR / fname
            if not dest.exists() and src.exists():
                shutil.copy2(str(src), str(dest))

    def compose(self) -> ComposeResult:
        """Build the TUI layout."""

        # ── Header bar ──
        with Horizontal(id="header-bar"):
            yield Static("", id="header-left")
            yield Static("", id="header-right")

        # ── Top section: mascot + performance graphs ──
        with Horizontal(id="top-section"):
            with Vertical(id="mascot-panel"):
                yield Mascot(id="mascot")
            yield PerfGraphs(id="perf-panel")

        # ── Table section ──
        with Vertical(id="table-section"):
            with Horizontal(id="table-info-bar"):
                yield Static("", id="table-title")
                yield Static("[dim]filter: all[/]", id="filter-label")
                yield Static("", id="trimmable-label")
            yield ServiceTable(id="service-table")

        # ── Detail panel ──
        yield DetailPanel(id="detail-panel")

        # ── Footer ──
        yield Footer()

    def on_mount(self) -> None:
        """Initialize everything when the app starts."""
        mascot = self.query_one("#mascot", Mascot)
        mascot.set_state("scanning")

        # Show admin status in header
        self._update_admin_display()

        # Start the resource monitor
        self._monitor_timer = self.set_interval(1.5, self._poll_resources)

        # Do initial scan
        self._do_scan()

    def _update_admin_display(self) -> None:
        """Reflect admin status in the header."""
        header = self.query_one("#header-left", Static)
        base = "[bold #00d4ff]TrimOS[/] [dim]v2.0.0[/] [dim]│[/] [dim]Smart System Optimizer[/]"
        if self._is_admin:
            suffix = "  [bold #00cc66]✔ Admin[/]"
        else:
            suffix = "  [bold #ff4466]⚠ Not Admin[/] [dim](Ctrl+R to elevate)[/]"
        header.update(base + suffix)

    # ─── Resource Monitoring ──────────────────────────────

    def _poll_resources(self) -> None:
        """Poll system resources and update graphs."""
        snapshot = self.monitor.poll()
        self.health_score = self.monitor.get_health_score(snapshot)

        # Update performance graphs
        perf = self.query_one("#perf-panel", PerfGraphs)
        perf.update_data(
            cpu_hist=self.monitor.cpu_history,
            ram_hist=self.monitor.ram_history,
            disk_hist=self.monitor.disk_history,
            net_hist=self.monitor.net_history,
            cpu_pct=snapshot.cpu_percent,
            ram_pct=snapshot.ram_percent,
            ram_used=snapshot.ram_used_gb,
            ram_total=snapshot.ram_total_gb,
            disk_rate=snapshot.disk_read_mb_s + snapshot.disk_write_mb_s,
            net_rate=snapshot.net_sent_kb_s + snapshot.net_recv_kb_s,
        )

        # Update header health score
        score = self.health_score
        if score >= 70:
            color = "#00cc66"
            icon = "●"
        elif score >= 40:
            color = "#ffaa00"
            icon = "●"
        else:
            color = "#ff4466"
            icon = "●"

        self.query_one("#header-right", Static).update(
            f"[{color}]{icon}[/] [{color}]Health: {score}/100[/]"
        )

        # Feed analytics store (aggregates to one sample/minute internally)
        self.analytics.record(
            cpu=snapshot.cpu_percent,
            ram=snapshot.ram_percent,
            disk=snapshot.disk_percent,
            net_kb_s=snapshot.net_sent_kb_s + snapshot.net_recv_kb_s,
            health=score,
        )

        # Update mascot based on health — only when state bucket changes
        mascot = self.query_one("#mascot", Mascot)
        if mascot.state not in ("scanning", "optimizing", "optimized"):
            target_state = "stressed" if score < 40 else "idle"
            if mascot.state != target_state:
                mascot.set_state(target_state)

    # ─── Scanning ─────────────────────────────────────────

    @work(thread=True)
    def _do_scan(self) -> None:
        """Scan services and processes in a background thread."""
        self.app.call_from_thread(
            lambda: self.query_one("#mascot", Mascot).set_state("scanning")
        )

        items = self.scanner.scan_all()

        # Mark protected items
        for item in items:
            item.is_protected = self.whitelist.is_protected(item.name)

        self._items = items

        # Count trimmable items (excluding protected)
        trimmable = [
            i for i in items
            if i.safety == SafetyLevel.TRIMMABLE
            and i.status == "running"
            and not self.whitelist.is_protected(i.name)
        ]
        running_count = sum(1 for i in items if i.status == "running")
        bloat_count = sum(
            1 for i in items if i.bloatware and i.status == "running"
        )

        def _update_ui():
            table = self.query_one("#service-table", ServiceTable)
            table.load_items(items, self.whitelist.protected_names)

            self.trimmable_count = len(trimmable)
            self.trimmable_ram = sum(i.ram_mb for i in trimmable)

            # Update table title
            bloat_info = f" [bold #ff4466]🗑{bloat_count} bloat[/]" if bloat_count else ""
            protect_count = self.whitelist.count
            protect_info = f" [bold #ffaa00]🛡{protect_count}[/]" if protect_count else ""
            self.query_one("#table-title", Static).update(
                f"[bold #d4d4d4]Services & Processes[/] "
                f"[dim]({running_count} running / {len(items)} total)[/]"
                f"{bloat_info}{protect_info}"
            )

            # Update trimmable label
            self._update_trimmable_display()

            # Mascot back to idle
            self.query_one("#mascot", Mascot).set_state("idle")

        self.app.call_from_thread(_update_ui)

    def _update_trimmable_display(self) -> None:
        """Update the trimmable items info in the status bar."""
        label = self.query_one("#trimmable-label", Static)
        if self.trimmable_count > 0:
            label.update(
                f"[bold #ff4466]{self.trimmable_count} trimmable "
                f"(~{self.trimmable_ram:.0f} MB)[/]"
            )
        else:
            label.update("[bold #00cc66]optimized[/]")

    # ─── Detail Panel Updates ─────────────────────────────

    def on_service_table_row_highlighted(
        self, event: ServiceTable.RowHighlighted
    ) -> None:
        """Update the detail panel when a row is highlighted."""
        panel = self.query_one("#detail-panel", DetailPanel)
        if event.item:
            is_protected = self.whitelist.is_protected(event.item.name)
            panel.set_item(event.item, is_protected)
        else:
            panel.set_item(None)

    # ─── Protection / Whitelist ───────────────────────────

    def action_toggle_protect(self) -> None:
        """Toggle protection on the currently selected service."""
        table = self.query_one("#service-table", ServiceTable)
        item = table.get_selected_item()
        if not item:
            self.notify("No service selected", severity="warning")
            return

        is_now_protected = self.whitelist.toggle(item.name)
        item.is_protected = is_now_protected

        # Update the table
        table.update_protection(self.whitelist.protected_names)

        # Update detail panel
        panel = self.query_one("#detail-panel", DetailPanel)
        panel.set_item(item, is_now_protected)

        # Recalculate trimmable count
        trimmable = [
            i for i in self._items
            if i.safety == SafetyLevel.TRIMMABLE
            and i.status == "running"
            and not self.whitelist.is_protected(i.name)
        ]
        self.trimmable_count = len(trimmable)
        self.trimmable_ram = sum(i.ram_mb for i in trimmable)
        self._update_trimmable_display()

        if is_now_protected:
            self.notify(
                f"🛡️ {item.display_name} is now PROTECTED — "
                f"excluded from bulk operations",
                title="Protected",
                severity="information",
            )
        else:
            self.notify(
                f"✕ {item.display_name} protection removed — "
                f"will be included in bulk operations",
                title="Unprotected",
                severity="warning",
            )

    # ─── Stop/Start Individual Service ────────────────────

    def action_stop_selected(self) -> None:
        """Stop or start the currently selected service."""
        table = self.query_one("#service-table", ServiceTable)
        item = table.get_selected_item()
        if not item:
            self.notify("No service selected", severity="warning")
            return

        if item.safety == SafetyLevel.ESSENTIAL:
            self.notify(
                f"🔒 {item.display_name} is ESSENTIAL — cannot stop",
                title="Protected",
                severity="error",
            )
            return

        self._do_stop_start(item)

    @work(thread=True)
    def _do_stop_start(self, item: SystemItem) -> None:
        """Stop or start a single service in a background thread."""
        if item.status == "running":
            if item.item_type.value == "service":
                success, msg = self.optimizer.stop_service(item.name)
            else:
                success, msg = self.optimizer.kill_process(item.name)

            def _notify():
                if success:
                    self.notify(
                        f"Stopped {item.display_name}",
                        title="Service Stopped",
                        severity="information",
                    )
                else:
                    hint = "" if self._is_admin else " — try Ctrl+R (run as Admin)"
                    self.notify(
                        f"Failed: {msg}{hint}",
                        title="Error",
                        severity="error",
                    )
            self.app.call_from_thread(_notify)
        else:
            if item.item_type.value == "service":
                success, msg = self.optimizer.start_service(item.name)

                def _notify():
                    if success:
                        self.notify(
                            f"Started {item.display_name}",
                            title="Service Started",
                            severity="information",
                        )
                    else:
                        self.notify(
                            f"Failed: {msg}",
                            title="Error",
                            severity="error",
                        )
                self.app.call_from_thread(_notify)
            else:
                self.app.call_from_thread(
                    lambda: self.notify(
                        "Cannot restart a killed process",
                        severity="warning",
                    )
                )

        import time
        time.sleep(1)
        self._do_scan()

    # ─── Bulk Close with Confirmation ─────────────────────

    def action_bulk_close(self) -> None:
        """Show confirmation dialog then bulk-close all trimmable services."""
        self._show_bulk_confirm("default")

    def _show_bulk_confirm(self, mode: str) -> None:
        """Show the bulk close confirmation modal."""
        targets = self.optimizer.get_bulk_targets(self._items, mode=mode)

        if not targets:
            mode_labels = {
                "default": "trimmable",
                "bloatware": "bloatware",
                "gaming": "non-essential",
                "work": "non-work",
            }
            self.notify(
                f"No {mode_labels.get(mode, 'eligible')} services to close — already clean!",
                title="All Good",
                severity="warning",
            )
            return

        self.push_screen(
            ConfirmBulkClose(targets, mode=mode),
            callback=lambda confirmed: self._on_bulk_confirmed(confirmed, mode),
        )

    def _on_bulk_confirmed(self, confirmed: bool, mode: str) -> None:
        """Handle the bulk close confirmation result."""
        if confirmed:
            self._run_optimize(mode)
        else:
            self.notify("Bulk close cancelled", severity="information")

    # ─── Optimization Actions ─────────────────────────────

    def action_optimize(self) -> None:
        """Run default optimization — stop all trimmable services."""
        self._show_bulk_confirm("default")

    def action_gaming_mode(self) -> None:
        """Run gaming optimization — aggressive mode."""
        self._show_bulk_confirm("gaming")

    def action_work_mode(self) -> None:
        """Run work optimization — keep productivity apps."""
        self._show_bulk_confirm("work")

    @work(thread=True)
    def _run_optimize(self, mode: str) -> None:
        """Execute optimization in a background thread."""
        self.app.call_from_thread(
            lambda: self.query_one("#mascot", Mascot).set_state("optimizing")
        )

        # Save snapshot before changes
        self.snapshots.save(self._items, label=mode)

        # Run optimization
        result = self.optimizer.optimize(self._items, mode=mode)

        def _show_result():
            mascot = self.query_one("#mascot", Mascot)
            if result.stopped:
                mascot.set_state("optimized")
                msg = (
                    f"Stopped {len(result.stopped)} items — "
                    f"freed ~{result.ram_freed_mb:.0f} MB"
                )
                if result.protected_skipped:
                    msg += (
                        f"\n🛡️ Skipped {len(result.protected_skipped)} "
                        f"protected services"
                    )
                self.notify(
                    msg,
                    title="Optimization Complete",
                    severity="information",
                )
            else:
                mascot.set_state("idle")
                self.notify(
                    "Nothing to optimize — already clean!",
                    title="All Good",
                    severity="warning",
                )

            if result.failed:
                if self._is_admin:
                    msg = f"{len(result.failed)} items failed (service may be locked)"
                else:
                    msg = (
                        f"{len(result.failed)} items failed — needs admin. "
                        f"Press Ctrl+R to restart elevated."
                    )
                self.notify(msg, title="Some Failures", severity="warning")

        self.app.call_from_thread(_show_result)

        # Re-scan after a short delay
        import time
        time.sleep(1.5)
        self._do_scan()

    def action_restore(self) -> None:
        """Restore from the latest snapshot."""
        self._do_restore()

    @work(thread=True)
    def _do_restore(self) -> None:
        """Restore services from the latest snapshot."""
        latest = self.snapshots.get_latest()
        if not latest:
            self.app.call_from_thread(
                lambda: self.notify(
                    "No snapshots found. Run an optimization first.",
                    title="No Snapshot",
                    severity="warning",
                )
            )
            return

        items = self.snapshots.load(latest)
        restored = 0

        for item_data in items:
            if item_data.get("status") == "running":
                name = item_data["name"]
                success, _ = self.optimizer.start_service(name)
                if success:
                    restored += 1

        def _notify():
            self.notify(
                f"Restored {restored} services from snapshot.",
                title="Restore Complete",
                severity="information",
            )

        self.app.call_from_thread(_notify)

        import time
        time.sleep(1)
        self._do_scan()

    def action_scan(self) -> None:
        """Trigger a manual re-scan."""
        self._do_scan()

    def action_startup_manager(self) -> None:
        """Open the Startup Manager screen."""
        self.push_screen(StartupScreen())

    def action_analytics(self) -> None:
        """Open the Advanced Analytics screen."""
        self.push_screen(AnalyticsScreen(self.analytics))

    def action_deep_clean(self) -> None:
        """Open the Deep Clean screen."""
        self.push_screen(DeepCleanScreen())

    def action_cycle_filter(self) -> None:
        """Cycle through filter options."""
        self._filter_index = (self._filter_index + 1) % len(self._filter_options)
        filter_name = self._filter_options[self._filter_index]

        table = self.query_one("#service-table", ServiceTable)
        table.set_filter(filter_name)

        # Show filter label with icon
        filter_icons = {
            "all": "◉ all",
            "trimmable": "🔴 trimmable",
            "bloatware": "🗑️ bloatware",
            "running": "● running",
            "services": "⚙ services",
            "processes": "📦 processes",
            "protected": "🛡️ protected",
        }
        display = filter_icons.get(filter_name, filter_name)

        label = self.query_one("#filter-label", Static)
        label.update(f"[dim]filter: {display}[/]")

    def action_sort_ram(self) -> None:
        self.query_one("#service-table", ServiceTable).set_sort("ram")

    def action_sort_cpu(self) -> None:
        self.query_one("#service-table", ServiceTable).set_sort("cpu")

    def action_sort_name(self) -> None:
        self.query_one("#service-table", ServiceTable).set_sort("name")

    def action_sort_safety(self) -> None:
        self.query_one("#service-table", ServiceTable).set_sort("safety")

    # ─── Admin Elevation ───────────────────────────────────

    def action_restart_admin(self) -> None:
        """Re-launch TrimOS with admin privileges via UAC."""
        if self._is_admin:
            self.notify(
                "Already running as Administrator.",
                title="Admin",
                severity="information",
            )
            return
        self.notify(
            "Requesting elevation — UAC prompt will appear...",
            title="Restarting as Admin",
            severity="warning",
        )
        # Brief delay so the toast is visible before exit
        import threading
        def _do_elevate():
            import time
            time.sleep(0.8)
            restart_as_admin()
            self.call_from_thread(self.exit)
        threading.Thread(target=_do_elevate, daemon=True).start()

    def check_action(self, action: str, parameters: tuple) -> bool:
        """Hide the restart_admin binding when already elevated."""
        if action == "restart_admin" and self._is_admin:
            return False
        return True


def main():
    """Entry point for TrimOS."""
    enable_vt_mode()
    app = TrimOS()
    app.run()


if __name__ == "__main__":
    main()
