"""Host usage history — tracks recently used hosts for quick access.

Stores a simple JSON file at ~/.config/ops-launcher/history.json with
the last N host references used, ordered by most recent first.
"""

from __future__ import annotations

import json

from ops_launcher.config import DEFAULT_CONFIG_DIR

HISTORY_FILE = DEFAULT_CONFIG_DIR / "history.json"
MAX_RECENT = 5


def load_recent_hosts() -> list[str]:
    """Load the list of recently used host display names (client:host)."""
    if not HISTORY_FILE.exists():
        return []
    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [str(h) for h in data[:MAX_RECENT]]
    except (json.JSONDecodeError, OSError):
        pass
    return []


def record_host_usage(host_display: str) -> None:
    """Record a host as recently used, pushing it to the top of the list."""
    recent = load_recent_hosts()

    # Remove if already present, then prepend
    recent = [h for h in recent if h != host_display]
    recent.insert(0, host_display)
    recent = recent[:MAX_RECENT]

    try:
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        HISTORY_FILE.write_text(json.dumps(recent), encoding="utf-8")
    except OSError:
        pass  # non-critical, silently ignore
