"""Synthetic YouTube responses only: MockTransport cannot contact the network."""

import json
import logging
from datetime import UTC, datetime
from unittest.mock import patch

import httpx
import pytest
from pydantic import ValidationError

from youtube_insight.config import Settings
from youtube_insight.etl.cli import SafeJSONFormatter, main
from youtube_insight.etl.youtube import (
    API_BASE_URL,
    YouTubeAuthenticationError,
    YouTubeClient,
    YouTubeHTTPError,
    YouTubeNetworkError,
    YouTubeNotFoundError,
    YouTubeQuotaError,
    YouTubeResponseError,
)

NOW = datetime(2026, 10, 31, 12, tzinfo=UTC)
TEST_KEY = "synthetic-key-never-live"


def channel_item(**overrides):
    return {
        "id": "channel1",
        "snippet": {
            "title": "Synthetic channel",
            "publishedAt": "2020-01-01T00:00:00Z",
        },
        "contentDetails": {"relatedPlaylists": {"uploads": "uploads1"}},
        "statistics": {"viewCount": "1000", "subscriberCount": "20", "videoCount": "3"},
        **overrides,
    }


def video_item(video_id="video1", **overrides):
    return {
        "id": video_id,
        "snippet": {
            "channelId": "channel1",
            "title": "Synthetic video",
            "publishedAt": "2021-01-01T00:00:00Z",
            "tags": ["fixture"],
        },
        "contentDetails": {"duration": "PT3M15S", "licensedContent": True},
        "statistics": {"viewCount": "42", "likeCount": "4", "commentCount": "0"},
        **overrides,
    }


@pytest.fixture
def make_client(monkeypatch):
    for name in (
        "YOUTUBE_API_KEY",
        "YOUTUBE_MAX_VIDEOS",
        "YOUTUBE_MAX_RETRIES",
        "YOUTUBE_TIMEOUT_SECONDS",
        "YOUTUBE_BACKOFF_SECONDS",
    ):
        monkeypatch.delenv(name, raising=False)
    clients = []

    def factory(handler, **overrides):
        settings = Settings(_env_file=None, youtube_api_key=TEST_KEY, **overrides)
        delays = []
        client = YouTubeClient(
            settings,
            transport=httpx.MockTransport(handler),
            sleep=delays.append,
            now=lambda: NOW,
        )
        clients.append(client)
        return client, delays

    yield factory
    for client in clients:
        client.close()


def error_response(status, reason):
    return httpx.Response(
        status, json={"error": {"message": TEST_KEY, "errors": [{"reason": reason}]}}
    )


def test_channel_retrieval_headers_and_timestamp(make_client):
    def handler(request):
        assert str(request.url).startswith(API_BASE_URL + "channels?")
        assert request.url.params["part"] == "snippet,contentDetails,statistics"
        assert request.url.params["id"] == "channel1"
        assert "key" not in request.url.params
        assert TEST_KEY not in str(request.url)
        assert request.headers["X-Goog-Api-Key"] == TEST_KEY
        assert request.extensions["timeout"]["read"] == 10
        return httpx.Response(200, json={"items": [channel_item()]})

    client, delays = make_client(handler)
    result = client.get_channel("channel1")
    assert result.uploads_playlist_id == "uploads1"
    assert result.subscriber_count == 20
    assert result.fetched_at == NOW
    assert result.published_at.tzinfo is not None
    assert delays == []


def test_hidden_subscriber_count_and_missing_fields(make_client):
    client, _ = make_client(
        lambda _: httpx.Response(
            200,
            json={
                "items": [
                    channel_item(
                        snippet={},
                        statistics={
                            "hiddenSubscriberCount": True,
                            "subscriberCount": "99",
                        },
                    )
                ]
            },
        )
    )
    result = client.get_channel("channel1")
    assert result.subscriber_count is None
    assert result.view_count is None
    assert result.title is None
    assert result.subscriber_count_hidden


