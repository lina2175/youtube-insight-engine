"""Bounded synchronous YouTube Data API v3 client with injectable HTTP transport."""

import logging
import math
import re
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Any

import httpx
from pydantic import ValidationError

from youtube_insight.config import Settings
from youtube_insight.etl.models import (
    ChannelMetadata,
    ExtractionSample,
    PlaylistSelection,
    VideoMetadata,
)

logger = logging.getLogger(__name__)
API_BASE_URL = "https://www.googleapis.com/youtube/v3/"
BATCH_SIZE = 50
_IDENTIFIER = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")


class YouTubeError(Exception):
    """Sanitized errors: no remote body, request object, key or transport exception."""


class YouTubeAuthenticationError(YouTubeError):
    pass


class YouTubeQuotaError(YouTubeError):
    pass


class YouTubeHTTPError(YouTubeError):
    pass


class YouTubeNetworkError(YouTubeError):
    pass


class YouTubeResponseError(YouTubeError):
    pass


class YouTubeNotFoundError(YouTubeError):
    pass


def utc_now() -> datetime:
    return datetime.now(UTC)


def validate_identifier(value: str) -> str:
    if not _IDENTIFIER.fullmatch(value):
        raise ValueError("Resource IDs must contain only letters, digits, '_' or '-'")
    return value


