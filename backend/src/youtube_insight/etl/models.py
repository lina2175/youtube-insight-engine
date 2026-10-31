"""Normalized public metadata. Missing statistics remain unknown, never zero."""

from datetime import UTC, datetime

from pydantic import AwareDatetime, BaseModel, Field, field_validator


class MetadataModel(BaseModel):
    @field_validator("published_at", "fetched_at", "completed_at", check_fields=False)
    @classmethod
    def normalize_timestamp(cls, value: AwareDatetime | None) -> datetime | None:
        return value.astimezone(UTC) if value is not None else None


class ChannelMetadata(MetadataModel):
    id: str
    title: str | None = None
    description: str | None = None
    published_at: AwareDatetime | None = None
    country: str | None = None
    uploads_playlist_id: str
    view_count: int | None = Field(default=None, ge=0)
    subscriber_count: int | None = Field(default=None, ge=0)
    subscriber_count_hidden: bool = False
    video_count: int | None = Field(default=None, ge=0)
    fetched_at: AwareDatetime


class VideoMetadata(MetadataModel):
    id: str
    channel_id: str | None = None
    title: str | None = None
    description: str | None = None
    published_at: AwareDatetime | None = None
    category_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    duration: str | None = None
    caption: str | None = None
    licensed_content: bool | None = None
    live_broadcast_content: str | None = None
    view_count: int | None = Field(default=None, ge=0)
    like_count: int | None = Field(default=None, ge=0)
    comment_count: int | None = Field(default=None, ge=0)
    fetched_at: AwareDatetime


class PlaylistSelection(MetadataModel):
    video_ids: list[str]
    entries_scanned: int
    unavailable_entries: int
    pages_fetched: int
    has_more: bool
    fetched_at: AwareDatetime


class ExtractionSample(MetadataModel):
    channel: ChannelMetadata
    videos: list[VideoMetadata]
    unavailable_video_ids: list[str]
    playlist: PlaylistSelection
    max_videos: int
    completed_at: AwareDatetime