def test_video_retrieval_order_missing_optional_statistics_and_unavailable(make_client):
    def handler(request):
        assert request.url.path.endswith("/videos")
        return httpx.Response(
            200,
            json={
                "items": [
                    video_item("video2", statistics={"viewCount": "0"}),
                    video_item("video1", snippet={}, contentDetails={}, statistics={}),
                ]
            },
        )

    client, _ = make_client(handler)
    result = client.get_videos(["video1", "video2", "missing3", "video1"])
    assert [video.id for video in result] == ["video1", "video2"]
    assert result[0].view_count is None
    assert result[0].title is None
    assert result[0].duration is None
    assert result[0].tags == []
    assert result[1].view_count == 0
    assert result[1].like_count is None
    assert all(video.fetched_at == NOW for video in result)


def test_video_details_and_absent_statistics(make_client):
    item = video_item()
    del item["statistics"]
    client, _ = make_client(lambda _: httpx.Response(200, json={"items": [item]}))
    result = client.get_videos(["video1"])[0]
    assert result.view_count is None
    assert result.duration == "PT3M15S"
    assert result.tags == ["fixture"]
    assert result.licensed_content is True


def test_pagination_and_batch_limits(make_client):
    calls = []

    def handler(request):
        calls.append(request)
        if request.url.path.endswith("/playlistItems"):
            page = int(request.url.params.get("pageToken", "0"))
            size = int(request.url.params["maxResults"])
            assert 1 <= size <= 50
            start = page * 50
            body = {
                "items": [
                    {"contentDetails": {"videoId": f"v{i}"}}
                    for i in range(start, start + size)
                ]
            }
            if page < 2:
                body["nextPageToken"] = str(page + 1)
            return httpx.Response(200, json=body)
        ids = request.url.params["id"].split(",")
        assert len(ids) <= 50
        return httpx.Response(
            200, json={"items": [video_item(value) for value in reversed(ids)]}
        )

    client, _ = make_client(handler, youtube_max_videos=120)
    selection = client.list_playlist_video_ids("uploads1", max_videos=102)
    assert selection.video_ids == [f"v{i}" for i in range(102)]
    assert selection.entries_scanned == 102
    assert selection.pages_fetched == 3
    assert not selection.has_more
    videos = client.get_videos(selection.video_ids)
    assert [video.id for video in videos] == selection.video_ids
    assert [len(call.url.params["id"].split(",")) for call in calls[3:]] == [50, 50, 2]


def test_playlist_limit_and_deduplication_with_unavailable_entry(make_client):
    calls = []

    def handler(request):
        calls.append(request)
        assert request.url.params["maxResults"] == "4"
        return httpx.Response(
            200,
            json={
                "items": [
                    {"contentDetails": {"videoId": "v1"}},
                    {"contentDetails": {"videoId": "v1"}},
                    {"contentDetails": {}},
                    {"contentDetails": {"videoId": "v2"}},
                ],
                "nextPageToken": "next",
            },
        )

    client, _ = make_client(handler)
    selection = client.list_playlist_video_ids("uploads1", max_videos=4)
    assert selection.video_ids == ["v1", "v2"]
    assert selection.entries_scanned == 4
    assert selection.unavailable_entries == 1
    assert selection.has_more
    assert len(calls) == 1


def test_empty_playlist_and_empty_video_list(make_client):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"items": []})

    client, _ = make_client(handler)
    selection = client.list_playlist_video_ids("uploads1")
    assert selection.video_ids == []
    assert selection.pages_fetched == 1
    assert not selection.has_more
    assert client.get_videos([]) == []
    assert len(calls) == 1


def test_sparse_pages_remain_within_quota_budget(make_client):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"items": [], "nextPageToken": str(len(calls))})

    client, _ = make_client(handler)
    selection = client.list_playlist_video_ids("uploads1", max_videos=51)
    assert selection.pages_fetched == 2
    assert selection.has_more
    assert selection.entries_scanned == 0


def test_repeated_page_token_is_rejected(make_client):
    client, _ = make_client(
        lambda _: httpx.Response(200, json={"items": [], "nextPageToken": "same"}),
        youtube_max_videos=150,
    )
    with pytest.raises(YouTubeResponseError, match="Repeated"):
        client.list_playlist_video_ids("uploads1")


