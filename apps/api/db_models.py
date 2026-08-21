# SQLAlchemy ORM tables — the storage shape. Kept separate from models.py
# (the pydantic request/response schemas, the wire shape); they look
# similar today but are free to diverge as each evolves independently.
#
# notes/groups stay as JSON columns on the session row rather than their
# own tables: they're produced wholesale by agents/consolidator.py on
# close and read back wholesale, not queried piecemeal. action_items get
# a real table because they have their own CRUD + concurrent export.
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base
from ids import new_id
from utils import now


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200))
    integration: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    sessions: Mapped[list["RetroSession"]] = relationship(
        back_populates="team", cascade="all, delete-orphan"
    )


class RetroSession(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id"))
    title: Mapped[str] = mapped_column(String(200))
    join_code: Mapped[str] = mapped_column(String(12), unique=True, index=True)
    phase: Mapped[str] = mapped_column(String(20), default="lobby")
    # Nullable so sessions created before this column existed (or by any
    # client that omits it) keep working — routes/sessions.py only enforces
    # the creator-only check when this is actually set, see _ensure_creator.
    created_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    dynamic: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    notes: Mapped[list] = mapped_column(JSON, default=list)
    groups: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    team: Mapped[Team] = relationship(back_populates="sessions")
    action_items: Mapped[list["ActionItem"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class ActionItem(Base):
    __tablename__ = "action_items"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"))
    group_id: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(String, default="")
    assignee: Mapped[str | None] = mapped_column(String(200), nullable=True)
    exported: Mapped[bool] = mapped_column(default=False)
    external_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)

    session: Mapped[RetroSession] = relationship(back_populates="action_items")
