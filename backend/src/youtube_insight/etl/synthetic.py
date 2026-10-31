"""Labeled fictional fixture generator. This module performs no I/O."""

from datetime import UTC, datetime, timedelta


def fixture_batch(now: datetime | None = None) -> dict:
    now = now or datetime.now(UTC)
    fetched = now.replace(hour=0, minute=0, second=0, microsecond=0)
    published = fetched - timedelta(days=100)
    return {
        "dataset_kind": "synthetic",
        "channels": [
            {
                "id": "synthetic_channel_alpha",
                "title": "  Fictional Studio Alpha  ",
                "view_count": 1000,
                "subscriber_count": None,
                "published_at": published,
                "fetched_at": fetched,
            },
            {
                "id": "synthetic_channel_beta",
                "title": "Fictional Studio Beta",
                "view_count": 0,
                "subscriber_count": 0,
                "published_at": published,
                "fetched_at": fetched,
            },
        ],
        "videos": [
            {
                "id": "synthetic_video_one",
                "channel_id": "synthetic_channel_alpha",
                "title": "  Example  One ",
                "view_count": 100,
                "like_count": None,
                "comment_count": 0,
                "published_at": published,
                "fetched_at": fetched,
            },
            {
                "id": "synthetic_video_two",
                "channel_id": "synthetic_channel_alpha",
                "title": "Example Two",
                "view_count": None,
                "like_count": 0,
                "comment_count": None,
                "published_at": published,
                "fetched_at": fetched,
            },
            {
                "id": "synthetic_video_three",
                "channel_id": "synthetic_channel_beta",
                "title": "Example Three",
                "view_count": 0,
                "like_count": 0,
                "comment_count": 0,
                "published_at": published,
                "fetched_at": fetched,
            },
        ],
    }
