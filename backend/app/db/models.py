"""Database models."""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _new_id() -> str:
    return uuid.uuid4().hex


class JobStatus(enum.StrEnum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    TRANSCRIBING = "transcribing"
    DETECTING = "detecting"
    CLIPPING = "clipping"
    RENDERING = "rendering"
    COMPLETED = "completed"
    FAILED = "failed"


class JobKind(enum.StrEnum):
    AUTO_CLIP = "auto_clip"
    AI_VIDEO = "ai_video"
    DUB = "dub"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_new_id)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    jobs: Mapped[list[Job]] = relationship(back_populates="user")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_new_id)
    user_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("users.id"), nullable=True, index=True
    )
    kind: Mapped[JobKind] = mapped_column(Enum(JobKind), default=JobKind.AUTO_CLIP)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.PENDING)
    progress: Mapped[int] = mapped_column(Integer, default=0)

    # Source
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    source_object_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_thumbnail: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_language: Mapped[str | None] = mapped_column(String(16), nullable=True)

    # Pipeline artifacts
    transcript_object_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    highlights_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ai_video_kind: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ai_video_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    user: Mapped[User | None] = relationship(back_populates="jobs")
    clips: Mapped[list[Clip]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


class Clip(Base):
    __tablename__ = "clips"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_new_id)
    job_id: Mapped[str] = mapped_column(String(64), ForeignKey("jobs.id"), index=True)
    index: Mapped[int] = mapped_column(Integer, default=0)

    title: Mapped[str] = mapped_column(String(512))
    caption: Mapped[str] = mapped_column(Text, default="")
    hashtags_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    reason: Mapped[str] = mapped_column(Text, default="")

    start: Mapped[float] = mapped_column(Float, default=0.0)
    end: Mapped[float] = mapped_column(Float, default=0.0)
    duration: Mapped[float] = mapped_column(Float, default=0.0)

    object_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    thumbnail_object_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    aspect_ratio: Mapped[str] = mapped_column(String(16), default="9:16")
    has_subtitles: Mapped[bool] = mapped_column(default=True)
    has_voice_hook: Mapped[bool] = mapped_column(default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    job: Mapped[Job] = relationship(back_populates="clips")
