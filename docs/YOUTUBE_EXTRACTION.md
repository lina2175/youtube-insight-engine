# Public YouTube extraction (Phase 2)

## Scope and data flow

This phase implements extraction only, using the official YouTube Data API v3 at `https://www.googleapis.com/youtube/v3/`. There are no database writes, new FastAPI routes, UI analytics, schedules or revenue calculations. The existing web application remains an offline foundation; it does not invoke this client.

1. `channels.list`: send the configured channel ID with `part=snippet,contentDetails,statistics`. Extract channel title/description, publication time, optional country and counts, and `contentDetails.relatedPlaylists.uploads`.
2. `playlistItems.list`: request the uploads playlist with `part=contentDetails` and `maxResults` between 1 and 50. Follow `nextPageToken` using `pageToken`. Read `contentDetails.videoId`, keeping playlist order and deduplicating IDs.
3. `videos.list`: split selected IDs into batches of at most 50; request `part=snippet,contentDetails,statistics`. Do not send `pageToken` or `maxResults` with the ID filter. Normalize results and restore requested order, since API response order is not guaranteed.
4. Return typed Pydantic models. Each channel, playlist selection and video has an aware UTC `fetched_at`; the sample also has `completed_at`. All publication and collection timestamps must include a timezone and normalize to UTC. Naive timestamps are rejected. These are collection times, not evidence of when YouTube last updated its counters. No raw response is persisted.

Available video fields: ID, channel ID, title, description, publication time, category, tags, ISO 8601 duration, caption flag, licensed-content flag, live-broadcast marker and public view/like/comment counts. Missing values stay `null` (tags default to an empty list). A known zero stays zero. Hidden subscriber counts remain `null` even if a count is present in a response.

A channel response with no items raises a not-found error. A video omitted from `videos.list` is reported in `unavailable_video_ids`; this does not establish whether it was deleted, private, restricted or otherwise unavailable. Missing playlist `videoId` entries are counted separately. Unexpected/malformed responses fail with a sanitized response error, not fabricated metadata. Oversized playlist pages and duplicate video response IDs are rejected rather than silently truncated/overwritten. An extraction failure produces no partial sample JSON.

## Limits, pagination and coverage

`YOUTUBE_MAX_VIDEOS` defaults to 100 and has an application ceiling of 500. It bounds the unique IDs accepted by `get_videos` and the maximum playlist entries inspected by traversal. The sample CLI defaults to 5 entries and cannot exceed that configured cap. Duplicate or unavailable entries count toward the traversal limit, so a sample may contain fewer actual videos.

For limit N, playlist traversal also has a page budget of `ceil(N / 50)` to bound quota if responses are sparse. It stops at exhaustion, the entry limit or that page budget. `playlist.has_more=true` means an API page token remained when traversal stopped; it is not a complete inventory. Repeated page tokens are rejected if encountered while traversing. A false value only describes the API traversal result at collection time, not a guarantee that every historical upload is publicly available.

Logical request upper bound for a sample is `1 + ceil(N / 50) + ceil(N / 50)`. Actual attempts multiply each request by at most `1 + YOUTUBE_MAX_RETRIES`. A default five-entry sample usually takes three logical requests and can take up to nine attempts with default retries. No `search.list` calls are used. These are request bounds, not a certified current quota-unit estimate: review Google's current quota documentation and configure project quota alerts before live use.

## Server configuration

Copy root `.env.example` to an ignored root `.env` without overwriting existing values, or use secure process environment bindings. Never put keys in frontend configuration, command arguments, Git, logs or screenshots.

| Variable | Default / bounds | Purpose |
| --- | --- | --- |
| `YOUTUBE_API_KEY` | unset | Required only when constructing the extraction client |
| `YOUTUBE_CHANNEL_ID` | unset | Optional CLI default channel; verify the intended artist identity |
| `YOUTUBE_MAX_VIDEOS` | 100; 1–500 | Maximum sample traversal entries / direct unique video IDs |
| `YOUTUBE_TIMEOUT_SECONDS` | 10; >0–60 | HTTPX connect/read/write/pool operation timeout |
| `YOUTUBE_MAX_RETRIES` | 2; 0–5 | Additional attempts after the initial request |
| `YOUTUBE_BACKOFF_SECONDS` | 0.5; 0–8 | Initial exponential retry delay |

The API key is supplied using Google's `X-Goog-Api-Key` system header, not a query parameter. Redirects are not followed, preventing forwarding to a redirect target. TLS verification stays enabled. Existing proxy/CA settings are respected. The key stays in the server process; normalized models and errors do not contain it. Avoid enabling header dumps or third-party wire/debug instrumentation around real keys.