@pytest.mark.parametrize("limit", [0, -1, 101, True])
def test_invalid_limit_makes_no_request(make_client, limit):
    def no_request(_):
        pytest.fail("Invalid limit must fail before HTTP")

    client, _ = make_client(no_request)
    with pytest.raises(ValueError):
        client.extract_sample("channel1", max_videos=limit)


def test_oversized_video_input_and_string_input(make_client):
    client, _ = make_client(lambda _: pytest.fail("Invalid batch must not call API"))
    with pytest.raises(ValueError):
        client.get_videos([f"v{i}" for i in range(101)])
    with pytest.raises(ValueError):
        client.get_videos("video1")


@pytest.mark.parametrize(
    ("status", "reason", "error"),
    [
        (400, "keyInvalid", YouTubeAuthenticationError),
        (403, "accessNotConfigured", YouTubeAuthenticationError),
        (401, "anything", YouTubeAuthenticationError),
        (403, "quotaExceeded", YouTubeQuotaError),
        (403, "dailyLimitExceeded", YouTubeQuotaError),
        (403, "forbidden", YouTubeHTTPError),
        (404, "notFound", YouTubeHTTPError),
        (400, "badRequest", YouTubeHTTPError),
    ],
)
def test_non_retryable_errors_are_sanitized(make_client, caplog, status, reason, error):
    calls = []

    def handler(request):
        calls.append(request)
        return error_response(status, reason)

    client, delays = make_client(handler)
    with caplog.at_level(logging.INFO), pytest.raises(error) as caught:
        client.get_channel("channel1")
    assert len(calls) == 1
    assert delays == []
    assert TEST_KEY not in str(caught.value)
    assert TEST_KEY not in caplog.text
    assert caught.value.__cause__ is None


@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
def test_retryable_http_failure_then_success(make_client, status):
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(
                status, headers={"Retry-After": "999"}, json={"error": {}}
            )
        return httpx.Response(200, json={"items": [channel_item()]})

    client, delays = make_client(handler)
    assert client.get_channel("channel1").id == "channel1"
    assert delays == [8.0]
    assert len(calls) == 2


def test_403_rate_limit_is_retryable(make_client):
    client, delays = make_client(lambda _: error_response(403, "rateLimitExceeded"))
    with pytest.raises(YouTubeHTTPError):
        client.get_channel("channel1")
    assert delays == [0.5, 1.0]


@pytest.mark.parametrize(
    "exception", [httpx.ReadTimeout, httpx.ConnectTimeout, httpx.ConnectError]
)
def test_transport_errors_are_bounded_sanitized_and_logged(
    make_client, caplog, exception
):
    calls = []

    def handler(request):
        calls.append(request)
        raise exception(f"private request {TEST_KEY}", request=request)

    client, delays = make_client(handler)
    with caplog.at_level(logging.INFO), pytest.raises(YouTubeNetworkError) as caught:
        client.get_channel("channel1")
    assert len(calls) == 3
    assert delays == [0.5, 1.0]
    assert TEST_KEY not in str(caught.value)
    assert TEST_KEY not in caplog.text
    assert caught.value.__context__ is None
    retries = [
        record for record in caplog.records if record.message == "youtube_request_retry"
    ]
    assert retries[0].endpoint == "channels"
    assert retries[0].attempt == 1
    assert retries[0].category == "network"


def test_no_retries_when_disabled(make_client):
    client, delays = make_client(lambda _: httpx.Response(503), youtube_max_retries=0)
    with pytest.raises(YouTubeHTTPError):
        client.get_channel("channel1")
    assert delays == []


@pytest.mark.parametrize("body", ["not json", "[]", "{}", '{"items":null}'])
def test_invalid_response_body(make_client, body):
    client, delays = make_client(lambda _: httpx.Response(200, text=body))
    with pytest.raises(YouTubeResponseError):
        client.get_channel("channel1")
    assert delays == []


def test_channel_not_found_and_invalid_identity(make_client):
    client, _ = make_client(lambda _: httpx.Response(200, json={"items": []}))
    with pytest.raises(YouTubeNotFoundError):
        client.get_channel("channel1")
    other, _ = make_client(
        lambda _: httpx.Response(200, json={"items": [channel_item(id="other")]})
    )
    with pytest.raises(YouTubeResponseError):
        other.get_channel("channel1")


