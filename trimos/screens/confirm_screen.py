"""
Confirmation modal screen for bulk operations.

Shows a list of services that will be affected and asks
the user to confirm before proceeding.
"""

from textual.screen import ModalScreen
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal, VerticalScroll
from textual.widgets import Static, Button
from textual.binding import Binding
from rich.text import Text

from ..core.scanner import SystemItem, SafetyLevel


class ConfirmBulkClose(ModalScreen[bool]):
    """Modal dialog confirming bulk service closure."""

    BINDINGS = [
        Binding("y", "confirm", "Yes, close all", show=True),
        Binding("n", "cancel", "No, cancel", show=True),
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    CSS = """
    ConfirmBulkClose {
        align: center middle;
    }

    #confirm-dialog {
        width: 72;
        height: auto;
        max-height: 80%;
        background: #1a1a2e;
        border: thick #ff4466;
        border-title-color: #ff4466;
        padding: 1 2;
    }

    #confirm-title {
        text-align: center;
        text-style: bold;
        color: #ff4466;
        width: 100%;
        margin-bottom: 1;
    }

    #confirm-summary {
        color: #d4d4d4;
        width: 100%;
        margin-bottom: 1;
    }

    #confirm-list {
        height: auto;
        max-height: 18;
        background: #111118;
        border: round #2a2a3a;
        padding: 0 1;
        margin-bottom: 1;
    }

    .confirm-item {
        height: 1;
        color: #ff8888;
    }

    #confirm-warning {
        color: #ffaa00;
        text-style: italic;
        width: 100%;
        margin-bottom: 1;
    }

    #confirm-buttons {
        height: 3;
        align: center middle;
        width: 100%;
    }

    #confirm-buttons Button {
        margin: 0 2;
        min-width: 20;
    }

    #btn-yes {
        background: #ff4466;
        color: #ffffff;
        text-style: bold;
    }

    #btn-yes:hover {
        background: #ff6688;
    }

    #btn-no {
        background: #2a2a3a;
        color: #d4d4d4;
    }

    #btn-no:hover {
        background: #3a3a4a;
    }
    """

    def __init__(
        self,
        items: list[SystemItem],
        mode: str = "default",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._items = items
        self._mode = mode

    def compose(self) -> ComposeResult:
        total_ram = sum(i.ram_mb for i in self._items)
        count = len(self._items)

        with Vertical(id="confirm-dialog"):
            yield Static(
                "⚠️  BULK CLOSE CONFIRMATION  ⚠️",
                id="confirm-title",
            )

            mode_labels = {
                "default": "Default Optimization",
                "gaming": "Gaming Mode",
                "work": "Work Mode",
                "bloatware": "Bloatware Cleanup",
            }
            mode_label = mode_labels.get(self._mode, self._mode.title())

            yield Static(
                f"[bold]Mode:[/] [#00d4ff]{mode_label}[/]  │  "
                f"[bold]Services:[/] [#ff4466]{count}[/]  │  "
                f"[bold]RAM to free:[/] [#00cc66]~{total_ram:.0f} MB[/]",
                id="confirm-summary",
            )

            with VerticalScroll(id="confirm-list"):
                for item in self._items:
                    cat = f" [{item.category}]" if item.category else ""
                    ram = f"{item.ram_mb:.1f} MB"
                    yield Static(
                        f"  [#ff8888]✕[/] {item.display_name[:40]:<40} "
                        f"[dim]{ram:>8}[/] [dim]{cat}[/]",
                        classes="confirm-item",
                    )

            yield Static(
                "⚡ A snapshot will be saved before changes. "
                "You can restore with [bold]R[/].",
                id="confirm-warning",
            )

            with Horizontal(id="confirm-buttons"):
                yield Button(
                    "✕  Close All  (Y)", id="btn-yes", variant="error"
                )
                yield Button(
                    "Cancel  (N)", id="btn-no", variant="default"
                )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-yes":
            self.dismiss(True)
        else:
            self.dismiss(False)

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)
