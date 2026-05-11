"""
Detail panel widget — shows rich intelligence about the selected service.

Displays what a service does, why it's running, whether you should
close it, its resource impact, and its protection status.
"""

from textual.widget import Widget
from textual.reactive import reactive
from rich.text import Text

from ..core.scanner import SystemItem, SafetyLevel
from ..core.intelligence import get_intelligence


class DetailPanel(Widget):
    """
    Expandable panel showing detailed service intelligence.
    Updates when the user selects a different service in the table.
    """

    DEFAULT_CSS = """
    DetailPanel {
        height: auto;
        min-height: 6;
        max-height: 10;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._item: SystemItem | None = None
        self._is_protected: bool = False

    def set_item(self, item: SystemItem | None, is_protected: bool = False) -> None:
        """Update the displayed service item."""
        self._item = item
        self._is_protected = is_protected
        self.refresh()

    def render(self) -> Text:
        """Render the detail panel content."""
        text = Text()

        if self._item is None:
            text.append("  ↑ ", style="dim")
            text.append("Select a service above to see details", style="dim italic")
            return text

        item = self._item
        info = get_intelligence(item)

        # ── Line 1: Name and badges ──
        text.append(" 📋 ", style="bold")
        text.append(item.display_name, style="bold #00d4ff")
        text.append(f"  ({item.name})", style="dim")

        if self._is_protected:
            text.append("  🛡️ PROTECTED", style="bold #ffaa00")

        if info["is_bloatware"]:
            text.append("  🗑️ BLOATWARE", style="bold #ff4466")

        text.append("\n")

        # ── Line 2: Status, Type, Category ──
        status_color = "#00cc66" if item.status == "running" else "#555555"
        status_icon = "●" if item.status == "running" else "○"
        text.append(f" {status_icon} ", style=f"bold {status_color}")
        text.append(item.status.upper(), style=f"bold {status_color}")
        text.append("  │  ", style="dim")
        type_str = "SERVICE" if item.item_type.value == "service" else "PROCESS"
        text.append(type_str, style="bold #00d4ff")
        text.append("  │  ", style="dim")
        text.append(info["category_info"], style="#888888")
        text.append("  │  ", style="dim")
        text.append(info["impact"], style="#d4d4d4")
        text.append("\n")

        # ── Line 3: What it does ──
        text.append(" 📝 What: ", style="bold #888888")
        desc = info["description"]
        # Truncate if too long for single line
        max_desc = max(self.size.width - 14, 40)
        if len(desc) > max_desc:
            desc = desc[:max_desc - 3] + "..."
        text.append(desc, style="#d4d4d4")
        text.append("\n")

        # ── Line 4: Why it's running ──
        text.append(" 💡 Why:  ", style="bold #888888")
        reason = info["reason"]
        # Show first part of reason
        max_reason = max(self.size.width - 14, 40)
        if len(reason) > max_reason:
            reason = reason[:max_reason - 3] + "..."
        text.append(reason, style="#aaaaaa italic")
        text.append("\n")

        # ── Line 5: Recommendation ──
        rec = info["recommendation"]
        text.append(" ", style="")
        text.append(rec, style="bold")

        return text
