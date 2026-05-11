"""
Service Intelligence Engine — generates smart recommendations.

Analyzes services based on their category, safety level, description,
and resource usage to provide intelligent, human-readable advice
about what each service does and whether you should close it.
"""

from .scanner import SystemItem, SafetyLevel, ItemType


# ─── Category Explanations ───────────────────────────────────────

CATEGORY_INFO = {
    "system": "Core Windows system component",
    "security": "Security and protection service",
    "networking": "Network connectivity and communication",
    "audio": "Audio playback and recording",
    "display": "Screen rendering and display management",
    "bluetooth": "Bluetooth device connectivity",
    "input": "Keyboard, mouse, and input device support",
    "telemetry": "Data collection sent to Microsoft",
    "enterprise": "Enterprise/corporate management feature",
    "gaming": "Xbox and gaming platform service",
    "printing": "Printer and print queue management",
    "remote": "Remote desktop and remote access",
    "sync": "Data synchronization across devices",
    "legacy": "Outdated technology — rarely needed",
    "location": "GPS and location tracking",
    "maps": "Maps and navigation",
    "search": "File indexing and search",
    "multimedia": "Media playback and streaming",
    "iot": "Internet of Things device support",
    "maintenance": "System maintenance and optimization",
    "telephony": "Phone and telephony features",
    "imaging": "Scanner and camera support",
    "performance": "Performance tuning (can backfire)",
    "bloatware": "Pre-installed junk — typically unnecessary",
    "database": "Database engine — heavy when idle",
    "development": "Software development tools",
    "cloud": "Cloud storage and sync",
    "update": "Software auto-update service",
    "oem": "Manufacturer pre-installed service",
}


# ─── Safety Level Details ─────────────────────────────────────────

SAFETY_INFO = {
    SafetyLevel.ESSENTIAL: {
        "label": "🔒 ESSENTIAL — DO NOT CLOSE",
        "detail": (
            "This service is critical for Windows to function. "
            "Stopping it may cause crashes, freezes, or loss of "
            "core functionality like networking or login."
        ),
        "icon": "🔒",
        "color": "#00cc66",
    },
    SafetyLevel.RECOMMENDED: {
        "label": "🟡 RECOMMENDED — KEEP RUNNING",
        "detail": (
            "Provides important functionality most users need. "
            "Not system-critical, but disabling may break features "
            "like Windows Update, VPN, or app installations."
        ),
        "icon": "🟡",
        "color": "#ffaa00",
    },
    SafetyLevel.TRIMMABLE: {
        "label": "✅ SAFE TO CLOSE",
        "detail": (
            "You can safely stop this service without affecting "
            "core system stability. It provides optional functionality "
            "or uses resources you don't need."
        ),
        "icon": "✅",
        "color": "#ff4466",
    },
    SafetyLevel.APP: {
        "label": "📦 USER APPLICATION",
        "detail": (
            "This is a user-installed application, not a Windows "
            "service. Close it if you're not actively using it."
        ),
        "icon": "📦",
        "color": "#cc66ff",
    },
    SafetyLevel.UNKNOWN: {
        "label": "❓ UNKNOWN — NEEDS REVIEW",
        "detail": (
            "This service is not in our database. Exercise caution — "
            "research it before stopping."
        ),
        "icon": "❓",
        "color": "#555555",
    },
}


# ─── Public API ───────────────────────────────────────────────────

def get_intelligence(item: SystemItem) -> dict:
    """
    Generate comprehensive intelligence about a service/process.

    Returns a dict with keys:
        description, reason, recommendation, safety_label, safety_detail,
        safety_icon, safety_color, category_info, is_bloatware, impact
    """
    si = SAFETY_INFO.get(item.safety, SAFETY_INFO[SafetyLevel.UNKNOWN])
    cat_info = CATEGORY_INFO.get(item.category, "Uncategorized service")

    return {
        "description": item.description or "No description available.",
        "reason": _why_running(item),
        "recommendation": _should_close(item),
        "safety_label": si["label"],
        "safety_detail": si["detail"],
        "safety_icon": si["icon"],
        "safety_color": si["color"],
        "category_info": cat_info,
        "is_bloatware": getattr(item, "bloatware", False),
        "impact": _resource_impact(item),
    }


# ─── Reason Generator ────────────────────────────────────────────

