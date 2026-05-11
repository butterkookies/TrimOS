"""
Deep Clean Screen — scan and remove temp files, caches, and junk.

Shows all discovered cleanup targets with sizes. User toggles
which targets to include, then confirms with C to clean.
"""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import DataTable, Static, Footer
from textual.binding import Binding
from textual.containers import Vertical
from textual import work

from ..core.cleaner import DiskCleaner, CleanTarget, CleanResult


def _fmt_size(b: int) -> str:
    if b < 1024:
        return f"{b} B"
    elif b < 1024 * 1024:
        return f"{b / 1024:.1f} KB"
    elif b < 1024 ** 3:
        return f"{b / 1024 ** 2:.1f} MB"
    return f"{b / 1024 ** 3:.2f} GB"


class DeepCleanScreen(Screen):
    """Full-screen Deep Cleaner."""

    BINDINGS = [
        Binding("space", "toggle_target", "Toggle", show=True),
        Binding("c", "clean_selected", "Clean", show=True),
        Binding("a", "select_all", "Select All", show=True),
        Binding("n", "select_none", "Select None", show=True),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("escape", "dismiss", "Close", show=True),
        Binding("q", "dismiss", "Close", show=False),
    ]

    DEFAULT_CSS = """
    DeepCleanScreen {
        background: $background;
    }
    #clean-header {
        padding: 1 2;
        background: $panel;
        border-bottom: solid $primary-darken-2;
    }
    #clean-status {
        padding: 0 2;
        height: 1;
        background: $panel;
    }
    #clean-table {
        height: 1fr;
    }
    """

    def __init__(self):
        super().__init__()
        self._cleaner = DiskCleaner()
        self._targets: list[CleanTarget] = []
        self._scanning = False
        self._cleaning = False

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(
                "[bold #ffaa00]  Deep Clean[/]  "
                "[dim]│  Temp files, caches & junk  │  "
                "[bold]Space[/][dim]=Toggle  [bold]C[/][dim]=Clean  "
                "[bold]A[/][dim]=All  [bold]N[/][dim]=None  "
                "[bold]Esc[/][dim]=Close[/]",
                id="clean-header",
            )
            yield Static("[dim]  Scanning...[/]", id="clean-status")
            yield DataTable(id="clean-table", zebra_stripes=True, cursor_type="row")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#clean-table", DataTable)
        table.add_column("Sel",      key="sel",      width=3)
        table.add_column("Name",     key="name",     width=30)
        table.add_column("Category", key="category", width=10)
        table.add_column("Size",     key="size",     width=12)
        table.add_column("Files",    key="files",    width=8)
        table.add_column("State",    key="state",    width=8)
        table.focus()
        self._do_scan()

    @work(thread=True)
    def _do_scan(self) -> None:
        self._scanning = True
        self.app.call_from_thread(
            lambda: self.query_one("#clean-status", Static).update(
                "[dim]  Scanning...[/]"
            )
        )
        self._targets = self._cleaner.get_targets()
        self.app.call_from_thread(self._render_table)
        self._scanning = False

    def _render_table(self) -> None:
        table = self.query_one("#clean-table", DataTable)
        table.clear()

        cat_colors = {"System": "#00d4ff", "Browser": "#cc66ff"}

        for target in self._targets:
            sel = "[bold #00cc66]✓[/]" if target.selected else "[dim]○[/]"
            cat_color = cat_colors.get(target.category, "#d4d4d4")
            cat_str = f"[{cat_color}]{target.category}[/]"

            if not target.accessible:
                size_str = "[dim]no access[/]"
                files_str = "[dim]—[/]"
                state_str = "[bold #888888]locked[/]"
            elif target.size_bytes == 0:
                size_str = "[dim]empty[/]"
                files_str = "[dim]0[/]"
                state_str = "[dim]clean[/]"
            else:
                size_str = f"[bold #ffaa00]{_fmt_size(target.size_bytes)}[/]"
                files_str = f"{target.file_count:,}"
                state_str = "[bold #ff4466]junk[/]"

            table.add_row(sel, target.name, cat_str, size_str, files_str, state_str)

        total_size = sum(t.size_bytes for t in self._targets if t.accessible)
        selected_size = sum(
            t.size_bytes for t in self._targets if t.selected and t.accessible
        )
        selected_count = sum(1 for t in self._targets if t.selected)

        self.query_one("#clean-status", Static).update(
            f"[dim]  {len(self._targets)} targets  │  "
            f"Total junk: [bold #ffaa00]{_fmt_size(total_size)}[/dim]  │  "
            f"Selected: [bold #00cc66]{selected_count}[/dim] "
            f"([bold #ffaa00]{_fmt_size(selected_size)}[/dim])[/]"
        )

    # ── Actions ───────────────────────────────────────────────────────────

    def action_toggle_target(self) -> None:
        row = self.query_one("#clean-table", DataTable).cursor_row
        if 0 <= row < len(self._targets):
            self._targets[row].selected = not self._targets[row].selected
            self._render_table()

    def action_select_all(self) -> None:
        for t in self._targets:
            t.selected = True
        self._render_table()

    def action_select_none(self) -> None:
        for t in self._targets:
            t.selected = False
        self._render_table()

    def action_clean_selected(self) -> None:
        if self._cleaning or self._scanning:
            self.notify("Busy — wait for scan/clean to finish", severity="warning")
            return

        to_clean = [
            t for t in self._targets
            if t.selected and t.accessible and t.size_bytes > 0
        ]
        if not to_clean:
            self.notify(
                "Nothing to clean — all selected targets are empty or inaccessible",
                severity="warning",
            )
            return

        total = _fmt_size(sum(t.size_bytes for t in to_clean))
        self._do_clean(to_clean, total)

    @work(thread=True)
    def _do_clean(self, targets: list[CleanTarget], total_str: str) -> None:
        self._cleaning = True

        self.app.call_from_thread(
            lambda: self.query_one("#clean-status", Static).update(
                f"[bold #ffaa00]  Cleaning {len(targets)} targets "
                f"(~{total_str})...[/]"
            )
        )

        result: CleanResult = self._cleaner.clean(targets)
        self._cleaning = False

        def _show_result():
            freed_str = _fmt_size(result.freed_bytes)
            severity = "warning" if result.errors else "information"
            msg = f"Freed {freed_str} — {result.files_deleted:,} files removed"
            if result.errors:
                msg += f"\n{len(result.errors)} file(s) could not be deleted (in use or locked)"
            self.notify(msg, title="Deep Clean Complete", severity=severity)
            self._do_scan()

        self.app.call_from_thread(_show_result)

    def action_refresh(self) -> None:
        if not self._scanning and not self._cleaning:
            self._do_scan()