Restrict the key to YouTube Data API v3 and supported server application restrictions. Enable the API in its Google Cloud project, review quota/usage alerts, and rotate any exposed key. Do not add OAuth or private Analytics access for this public-data client.

## Retry and error contract

- Retry transport errors (including connect/read timeouts), HTTP 429, 5xx, and recognized temporary rate-limit reasons. Network failures raise `YouTubeNetworkError` after exhaustion; retryable HTTP failures raise `YouTubeHTTPError` after exhaustion.
- Exponential delay is `min(8, backoff × 2^attempt)`. A numeric `Retry-After` can increase that delay only up to 8 seconds. Invalid/non-finite values and HTTP-date values use the normal backoff. This deliberately bounds waiting; a persistent limit may still fail after retries. This client does not promise to wait until a quota reset.
- Invalid/restricted/expired key or disabled API errors raise `YouTubeAuthenticationError` immediately. Recognize both legacy error reasons and modern Google ErrorInfo details.
- Recognized quota exhaustion raises `YouTubeQuotaError` immediately. Ordinary permanent 4xx errors do not retry. Unknown 403 errors remain HTTP errors rather than being guessed to mean an invalid key or exhausted quota.
- Malformed successful responses raise `YouTubeResponseError` without retry. Missing channels raise `YouTubeNotFoundError`.

The CLI logs JSON events to stderr with an allowlist: event, level, endpoint name, status, attempt, category and retry delay. It does not log request headers, URLs, API keys, response bodies, titles, descriptions, exception objects or stack traces. The library emits structured standard-logging records without configuring the caller's logging globally. Remote error messages are never copied into exceptions. Collection stops on terminal errors; it never substitutes zeros or a fake successful sample.

## CLI and reusable Python API

Install from the repository root:

```bash
uv sync --project backend --frozen
uv run --project backend --frozen youtube-sample --help
```

After configuring the server key, reviewing current YouTube policies and verifying the intended channel identity, explicitly request a small live sample:

```bash
uv run --project backend --frozen youtube-sample \
  --channel-id UCLwbyg15zJgjtNL0EErkOPA --max-videos 5 --live
```

Without `--live`, the CLI exits before configuration/client creation and makes no requests. No sample above was run live during implementation. The proposed channel's ownership remains unverified. The CLI emits normalized JSON to stdout and sanitized events to stderr. It does not create files. Treat stdout as API data: do not commit/capture it or introduce stored exports before retention/deletion policy work. Terminal tools may retain output in scrollback/session logs; avoid retaining it and clear/delete captures under the applicable rules. Automated tests never invoke the real API.

Reusable entry points:

```python
from youtube_insight.config import Settings
from youtube_insight.etl.youtube import YouTubeClient

# Explicitly live; only invoke with appropriate server configuration and policy review.
with YouTubeClient(Settings()) as client:
    sample = client.extract_sample("verified_channel_id", max_videos=5)
    # Or call get_channel, list_playlist_video_ids, and get_videos separately.
```

Use a context manager or call `close()`. Tests inject `httpx.MockTransport`, a fake clock and a sleep recorder. The suite blocks real HTTPX transport calls globally; unit tests cannot silently consume live quota. No Google SDK is required: HTTPX was already installed for Phase 1 tests and is now a runtime dependency, with no transitive package upgrades.

## Policy-review status and live-use gate

On 2026-10-31 the environment denied `developers.google.com` with tunnel HTTP 403. Current policy and quota-page review could not be completed. The Google-maintained API discovery document on GitHub was accessible and used to verify endpoint paths, `part`/`pageToken` contracts, playlist page size and the incompatibility of `pageToken`/`maxResults` with the video ID filter. Discovery documentation is not a policy review or live verification of credentials, header authentication or channel identity.

Before live use, review and date the applicable rules at:

- https://developers.google.com/youtube/terms/api-services-terms-of-service
- https://developers.google.com/youtube/terms/developer-policies
- https://developers.google.com/youtube/v3/determine_quota_cost
- https://developers.google.com/youtube/v3/docs/channels/list
- https://developers.google.com/youtube/v3/docs/playlistItems/list
- https://developers.google.com/youtube/v3/docs/videos/list

Accessible contract reference: https://github.com/googleapis/google-api-python-client/blob/main/googleapiclient/discovery_cache/documents/youtube.v3.json

This extraction-only phase introduces no SQLite loading, snapshots, exports, caching or derived metrics. Any retained API output still requires policy-compliant handling; do not treat public visibility as permission for indefinite retention. Freshness, refresh, deletion cascades and expiry enforcement remain required before a separately authorized persistence phase. The earlier 30-day cap is provisional planning guidance, not a reviewed permission. Reference-project code was not reused, so no unreviewed external license was incorporated.
