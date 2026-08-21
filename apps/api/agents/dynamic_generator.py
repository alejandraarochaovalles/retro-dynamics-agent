# Proposes 1-3 unusual retro dynamics based on sprint context.
# Falls back to a canned set when GROQ_API_KEY isn't configured, so the
# /dynamics/generate route always returns something usable in dev.
from __future__ import annotations

import logging

from config import settings
from models import DynamicProposal

FALLBACK_PROPOSALS: list[DynamicProposal] = [
    DynamicProposal(
        name="Sailboat",
        description=(
            "The team is a sailboat: anchors (what holds us back), wind "
            "(what pushes us forward), rocks (risks ahead), island (the goal)."
        ),
        phases=["anchors", "wind", "rocks", "island", "vote", "actions"],
        icon="⛵",
        phase_descriptions={
            "anchors": "As a team, write what held you back this sprint — one anchor per note.",
            "wind": "As a team, write what pushed you forward — the things that helped the team move.",
            "rocks": "As a team, write the risks you see ahead, before they turn into incidents.",
            "island": "As a team, write what the destination looks like — the goal you're sailing toward together.",
            "vote": "As a team, vote for the notes that matter most — everyone gets to pick their top ones.",
            "actions": "As a team, turn the most-voted notes into concrete action items before closing.",
        },
    ),
    DynamicProposal(
        name="4Ls",
        description="Liked, Learned, Lacked, Longed for — good after a sprint with mixed results.",
        phases=["liked", "learned", "lacked", "longed_for", "vote", "actions"],
        icon="🔤",
        phase_descriptions={
            "liked": "As a team, write what you liked about this sprint.",
            "learned": "As a team, write something you learned together, big or small.",
            "lacked": "As a team, write what was missing that would have helped.",
            "longed_for": "As a team, write what you wished you'd had.",
            "vote": "As a team, vote for the notes that matter most — everyone gets to pick their top ones.",
            "actions": "As a team, turn the most-voted notes into concrete action items before closing.",
        },
    ),
    DynamicProposal(
        name="Mad Sad Glad",
        description="Emotion-first retro, useful after an incident-heavy sprint.",
        phases=["mad", "sad", "glad", "vote", "actions"],
        icon="🎭",
        phase_descriptions={
            "mad": "As a team, write what frustrated or angered you this sprint.",
            "sad": "As a team, write what disappointed you or let the team down.",
            "glad": "As a team, write what made you happy or proud.",
            "vote": "As a team, vote for the notes that matter most — everyone gets to pick their top ones.",
            "actions": "As a team, turn the most-voted notes into concrete action items before closing.",
        },
    ),
]


def _build_prompt(context: str, count: int) -> str:
    return (
        "You are a facilitator proposing retrospective dynamics for a "
        "software team. Given the sprint context below, propose "
        f"{count} unusual (not Start/Stop/Continue) dynamics.\n\n"
        f"Context: {context}\n\n"
        'Respond as JSON: an object {"proposals": [...]} where each item '
        "has keys 'name', 'description', 'phases' (list of short phase ids), "
        "'icon' — a single emoji that visually represents that specific "
        "dynamic's theme (e.g. ⛵ for a sailboat metaphor, 🌩️ for a storm "
        "metaphor) — pick one per proposal, not the same emoji for all — "
        "and 'phase_descriptions' — an object mapping every id in 'phases' "
        "to one short sentence telling participants what to do during that "
        "phase, phrased as an instruction to the whole team rather than one "
        "person — start it with \"As a team,\" or \"Together,\" (e.g. "
        "\"anchors\": \"As a team, write what held you back this sprint.\"). "
        "Every phase in 'phases' must have an entry."
    )


def generate(context: str, count: int = 3) -> tuple[list[DynamicProposal], str]:
    """Returns (proposals, source) where source is 'groq' or 'fallback'."""
    if not settings.groq_api_key:
        return FALLBACK_PROPOSALS[:count], "fallback"

    try:
        from groq import Groq

        client = Groq(api_key=settings.groq_api_key)
        # llama-3.3-70b-versatile was retired from Groq's catalog (404s on
        # every call) — verified against this key's actual model list
        # (client.models.list()); gpt-oss-120b is the closest replacement
        # for JSON-structured, instruction-following output.
        completion = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[{"role": "user", "content": _build_prompt(context, count)}],
            response_format={"type": "json_object"},
        )
        import json

        raw = completion.choices[0].message.content or "{}"
        parsed = json.loads(raw)
        items = parsed if isinstance(parsed, list) else parsed.get("proposals", [])
        proposals = [DynamicProposal(**item) for item in items[:count]]
        if not proposals:
            return FALLBACK_PROPOSALS[:count], "fallback"
        return proposals, "groq"
    except Exception:
        # Any failure (network, bad JSON, missing package) degrades to the
        # fallback rather than breaking the session-creation flow.
        logging.exception("dynamic_generator: Groq call failed, using fallback proposals")
        return FALLBACK_PROPOSALS[:count], "fallback"
