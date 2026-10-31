"""Strict fixture validation followed by explicit Pandas normalization."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

import pandas as pd
from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
)

SyntheticID = Annotated[
    str, StringConstraints(pattern=r"^synthetic_[A-Za-z0-9_-]{1,110}$")
]
Count = Annotated[int, Field(strict=True, ge=0, le=2**63 - 1)]


class DataQualityError(ValueError):
    """A safe description; never copy rejected row data or validation errors."""


class FixtureChannel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: SyntheticID
    title: str
    view_count: Count | None = None
    subscriber_count: Count | None = None
    published_at: AwareDatetime | None = None
    fetched_at: AwareDatetime


class FixtureVideo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: SyntheticID
    channel_id: SyntheticID
    title: str
    view_count: Count | None = None
    like_count: Count | None = None
    comment_count: Count | None = None
    published_at: AwareDatetime | None = None
    fetched_at: AwareDatetime


class SyntheticBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_kind: Literal["synthetic"]
    channels: list[FixtureChannel] = Field(min_length=1, max_length=100)
    videos: list[FixtureVideo] = Field(max_length=5000)


@dataclass
class TransformedBatch:
    channels: pd.DataFrame
    videos: pd.DataFrame
    input_rows: int
    duplicate_rows: int


def require_clock(now: datetime) -> datetime:
    if now.tzinfo is None:
        raise ValueError("Clock must be timezone-aware")
    return now.astimezone(UTC)


def _frame(
    rows: list[BaseModel], model: type[BaseModel], now: datetime, ttl: int
) -> pd.DataFrame:
    # Object dtype prevents float inference from rounding large integer counts.
    frame = pd.DataFrame(
        [row.model_dump() for row in rows],
        columns=list(model.model_fields),
        dtype=object,
    )
    frame["title"] = frame["title"].str.replace(r"\s+", " ", regex=True).str.strip()
    if frame["title"].eq("").any():
        raise DataQualityError("Titles must not be blank")
    for name in ("published_at", "fetched_at"):
        frame[name] = pd.to_datetime(frame[name], utc=True)
    for name in frame.columns:
        if name.endswith("_count"):
            frame[name] = pd.array(frame[name], dtype="Int64")
    if (frame["fetched_at"] > now).any() or (
        frame["published_at"] > frame["fetched_at"]
    ).any():
        raise DataQualityError("Invalid publication or collection chronology")
    frame["expires_at"] = frame["fetched_at"] + timedelta(days=ttl)
    if (frame["expires_at"] <= now).any():
        raise DataQualityError("Input observations are expired")
    frame["source"] = "synthetic"
    # Identical duplicates are safe; conflicting same-time observations are not.
    distinct = frame.drop_duplicates()
    if distinct.duplicated(["id", "fetched_at"]).any():
        raise DataQualityError(
            "Conflicting observations share an ID and collection time"
        )
    return (
        distinct.sort_values("fetched_at", kind="stable")
        .drop_duplicates("id", keep="last")
        .reset_index(drop=True)
    )


def transform_synthetic(
    payload: dict, *, now: datetime, retention_days: int = 30
) -> TransformedBatch:
    now = require_clock(now)
    if (
        isinstance(retention_days, bool)
        or not isinstance(retention_days, int)
        or not 1 <= retention_days <= 30
    ):
        raise ValueError("Synthetic retention must be 1–30 days")
    try:
        batch = SyntheticBatch.model_validate(payload)
    except ValidationError:
        raise DataQualityError("Invalid synthetic fixture schema or values") from None
    try:
        channels = _frame(batch.channels, FixtureChannel, now, retention_days)
        videos = _frame(batch.videos, FixtureVideo, now, retention_days)
    except (ValueError, TypeError, OverflowError):
        raise DataQualityError(
            "Invalid fixture chronology, conflicts or values"
        ) from None
    # Reject ownership changes even between older/newer versions of the same video.
    ownership = {(video.id, video.channel_id) for video in batch.videos}
    if len({video_id for video_id, _ in ownership}) != len(ownership):
        raise DataQualityError("Conflicting video channel ownership")
    if not set(videos["channel_id"]).issubset(set(channels["id"])):
        raise DataQualityError("Video references a channel absent from the batch")
    inputs = len(batch.channels) + len(batch.videos)
    return TransformedBatch(
        channels, videos, inputs, inputs - len(channels) - len(videos)
    )


def frame_records(frame: pd.DataFrame) -> list[dict]:
    """Convert Pandas missing values/timestamps for the persistence boundary."""
    return [
        {
            name: None
            if pd.isna(value)
            else value.to_pydatetime()
            if isinstance(value, pd.Timestamp)
            else value
            for name, value in row.items()
        }
        for row in frame.to_dict(orient="records")
    ]
