"""Persist runs to ~/.gerber2gcode_history.json."""

import json
from pathlib import Path

_HISTORY_FILE = Path.home() / '.gerber2gcode_history.json'
_MAX_ENTRIES = 50


def load_all() -> list:
    """Load all history entries from disk."""
    if not _HISTORY_FILE.exists():
        return []
    try:
        with open(_HISTORY_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


def add(entry: dict):
    """Prepend entry and save (max 50 entries)."""
    entries = load_all()
    entries.insert(0, entry)
    entries = entries[:_MAX_ENTRIES]
    try:
        with open(_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(entries, f, indent=2, default=str)
    except Exception as e:
        print(f"[history] Could not save history: {e}")