def test_invalid_video_metadata_does_not_escape_validation_error(make_client):
    client, _ = make_client(
        lambda _: httpx.Response(
            200, json={"items": [video_item(statistics={"viewCount": "-4"})]}
        )
    )
    with pytest.raises(YouTubeResponseError):
        client.get_videos(["video1"])


def test_end_to_end_sample_is_extraction_only(make_client):
    endpoints = []

    def handler(request):
        endpoint = request.url.path.rsplit("/", 1)[-1]
        endpoints.append(endpoint)
        if endpoint == "channels":
            body = {"items": [channel_item()]}
        elif endpoint == "playlistItems":
            body = {
                "items": [
                    {"contentDetails": {"videoId": "video1"}},
                    {"contentDetails": {"videoId": "missing2"}},
                ]
            }
        else:
            body = {"items": [video_item()]}
        return httpx.Response(200, json=body)

    client, _ = make_client(handler)
    sample = client.extract_sample("channel1", max_videos=2)
    assert endpoints == ["channels", "playlistItems", "videos"]
    assert sample.unavailable_video_ids == ["missing2"]
    assert sample.max_videos == 2
    assert sample.completed_at == NOW
    assert len(sample.videos) == 1


def test_missing_key_without_http(monkeypatch):
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    with pytest.raises(YouTubeAuthenticationError):
        YouTubeClient(Settings(_env_file=None))


@pytest.mark.parametrize(
    "values",
    [
        {"youtube_timeout_seconds": 0},
        {"youtube_max_retries": 6},
        {"youtube_max_videos": 501},
        {"youtube_backoff_seconds": -1},
        {"youtube_timeout_seconds": float("nan")},
    ],
)
def test_settings_safety_bounds(values):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values)


def test_cli_requires_explicit_live_opt_in(capsys):
    with patch("youtube_insight.etl.cli.YouTubeClient") as constructor:
        with pytest.raises(SystemExit) as caught:
            main(["--channel-id", "channel1"])
    assert caught.value.code == 2
    constructor.assert_not_called()
    assert "No calls made" in capsys.readouterr().err


def test_cli_successful_sample_uses_mock_transport(make_client, capsys):
    def handler(request):
        if request.url.path.endswith("/channels"):
            return httpx.Response(200, json={"items": [channel_item()]})
        return httpx.Response(200, json={"items": []})

    client, _ = make_client(handler)
    with patch("youtube_insight.etl.cli.YouTubeClient", return_value=client):
        assert main(["--channel-id", "channel1", "--max-videos", "2", "--live"]) == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out)["videos"] == []
    assert TEST_KEY not in captured.out + captured.err
    assert (
        json.loads(captured.err.splitlines()[0])["event"] == "youtube_request_succeeded"
    )


def test_cli_invalid_configuration_is_sanitized(capsys):
    with patch("youtube_insight.etl.cli.Settings", side_effect=ValueError("bad setup")):
        assert main(["--live"]) == 1
    assert "bad setup" in capsys.readouterr().err


def test_json_logging_allowlists_fields():
    record = logging.LogRecord(
        "test", logging.INFO, "", 0, "youtube_request_retry", (), None
    )
    record.endpoint = "channels"
    record.headers = {"key": TEST_KEY}
    result = SafeJSONFormatter().format(record)
    assert TEST_KEY not in result
    assert json.loads(result)["endpoint"] == "channels"


@pytest.mark.parametrize(
    "reason", ["API_KEY_INVALID", "API_KEY_EXPIRED", "API_KEY_SERVICE_BLOCKED"]
)
def test_google_error_info_key_failure(make_client, reason):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            400,
            json={
                "error": {
                    "message": TEST_KEY,
                    "details": [
                        {
                            "@type": "type.googleapis.com/google.rpc.ErrorInfo",
                            "reason": reason,
                        }
                    ],
                }
            },
        )

    client, delays = make_client(handler)
    with pytest.raises(YouTubeAuthenticationError):
        client.get_channel("channel1")
    assert len(calls) == 1
    assert delays == []