def _why_running(item: SystemItem) -> str:
    """Generate a human-readable explanation of why this service exists."""
    templates = {
        "system": "Windows system service that starts automatically at boot.",
        "security": "Security service that runs to protect your system.",
        "networking": "Manages network connectivity — runs to keep you online.",
        "audio": "Handles audio — runs so speakers and mics work.",
        "display": "Manages your displays — runs to render your screen.",
        "bluetooth": "Manages Bluetooth — runs to support wireless devices.",
        "telemetry": (
            "Collects usage data and sends it to Microsoft. Runs silently "
            "in the background consuming resources for analytics."
        ),
        "enterprise": (
            "Enterprise management feature for corporate environments. "
            "Unnecessary on personal computers."
        ),
        "gaming": (
            "Xbox/gaming integration. Runs for Xbox features "
            "even if you don't use Xbox services."
        ),
        "printing": "Manages printers — runs to handle print jobs.",
        "remote": (
            "Enables remote access to your PC. Runs to allow "
            "Remote Desktop connections."
        ),
        "sync": "Synchronizes data across devices in the background.",
        "legacy": "Legacy/outdated service for backward compatibility.",
        "location": "Tracks your device location for apps that request it.",
        "search": (
            "Indexes files for Windows Search. Continuously scans "
            "your drives, which can impact disk and CPU performance."
        ),
        "bloatware": (
            "Pre-installed software that came with Windows or your "
            "manufacturer. Not something you chose to install."
        ),
        "database": (
            "Database engine that reserves significant memory and CPU "
            "even when no applications are actively querying it."
        ),
        "cloud": "Cloud sync service — continuously syncs files.",
        "update": "Auto-update service — periodically checks for updates.",
        "oem": (
            "Installed by your device manufacturer. Often provides "
            "little value while consuming resources."
        ),
        "maps": "Maps service — downloads and manages map data.",
        "multimedia": "Media streaming/playback support service.",
        "iot": "IoT device communication service.",
        "maintenance": "System maintenance — can run manually instead.",
        "telephony": "Phone/telephony features — rarely used on desktops.",
        "imaging": "Scanner/camera acquisition — only needed with hardware.",
        "performance": (
            "Performance tuning service. Ironically, can cause "
            "high disk usage on modern SSDs."
        ),
    }

    reason = templates.get(item.category, "Running on your system — purpose not fully categorized.")

    if item.description:
        reason = f"{item.description} {reason}"

    return reason


# ─── Recommendation Generator ────────────────────────────────────

def _should_close(item: SystemItem) -> str:
    """Generate a clear recommendation about whether to close the service."""
    if item.safety == SafetyLevel.ESSENTIAL:
        return (
            "🔒 DO NOT CLOSE — This is critical for Windows. "
            "Stopping it may crash your system."
        )

    if item.safety == SafetyLevel.RECOMMENDED:
        return (
            "🟡 KEEP RUNNING unless you know you don't need it. "
            "Provides useful functionality most users rely on."
        )

    if item.safety == SafetyLevel.TRIMMABLE:
        cat_recs = {
            "telemetry": (
                "✅ CLOSE IT — This is telemetry. It sends your data "
                "to Microsoft and wastes resources. Better for privacy."
            ),
            "gaming": (
                "✅ CLOSE IT if you don't use Xbox. These services "
                "waste RAM and CPU for Xbox integration."
            ),
            "enterprise": (
                "✅ CLOSE IT — Enterprise feature not needed on "
                "personal computers."
            ),
            "legacy": (
                "✅ CLOSE IT — Outdated technology. Nobody uses fax "
                "machines or dial-up connections anymore."
            ),
            "remote": (
                "✅ CLOSE IT if you don't use Remote Desktop. "
                "Also a potential security risk if left running."
            ),
            "printing": (
                "✅ CLOSE IT if you don't have a printer connected."
            ),
            "bluetooth": (
                "✅ CLOSE IT if you don't use Bluetooth devices."
            ),
            "location": (
                "✅ CLOSE IT — Improves privacy. Location tracking "
                "is rarely needed on desktops."
            ),
            "search": (
                "✅ CLOSE IT if you don't use Windows Search heavily. "
                "It hogs disk I/O and CPU for indexing."
            ),
            "database": (
                "✅ CLOSE IT if you're not actively using databases. "
                "DB engines are major resource hogs when idle."
            ),
            "bloatware": (
                "✅ CLOSE IT — This is bloatware. Wastes resources "
                "with zero benefit to you."
            ),
            "oem": (
                "✅ CLOSE IT — Manufacturer junk. Provides little "
                "value while consuming your resources."
            ),
            "performance": (
                "✅ CLOSE IT — Ironically harms performance on SSDs. "
                "Modern drives don't need this."
            ),
        }
        return cat_recs.get(
            item.category,
            "✅ SAFE TO CLOSE — Not essential. Stopping it frees resources."
        )

    if item.safety == SafetyLevel.APP:
        return (
            "📦 YOUR CHOICE — This is an app you installed. "
            "Close it if you're not using it right now."
        )

    return (
        "❓ UNKNOWN — Research this service before stopping it. "
        "Check online what it does."
    )


# ─── Resource Impact Assessment ──────────────────────────────────

def _resource_impact(item: SystemItem) -> str:
    """Assess the resource impact of this service."""
    parts = []

    if item.ram_mb >= 200:
        parts.append(f"🔴 HIGH RAM ({item.ram_mb:.0f} MB)")
    elif item.ram_mb >= 50:
        parts.append(f"🟡 MED RAM ({item.ram_mb:.0f} MB)")
    elif item.ram_mb >= 5:
        parts.append(f"🟢 LOW RAM ({item.ram_mb:.1f} MB)")
    else:
        parts.append(f"⚪ MINIMAL RAM")

    if item.cpu_percent >= 10:
        parts.append(f"🔴 HIGH CPU ({item.cpu_percent:.1f}%)")
    elif item.cpu_percent >= 2:
        parts.append(f"🟡 MED CPU ({item.cpu_percent:.1f}%)")
    elif item.cpu_percent >= 0.1:
        parts.append(f"🟢 LOW CPU ({item.cpu_percent:.1f}%)")
    else:
        parts.append(f"⚪ IDLE CPU")

    return " │ ".join(parts)
