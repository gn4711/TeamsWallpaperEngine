"""Tracks recently-used artwork IDs so they aren't repeated within a cooldown window."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path


def load_used_ids(history_path: Path, cooldown_days: int) -> set[str]:
    if not history_path.exists():
        return set()

    try:
        entries = json.loads(history_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return set()

    cutoff = datetime.now() - timedelta(days=cooldown_days)
    used = set()
    for entry in entries:
        try:
            used_at = datetime.fromisoformat(entry["date"])
        except (KeyError, ValueError):
            continue
        if used_at >= cutoff:
            used.add(entry["id"])
    return used


def record_usage(history_path: Path, artwork_id: str, title: str, artist: str) -> None:
    entries = []
    if history_path.exists():
        try:
            entries = json.loads(history_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            entries = []

    entries.append(
        {
            "id": artwork_id,
            "title": title,
            "artist": artist,
            "date": datetime.now().isoformat(timespec="seconds"),
        }
    )

    # keep the file from growing forever: drop entries older than a year
    cutoff = datetime.now() - timedelta(days=365)
    entries = [e for e in entries if _safe_parse(e.get("date")) and _safe_parse(e["date"]) >= cutoff]

    history_path.write_text(json.dumps(entries, indent=2), encoding="utf-8")


def _safe_parse(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
