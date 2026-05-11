# TrimOS 🔧

> A lightweight, terminal-based Windows optimizer with real-time performance graphs, intelligent service management, and a cute animated mascot.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run TrimOS (requires admin for service control)
python main.py
```

## Keyboard Controls

| Key | Action |
|-----|--------|
| `O` | **Optimize** — Stop all trimmable services |
| `G` | **Gaming Mode** — Aggressive optimization |
| `W` | **Work Mode** — Keep productivity apps |
| `R` | **Restore** — Rollback to previous state |
| `S` | **Rescan** — Refresh service list |
| `F` | **Filter** — Cycle through filters |
| `/` | **Search** — Find services/processes |
| `Q` | **Quit** |

## Features

- 📊 **Live performance graphs** — CPU, RAM, Disk, Network sparklines
- 🔍 **Smart scanner** — Detects and classifies 120+ Windows services
- ⚡ **One-key optimization** — Batch stop non-essential services
- 🎮 **Gaming/Work modes** — Profile-based optimization
- 📸 **Snapshots** — Auto-save state before changes, one-click restore
- 🐾 **Trimmy** — Cute animated mascot that reacts to system health

## Tech Stack

- **Python 3.10+**
- **Textual** — Terminal UI framework
- **psutil** — System monitoring
- **Rich** — Terminal formatting
