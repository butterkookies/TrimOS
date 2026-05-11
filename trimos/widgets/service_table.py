"""
Service/process table widget — color-coded, sortable, filterable.

Displays all scanned services and processes in a DataTable
with safety-level color coding and resource usage highlighting.
Supports protection indicators and bloatware identification.
"""

from textual.widgets import DataTable
from textual.messages import Message
from rich.text import Text

from ..core.scanner import SystemItem, SafetyLevel, SAFETY_DISPLAY, ItemType


# Safety level sort priority (trimmable first — things you can act on)
SAFETY_ORDER = {
    SafetyLevel.TRIMMABLE: 0,
    SafetyLevel.UNKNOWN: 1,
    SafetyLevel.APP: 2,
    SafetyLevel.RECOMMENDED: 3,
    SafetyLevel.ESSENTIAL: 4,
}


class ServiceTable(DataTable):
    """
    Interactive service/process table with color-coded safety ratings.
    Shows protection status, bloatware badges, and descriptions.
    """

    class RowHighlighted(Message):
        """Emitted when the cursor moves to a new row."""
        def __init__(self, item: SystemItem | None):
            super().__init__()
            self.item = item

    DEFAULT_CSS = """
    ServiceTable {
        height: 1fr;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._items: list[SystemItem] = []
        self._item_index: dict[str, SystemItem] = {}
        self._filter: str = "all"
        self._sort_key: str = "ram"
        self.cursor_type = "row"
        self.zebra_stripes = True
        self._protected_names: set[str] = set()

    def on_mount(self) -> None:
        """Set up the table columns."""
        self.add_column("", key="status", width=2)
        self.add_column("Name", key="name", width=26)
        self.add_column("Type", key="type", width=5)
        self.add_column("RAM", key="ram", width=10)
        self.add_column("CPU", key="cpu", width=7)
        self.add_column("Safety", key="safety", width=12)
        self.add_column("Info", key="info", width=18)

    def load_items(
        self,
        items: list[SystemItem],
        protected_names: set[str] | None = None,
    ) -> None:
        """Load and display system items in the table."""
        self._items = items
        self._item_index = {item.name: item for item in items}
        if protected_names is not None:
            self._protected_names = protected_names
        self._render_rows()

    def update_protection(self, protected_names: set[str]) -> None:
        """Update protection status and re-render."""
        self._protected_names = protected_names
        self._render_rows()

    def _get_filtered_items(self) -> list[SystemItem]:
        """Filter and sort items."""
        filtered = self._items

        if self._filter == "trimmable":
            filtered = [i for i in filtered if i.safety == SafetyLevel.TRIMMABLE]
        elif self._filter == "running":
            filtered = [i for i in filtered if i.status == "running"]
        elif self._filter == "services":
            filtered = [i for i in filtered if i.item_type == ItemType.SERVICE]
        elif self._filter == "processes":
            filtered = [i for i in filtered if i.item_type == ItemType.PROCESS]
        elif self._filter == "bloatware":
            filtered = [i for i in filtered if i.bloatware]
        elif self._filter == "protected":
            filtered = [
                i for i in filtered
                if i.name.lower() in self._protected_names
            ]

        if self._sort_key == "ram":
            filtered.sort(key=lambda x: x.ram_mb, reverse=True)
        elif self._sort_key == "cpu":
            filtered.sort(key=lambda x: x.cpu_percent, reverse=True)
        elif self._sort_key == "name":
            filtered.sort(key=lambda x: x.display_name.lower())
        elif self._sort_key == "safety":
            filtered.sort(key=lambda x: SAFETY_ORDER.get(x.safety, 5))

        return filtered

    def _render_rows(self) -> None:
        """Re-render all rows based on current filter and sort."""
        self.clear()

        for item in self._get_filtered_items():
            is_protected = item.name.lower() in self._protected_names

            # Status dot
            if item.status == "running":
                status = Text("●", style="bold #00cc66")
            else:
                status = Text("○", style="#555555")

            # Name (truncate long names) with protection indicator.
            # Emoji prefix is 2 terminal cols wide, so cap name at 21 chars
            # to stay within the 26-col Name column (2 + 21 + col padding).
            prefix = ""
            if is_protected:
                prefix = "🛡"
            elif item.bloatware:
                prefix = "🗑"

            if prefix:
                name_str = f"{prefix}{item.display_name[:21]}"
            else:
                name_str = item.display_name[:24]

            if item.safety == SafetyLevel.TRIMMABLE:
                name = Text(name_str, style="bold #ff8888")
            elif item.safety == SafetyLevel.ESSENTIAL:
                name = Text(name_str, style="#888888")
            elif is_protected:
                name = Text(name_str, style="bold #ffaa00")
            else:
                name = Text(name_str, style="#d4d4d4")

            # Type badge
            if item.item_type == ItemType.SERVICE:
                type_text = Text("SVC", style="bold #00d4ff")
            else:
                type_text = Text("APP", style="bold #cc66ff")

            # RAM with color based on usage
            if item.ram_mb >= 200:
                ram_style = "bold #ff4466"
            elif item.ram_mb >= 50:
                ram_style = "bold #ffaa00"
            elif item.ram_mb >= 1:
                ram_style = "#d4d4d4"
            else:
                ram_style = "#555555"
            ram = Text(f"{item.ram_mb:>6.0f} MB", style=ram_style)

            # CPU with color
            if item.cpu_percent >= 10:
                cpu_style = "bold #ff4466"
            elif item.cpu_percent >= 2:
                cpu_style = "bold #ffaa00"
            elif item.cpu_percent >= 0.1:
                cpu_style = "#d4d4d4"
            else:
                cpu_style = "#555555"
            cpu = Text(f"{item.cpu_percent:>4.1f}%", style=cpu_style)

            # Safety label with better naming
            if is_protected:
                safety = Text("[GUARD]", style="bold #ffaa00")
            else:
                safety_labels = {
                    SafetyLevel.ESSENTIAL:   ("SAFE",  "#00cc66"),
                    SafetyLevel.RECOMMENDED: ("KEEP",  "#ffaa00"),
                    SafetyLevel.TRIMMABLE:   ("TRIM",  "#ff4466"),
                    SafetyLevel.APP:         ("APP",   "#cc66ff"),
                    SafetyLevel.UNKNOWN:     ("???",   "#555555"),
                }
                label, color = safety_labels.get(item.safety, ("???", "#555555"))
                if item.bloatware:
                    safety = Text("[BLOAT]", style="bold #ff4466")
                else:
                    safety = Text(f"[{label}]", style=f"bold {color}")

            # Info column — short category + description snippet
            info_parts = []
            if item.category:
                info_parts.append(item.category)
            if item.bloatware and not is_protected:
                info_parts.append("bloatware")
            info_str = " · ".join(info_parts)[:18]
            info = Text(info_str, style="dim")

            self.add_row(
                status, name, type_text, ram, cpu, safety, info,
                key=item.name,
            )

    def set_filter(self, filter_name: str) -> None:
        """Change the active filter and re-render."""
        self._filter = filter_name
        self._render_rows()

    def set_sort(self, sort_key: str) -> None:
        """Change the sort key and re-render."""
        self._sort_key = sort_key
        self._render_rows()

    def get_selected_item(self) -> SystemItem | None:
        """Get the SystemItem for the currently highlighted row."""
        if self.cursor_row is not None:
            try:
                row_key = self.ordered_rows[self.cursor_row].key
                name = str(row_key.value)
                return self._item_index.get(name)
            except (IndexError, AttributeError):
                pass
        return None

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Forward row highlight events with the full SystemItem."""
        item = self.get_selected_item()
        self.post_message(self.RowHighlighted(item))

    def get_bloatware_count(self) -> tuple[int, float]:
        """Get count and total RAM of running bloatware services."""
        bloat = [
            i for i in self._items
            if i.bloatware and i.status == "running"
        ]
        return len(bloat), sum(i.ram_mb for i in bloat)
