# Groups notes synced from Liveblocks when a session closes, and ranks
# them by votes. Grouping is currently a naive 1:1 (each note becomes its
# own group) — real clustering (by canvas proximity and/or LLM similarity)
# is a follow-up once real session data exists to tune it against.
from __future__ import annotations

from typing import Any

from ids import new_id


def group_notes(notes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": new_id(),
            "label": note["text"][:60],
            "note_ids": [note["id"]],
            "votes": note.get("votes", 0),
            "author": note["author"],
            "text": note["text"],
            "phase": note.get("phase", "unknown"),
        }
        for note in notes
    ]


def rank_by_votes(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(groups, key=lambda g: g["votes"], reverse=True)
