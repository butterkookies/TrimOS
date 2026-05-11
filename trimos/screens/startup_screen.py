"""
Startup Manager Screen — view and toggle Windows startup entries.

Shows all HKCU and HKLM Run key entries. Toggle enable/disable
via StartupApproved (same as Task Manager). Delete removes permanently.
"""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import DataTable, Static, Footer
from textual.binding import Binding
from textual.containers import Vertical

from ..core.startup import StartupManager, StartupEntry


class StartupScreen(Screen):
    """Full-screen Startup Manager."""

    BINDINGS = [
        Binding("t", "toggle_entry", "Toggle", show=True),
        Binding("d", "delete_entry", "Delete", show=True),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("escape", "dismiss", "Close", show=True),
        Binding("q", "dismiss", "Close", show=False),
    ]

    DEFAULT_CSS = """
    StartupScreen {
        background: $background;
    }
    #startup-header {
        padding: 1 2;
        background: $panel;
        border-bottom: solid $primary-darken-2;
    }
    #startup-status {
        padding: 0 2;
        height: 1;
        background: $panel;
    }
    #startup-table {
        height: 1fr;
    }
    """

    def __init__(self):
        super().__init__()
        self._manager = StartupManager()
        self._entries: list[StartupEntry] = []

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(
                "[bold #00d4ff]  Startup Manager[/]  "
                "[dim]│  Programs that launch with Windows  │  "
                "[bold]T[/][dim]=Toggle  [bold]D[/][dim]=Delete  [bold]Esc[/][dim]=Close[/]",
                id="startup-header",
            )
            yield Static("", id="startup-status")
            yield DataTable(id="startup-table", zebra_stripes=True, cursor_type="row")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#startup-table", DataTable)
        table.add_column("Status", key="status", width=11)
        table.add_column("Name",   key="name",   width=30)
        table.add_column("Scope",  key="scope",  width=8)
        table.add_column("Command", key="command", width=72)
        table.focus()
        self._load_entries()

    def _load_entries(self) -> None:
        self._entries = self._manager.get_entries()
        table = self.query_one("#startup-table", DataTable)
        table.clear()

        for entry in self._entries:
            if entry.enabled:
                status = "[bold #00cc66]● Enabled [/]"
            else:
                status = "[bold #ff4466]○ Disabled[/]"

            scope_color = "#00d4ff" if entry.scope == "user" else "#ffaa00"
            scope_label = f"[{scope_color}]{entry.scope.upper()}[/]"

            cmd = entry.command
            if len(cmd) > 72:
                cmd = cmd[:69] + "..."

            table.add_row(status, entry.name, scope_label, cmd)

        total = len(self._entries)
        enabled = sum(1 for e in self._entries if e.enabled)
        disabled = total - enabled

        self.query_one("#startup-status", Static).update(
            f"[dim]  {total} entries  │  "
            f"[bold #00cc66]{enabled}[/dim] enabled  │  "
            f"[bold #ff4466]{disabled}[/dim] disabled[/]"
        )

    def _get_selected(self) -> StartupEntry | None:
        table = self.query_one("#startup-table", DataTable)
        row = table.cursor_row
        if 0 <= row < len(self._entries):
            return self._entries[row]
        return None

    def action_toggle_entry(self) -> None:
        entry = self._get_selected()
        if not entry:
            self.notify("No entry selected", severity="warning")
            return

        new_state, err = self._manager.toggle(entry)
        if err:
            self.notify(f"Failed: {err}", title="Error", severity="error")
        else:
            verb = "enabled" if new_state else "disabled"
            self.notify(
                f"{entry.name} → {verb}",
                title="Startup Entry Updated",
                severity="information",
            )
            self._load_entries()

    def action_delete_entry(self) -> None:
        entry = self._get_selected()
        if not entry:
            self.notify("No entry selected", severity="warning")
            return

        ok, err = self._manager.delete_entry(entry)
        if ok:
            self.notify(
                f"Deleted '{entry.name}' from startup",
                title="Entry Deleted",
                severity="warning",
            )
            self._load_entries()
        else:
            self.notify(f"Failed: {err}", title="Error", severity="error")

    def action_refresh(self) -> None:
        self._load_entries()
        self.notify("Refreshed", severity="information")
