# Request/response schemas for packages/contracts/openapi.yaml.
# Provisional: the contract itself doesn't formalize components.schemas yet
# (see the note at the bottom of openapi.yaml), so these are derived from
# the operationIds and should be ported back into the contract as they
# stabilize.
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Phase = Literal["lobby", "active", "consolidation", "closed"]


# ── Teams ────────────────────────────────────────────────────────────
class TeamCreate(BaseModel):
    name: str


class Team(BaseModel):
    id: str
    name: str
    integration: dict[str, Any] | None = None
    created_at: str


class IntegrationConnect(BaseModel):
    provider: Literal["jira", "azure_devops"]
    config: dict[str, Any] = Field(default_factory=dict)
    # Optional facilitator check, same backward-compat story as
    # SessionCreate.created_by: only enforced (see routes/teams.py) when
    # session_id resolves to a session that actually has a created_by set.
    session_id: str | None = None
    participant_name: str | None = None


# ── Dynamics ─────────────────────────────────────────────────────────
class DynamicsGenerateRequest(BaseModel):
    context: str  # free-text: "incident-heavy sprint", "new team", etc.
    team_id: str | None = None
    count: int = Field(default=3, ge=1, le=5)


class DynamicProposal(BaseModel):
    name: str
    description: str
    phases: list[str]
    # Single emoji chosen by the generator (or fallback list) to represent
    # the dynamic's theme at a glance — e.g. ⛵ for "Sailboat". Defaults to
    # a neutral icon so old sessions/rows created before this field existed
    # (dynamic is stored as a JSON blob, see db_models.py) still validate.
    icon: str = "🧭"
    # One sentence per phase id (from `phases` above) telling participants
    # what to actually do during that phase — shown live on the board's
    # phase bar. Keyed by phase id rather than positional so it survives
    # phases being read out of order; defaults to {} so old sessions/rows
    # created before this field existed still validate (the board falls
    # back to a generic explanation when a phase's key is missing).
    phase_descriptions: dict[str, str] = Field(default_factory=dict)


class DynamicsGenerateResponse(BaseModel):
    proposals: list[DynamicProposal]
    source: Literal["groq", "fallback"]


# ── Sessions ─────────────────────────────────────────────────────────
class SessionCreate(BaseModel):
    team_id: str
    title: str
    dynamic: dict[str, Any] | None = None
    # Optional (not every caller — old clients, tests — sends it) so this
    # stays backward compatible; routes/sessions.py only enforces the
    # creator-only check on start/close when a session actually has one.
    created_by: str | None = None


class SessionOut(BaseModel):
    id: str
    team_id: str
    title: str
    join_code: str
    phase: Phase
    dynamic: dict[str, Any] | None
    created_at: str
    closed_at: str | None
    created_by: str | None = None


class SessionStart(BaseModel):
    participant_name: str | None = None


class SessionListItem(BaseModel):
    id: str
    title: str
    phase: Phase
    created_at: str


class SessionJoin(BaseModel):
    join_code: str
    participant_name: str


class PhaseAdvance(BaseModel):
    phase: Phase


class Note(BaseModel):
    id: str | None = None
    author: str
    text: str
    x: float = 0
    y: float = 0
    votes: int = 0
    # Which phase (a `DynamicProposal.phases` id) the note was written
    # during — stamped client-side at creation (see Canvas.tsx). Defaulted
    # so notes written before this field existed still validate.
    phase: str = "unknown"


class SessionClose(BaseModel):
    notes: list[Note] = Field(default_factory=list)
    # Same backward-compat story as SessionStart.participant_name above.
    participant_name: str | None = None


# ── Consolidation ────────────────────────────────────────────────────
class Group(BaseModel):
    id: str
    label: str
    note_ids: list[str]
    votes: int
    # Defaulted (rather than required) so groups written before these
    # fields existed (stored as a JSON blob on the session row, see
    # db_models.py) still validate — only newly-closed sessions populate
    # them for real, via agents/consolidator.py.
    author: str = "someone"
    text: str = ""
    phase: str = "unknown"


class GroupUpdate(BaseModel):
    label: str | None = None
    note_ids: list[str] | None = None


class VotesSummaryEntry(BaseModel):
    id: str
    label: str
    votes: int


# ── Action items ─────────────────────────────────────────────────────
class ActionItemCreate(BaseModel):
    group_id: str
    title: str
    description: str = ""
    assignee: str | None = None


class ActionItemUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    assignee: str | None = None


class ActionItem(BaseModel):
    id: str
    group_id: str
    title: str
    description: str
    assignee: str | None
    exported: bool = False
    external_ref: str | None = None


class DeleteResponse(BaseModel):
    deleted: str


# ── Export ───────────────────────────────────────────────────────────
class ExportRequest(BaseModel):
    action_item_ids: list[str] = Field(default_factory=list)  # empty = export all pending
    # Same backward-compat story as SessionStart.participant_name: only
    # enforced when the session actually recorded a creator.
    participant_name: str | None = None


class ExportResult(BaseModel):
    action_item_id: str
    status: Literal["created", "skipped", "failed"]
    external_ref: str | None = None
    detail: str | None = None


class ExportResponse(BaseModel):
    results: list[ExportResult]


# ── Liveblocks ───────────────────────────────────────────────────────
class LiveblocksAuthRequest(BaseModel):
    room: str
    participant_name: str


class LiveblocksAuthResponse(BaseModel):
    token: str
    configured: bool


# ── Summary ──────────────────────────────────────────────────────────
class SessionSummary(BaseModel):
    session_id: str
    title: str
    phase: Phase
    groups: list[Group]
    action_items: list[ActionItem]
