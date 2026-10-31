"""Current-state synthetic domain schema; no live-data adapter in Phase 3A."""

from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from youtube_insight.data.database import Base


class UTCDateTime(TypeDecorator):
    """SQLite stores UTC wall time; Python always receives aware UTC values."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, _dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("A timezone-aware datetime is required")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value, _dialect):
        return value.replace(tzinfo=UTC) if value is not None else None


class Channel(Base):
    __tablename__ = "channels"
    __table_args__ = (
        CheckConstraint("source = 'synthetic'"),
        CheckConstraint("view_count IS NULL OR view_count >= 0"),
        CheckConstraint("subscriber_count IS NULL OR subscriber_count >= 0"),
        CheckConstraint("expires_at > fetched_at"),
    )

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(16))
    view_count: Mapped[int | None] = mapped_column(Integer)
    subscriber_count: Mapped[int | None] = mapped_column(Integer)
    published_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)


class Video(Base):
    __tablename__ = "videos"
    __table_args__ = (
        CheckConstraint("source = 'synthetic'"),
        CheckConstraint("view_count IS NULL OR view_count >= 0"),
        CheckConstraint("like_count IS NULL OR like_count >= 0"),
        CheckConstraint("comment_count IS NULL OR comment_count >= 0"),
        CheckConstraint("expires_at > fetched_at"),
    )

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    channel_id: Mapped[str] = mapped_column(
        ForeignKey("channels.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(16))
    view_count: Mapped[int | None] = mapped_column(Integer)
    like_count: Mapped[int | None] = mapped_column(Integer)
    comment_count: Mapped[int | None] = mapped_column(Integer)
    published_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"
    __table_args__ = (
        CheckConstraint("source = 'synthetic'"),
        CheckConstraint("status IN ('running', 'succeeded', 'failed')"),
        CheckConstraint(
            "input_rows >= 0 AND output_rows >= 0 AND duplicate_rows >= 0 "
            "AND skipped_rows >= 0 AND rejected_rows >= 0"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source: Mapped[str] = mapped_column(String(16), default="synthetic")
    status: Mapped[str] = mapped_column(String(16))
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    input_rows: Mapped[int] = mapped_column(Integer, default=0)
    output_rows: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_rows: Mapped[int] = mapped_column(Integer, default=0)
    skipped_rows: Mapped[int] = mapped_column(Integer, default=0)
    rejected_rows: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(String(32))