def test_transport_timeout_then_recovers(make_client):
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            raise httpx.ReadTimeout("synthetic timeout", request=request)
        return httpx.Response(200, json={"items": [channel_item()]})

    client, delays = make_client(handler)
    assert client.get_channel("channel1").id == "channel1"
    assert len(calls) == 2
    assert delays == [0.5]


@pytest.mark.parametrize("retry_after", ["garbage", "NaN", "-1"])
def test_invalid_retry_after_uses_bounded_backoff(make_client, retry_after):
    client, delays = make_client(
        lambda _: httpx.Response(503, headers={"Retry-After": retry_after})
    )
    with pytest.raises(YouTubeHTTPError):
        client.get_channel("channel1")
    assert delays == [0.5, 1.0]


def test_redirect_is_not_followed_with_key(make_client):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(302, headers={"Location": "https://untrusted.example/"})

    client, delays = make_client(handler)
    with pytest.raises(YouTubeHTTPError):
        client.get_channel("channel1")
    assert len(requests) == 1
    assert delays == []


def test_cli_missing_key_is_safe_and_makes_no_http(monkeypatch, capsys):
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    settings = Settings(_env_file=None)
    with (
        patch("youtube_insight.etl.cli.Settings", return_value=settings),
        patch("httpx.Client.get") as get,
    ):
        assert main(["--live", "--channel-id", "channel1"]) == 1
        get.assert_not_called()
    assert "YOUTUBE_API_KEY is required" in capsys.readouterr().err


def test_missing_uploads_and_malformed_playlist_are_sanitized(make_client):
    client, _ = make_client(
        lambda _: httpx.Response(200, json={"items": [channel_item(contentDetails={})]})
    )
    with pytest.raises(YouTubeResponseError):
        client.get_channel("channel1")
    other, _ = make_client(lambda _: httpx.Response(200, json={"items": [None]}))
    with pytest.raises(YouTubeResponseError):
        other.list_playlist_video_ids("uploads1")


def test_invalid_channel_input_fails_before_http(make_client):
    client, _ = make_client(lambda _: pytest.fail("No request for invalid identifier"))
    with pytest.raises(ValueError):
        client.get_channel("https://example.com/channel")


def test_publication_offset_normalizes_to_utc(make_client):
    item = video_item(snippet={"publishedAt": "2021-01-01T02:30:00+02:30"})
    client, _ = make_client(lambda _: httpx.Response(200, json={"items": [item]}))
    video = client.get_videos(["video1"])[0]
    assert video.published_at == datetime(2021, 1, 1, tzinfo=UTC)
    assert video.published_at.utcoffset().total_seconds() == 0


def test_naive_publication_timestamp_is_rejected(make_client):
    item = channel_item(snippet={"publishedAt": "2020-01-01T00:00:00"})
    client, _ = make_client(lambda _: httpx.Response(200, json={"items": [item]}))
    with pytest.raises(YouTubeResponseError, match="Malformed channel"):
        client.get_channel("channel1")


def test_oversized_playlist_page_is_rejected_instead_of_silently_truncated(make_client):
    client, _ = make_client(
        lambda _: httpx.Response(
            200,
            json={
                "items": [
                    {"contentDetails": {"videoId": "v1"}},
                    {"contentDetails": {"videoId": "v2"}},
                ]
            },
        )
    )
    with pytest.raises(YouTubeResponseError, match="Malformed playlist"):
        client.list_playlist_video_ids("uploads1", max_videos=1)


def test_duplicate_video_response_is_rejected(make_client):
    client, _ = make_client(
        lambda _: httpx.Response(200, json={"items": [video_item(), video_item()]})
    )
    with pytest.raises(YouTubeResponseError, match="Malformed video"):
        client.get_videos(["video1"])


def test_later_batch_error_never_returns_a_partial_success(make_client):
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) > 1:
            return error_response(403, "quotaExceeded")
        return httpx.Response(
            200,
            json={
                "items": [
                    video_item(value) for value in request.url.params["id"].split(",")
                ]
            },
        )

    client, _ = make_client(handler)
    with pytest.raises(YouTubeQuotaError):
        client.get_videos([f"v{i}" for i in range(51)])
    assert len(calls) == 2