class YouTubeClient:
    """Owns its HTTP client. Use a context manager to close connections reliably."""

    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        now: Callable[[], datetime] = utc_now,
    ) -> None:
        key = settings.youtube_api_key
        if key is None or not key.get_secret_value().strip():
            raise YouTubeAuthenticationError(
                "YOUTUBE_API_KEY is required for extraction"
            )
        self._settings = settings
        self._sleep = sleep
        self._now = now
        self._http = httpx.Client(
            base_url=API_BASE_URL,
            # Google API system header keeps the key out of URLs and access logs.
            headers={
                "X-Goog-Api-Key": key.get_secret_value(),
                "Accept": "application/json",
            },
            timeout=httpx.Timeout(settings.youtube_timeout_seconds),
            follow_redirects=False,
            transport=transport,
        )

    def __enter__(self) -> "YouTubeClient":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    def _timestamp(self) -> datetime:
        timestamp = self._now()
        if timestamp.tzinfo is None:
            raise ValueError("Collection clock must return a timezone-aware datetime")
        return timestamp.astimezone(UTC)

    @staticmethod
    def _error_reasons(response: httpx.Response) -> set[str]:
        try:
            error = response.json()["error"]
            reasons: set[str] = set()
            for field in ("errors", "details"):
                entries = error.get(field, [])
                if isinstance(entries, list):
                    reasons.update(
                        item["reason"]
                        for item in entries
                        if isinstance(item, dict)
                        and isinstance(item.get("reason"), str)
                    )
            return reasons
        except (ValueError, TypeError, KeyError, AttributeError):
            return set()

    def _delay(self, attempt: int, response: httpx.Response | None) -> float:
        delay = min(8.0, self._settings.youtube_backoff_seconds * 2**attempt)
        if response is not None:
            try:
                retry_after = float(response.headers.get("Retry-After", ""))
                if math.isfinite(retry_after):
                    delay = min(8.0, max(delay, retry_after))
            except ValueError:
                pass
        return delay

    def _request(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        for attempt in range(self._settings.youtube_max_retries + 1):
            response = None
            category = "network"
            status = None
            try:
                response = self._http.get(endpoint, params=params)
            except httpx.TransportError:
                # Never retain or chain credential-bearing HTTPX request exceptions.
                pass
            if response is not None:
                status = response.status_code
                reasons = self._error_reasons(response) if status >= 400 else set()
                if reasons & {
                    "quotaExceeded",
                    "dailyLimitExceeded",
                    "dailyLimitExceededUnreg",
                    "QUOTA_EXCEEDED",
                    "DAILY_LIMIT_EXCEEDED",
                }:
                    logger.warning(
                        "youtube_request_failed",
                        extra={
                            "endpoint": endpoint,
                            "category": "quota",
                            "status": status,
                        },
                    )
                    raise YouTubeQuotaError(
                        "YouTube quota exhausted; no automatic retry"
                    )
                if status == 401 or reasons & {
                    "keyInvalid",
                    "accessNotConfigured",
                    "ipRefererBlocked",
                    "authError",
                    "forbiddenReferer",
                    "API_KEY_INVALID",
                    "API_KEY_EXPIRED",
                    "API_KEY_SERVICE_BLOCKED",
                    "API_KEY_HTTP_REFERRER_BLOCKED",
                    "API_KEY_IP_ADDRESS_BLOCKED",
                    "API_KEY_ANDROID_APP_BLOCKED",
                    "API_KEY_IOS_APP_BLOCKED",
                    "SERVICE_DISABLED",
                }:
                    logger.warning(
                        "youtube_request_failed",
                        extra={
                            "endpoint": endpoint,
                            "category": "authentication",
                            "status": status,
                        },
                    )
                    raise YouTubeAuthenticationError(
                        "YouTube API key or API access rejected"
                    )
                if 200 <= status < 300:
                    try:
                        body = response.json()
                        if not isinstance(body, dict) or not isinstance(
                            body.get("items"), list
                        ):
                            raise ValueError
                    except ValueError:
                        raise YouTubeResponseError(
                            "Malformed YouTube response"
                        ) from None
                    logger.info(
                        "youtube_request_succeeded",
                        extra={
                            "endpoint": endpoint,
                            "attempt": attempt + 1,
                            "status": status,
                        },
                    )
                    return body
                if not (
                    status == 429
                    or 500 <= status <= 599
                    or reasons & {"rateLimitExceeded", "userRateLimitExceeded"}
                ):
                    logger.warning(
                        "youtube_request_failed",
                        extra={
                            "endpoint": endpoint,
                            "category": "http",
                            "status": status,
                        },
                    )
                    raise YouTubeHTTPError(f"YouTube HTTP request rejected ({status})")
                category = "retryable_http"
            if attempt == self._settings.youtube_max_retries:
                logger.warning(
                    "youtube_request_failed",
                    extra={
                        "endpoint": endpoint,
                        "category": category,
                        "status": status,
                        "attempt": attempt + 1,
                    },
                )
                if response is None:
                    raise YouTubeNetworkError(
                        "YouTube network request failed after bounded attempts"
                    )
                raise YouTubeHTTPError(
                    f"YouTube HTTP request failed after bounded attempts ({status})"
                )
            delay = self._delay(attempt, response)
            logger.warning(
                "youtube_request_retry",
                extra={
                    "endpoint": endpoint,
                    "category": category,
                    "status": status,
                    "attempt": attempt + 1,
                    "delay_seconds": delay,
                },
            )
            self._sleep(delay)
        raise AssertionError("Retry loop must return or raise")

    def get_channel(self, channel_id: str) -> ChannelMetadata:
        channel_id = validate_identifier(channel_id)
        body = self._request(
            "channels", {"part": "snippet,contentDetails,statistics", "id": channel_id}
        )
        if not body["items"]:
            raise YouTubeNotFoundError("Public channel not found")
        try:
            item = body["items"][0]
            if item["id"] != channel_id:
                raise ValueError
            snippet = item.get("snippet", {})
            statistics = item.get("statistics", {})
            hidden = statistics.get("hiddenSubscriberCount", False)
            return ChannelMetadata(
                id=item["id"],
                title=snippet.get("title"),
                description=snippet.get("description"),
                published_at=snippet.get("publishedAt"),
                country=snippet.get("country"),
                uploads_playlist_id=validate_identifier(
                    item["contentDetails"]["relatedPlaylists"]["uploads"]
                ),
                view_count=statistics.get("viewCount"),
                subscriber_count=None if hidden else statistics.get("subscriberCount"),
                subscriber_count_hidden=hidden,
                video_count=statistics.get("videoCount"),
                fetched_at=self._timestamp(),
            )
        except (KeyError, TypeError, ValueError, AttributeError, ValidationError):
            raise YouTubeResponseError("Malformed channel metadata") from None

    def list_playlist_video_ids(
        self, playlist_id: str, *, max_videos: int | None = None
    ) -> PlaylistSelection:
        playlist_id = validate_identifier(playlist_id)
        limit = self._limit(max_videos)
        selected: list[str] = []
        scanned = unavailable = pages = 0
        token: str | None = None
        seen_tokens: set[str] = set()
        # Bound quota even if the API returns sparse pages or repeated tokens.
        page_budget = math.ceil(limit / BATCH_SIZE)
        while pages < page_budget and scanned < limit:
            params: dict[str, Any] = {
                "part": "contentDetails",
                "playlistId": playlist_id,
                "maxResults": min(BATCH_SIZE, limit - scanned),
            }
            if token:
                params["pageToken"] = token
            body = self._request("playlistItems", params)
            pages += 1
            try:
                if len(body["items"]) > params["maxResults"]:
                    raise ValueError
                for item in body["items"]:
                    scanned += 1
                    video_id = item.get("contentDetails", {}).get("videoId")
                    if video_id is None:
                        unavailable += 1
                    else:
                        video_id = validate_identifier(video_id)
                        if video_id not in selected:
                            selected.append(video_id)
                token = body.get("nextPageToken")
                if token is not None and (not isinstance(token, str) or not token):
                    raise ValueError
            except (TypeError, ValueError, AttributeError):
                raise YouTubeResponseError("Malformed playlist metadata") from None
            if not token:
                break
            if token in seen_tokens:
                raise YouTubeResponseError("Repeated playlist page token")
            seen_tokens.add(token)
        return PlaylistSelection(
            video_ids=selected,
            entries_scanned=scanned,
            unavailable_entries=unavailable,
            pages_fetched=pages,
            has_more=bool(token),
            fetched_at=self._timestamp(),
        )

    def _limit(self, max_videos: int | None) -> int:
        limit = self._settings.youtube_max_videos if max_videos is None else max_videos
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= self._settings.youtube_max_videos
        ):
            raise ValueError(
                "Video limit must be within the configured positive maximum"
            )
        return limit

    def get_videos(self, video_ids: Sequence[str]) -> list[VideoMetadata]:
        if isinstance(video_ids, str):
            raise ValueError("Provide a sequence of video IDs, not a string")
        ids = list(dict.fromkeys(validate_identifier(value) for value in video_ids))
        if len(ids) > self._settings.youtube_max_videos:
            raise ValueError("Video IDs exceed the configured maximum")
        found: dict[str, VideoMetadata] = {}
        for start in range(0, len(ids), BATCH_SIZE):
            batch = ids[start : start + BATCH_SIZE]
            body = self._request(
                "videos",
                {"part": "snippet,contentDetails,statistics", "id": ",".join(batch)},
            )
            timestamp = self._timestamp()
            try:
                for item in body["items"]:
                    video_id = item["id"]
                    if video_id not in batch or video_id in found:
                        raise ValueError
                    snippet = item.get("snippet", {})
                    details = item.get("contentDetails", {})
                    statistics = item.get("statistics", {})
                    found[video_id] = VideoMetadata(
                        id=video_id,
                        channel_id=snippet.get("channelId"),
                        title=snippet.get("title"),
                        description=snippet.get("description"),
                        published_at=snippet.get("publishedAt"),
                        category_id=snippet.get("categoryId"),
                        tags=snippet.get("tags", []),
                        duration=details.get("duration"),
                        caption=details.get("caption"),
                        licensed_content=details.get("licensedContent"),
                        live_broadcast_content=snippet.get("liveBroadcastContent"),
                        view_count=statistics.get("viewCount"),
                        like_count=statistics.get("likeCount"),
                        comment_count=statistics.get("commentCount"),
                        fetched_at=timestamp,
                    )
            except (KeyError, TypeError, ValueError, AttributeError, ValidationError):
                raise YouTubeResponseError("Malformed video metadata") from None
        return [found[video_id] for video_id in ids if video_id in found]

    def extract_sample(
        self, channel_id: str, *, max_videos: int | None = None
    ) -> ExtractionSample:
        limit = self._limit(max_videos)
        channel = self.get_channel(channel_id)
        playlist = self.list_playlist_video_ids(
            channel.uploads_playlist_id, max_videos=limit
        )
        videos = self.get_videos(playlist.video_ids)
        returned = {video.id for video in videos}
        return ExtractionSample(
            channel=channel,
            videos=videos,
            playlist=playlist,
            max_videos=limit,
            unavailable_video_ids=[
                value for value in playlist.video_ids if value not in returned
            ],
            completed_at=self._timestamp(),
        )
