"""Small, opt-in live extraction sample. Writes JSON to stdout, never a database."""

import argparse
import json
import logging
import sys
from typing import Any

from pydantic import ValidationError

from youtube_insight.config import Settings
from youtube_insight.etl.youtube import YouTubeClient, YouTubeError


class SafeJSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        # Allowlist fields; never serialize a record's request, exception or headers.
        output: dict[str, Any] = {
            "event": record.getMessage(),
            "level": record.levelname,
        }
        for field in ("endpoint", "category", "status", "attempt", "delay_seconds"):
            if hasattr(record, field):
                output[field] = getattr(record, field)
        return json.dumps(output)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Extract a bounded public YouTube sample; no database writes."
    )
    parser.add_argument(
        "--channel-id", help="Channel ID; defaults to server YOUTUBE_CHANNEL_ID"
    )
    parser.add_argument(
        "--max-videos",
        type=int,
        default=5,
        help="Playlist entries to inspect (default 5)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Enable real API calls after reviewing current YouTube policies",
    )
    args = parser.parse_args(argv)
    if not args.live:
        parser.error(
            "No calls made. Pass --live only for an intentional API sample "
            "after policy review."
        )
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(SafeJSONFormatter())
    log = logging.getLogger("youtube_insight.etl.youtube")
    previous = (log.level, log.propagate)
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    log.propagate = False
    try:
        settings = Settings()
        channel_id = args.channel_id or settings.youtube_channel_id
        if not channel_id:
            raise ValueError("Provide --channel-id or YOUTUBE_CHANNEL_ID")
        if not 1 <= args.max_videos <= settings.youtube_max_videos:
            raise ValueError("--max-videos must be within YOUTUBE_MAX_VIDEOS")
        with YouTubeClient(settings) as client:
            sample = client.extract_sample(channel_id, max_videos=args.max_videos)
        print(sample.model_dump_json(indent=2))
        return 0
    except ValidationError:
        print(
            "Invalid server environment configuration; check .env.example",
            file=sys.stderr,
        )
        return 2
    except (YouTubeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1
    finally:
        log.removeHandler(handler)
        log.setLevel(previous[0])
        log.propagate = previous[1]
        handler.close()


if __name__ == "__main__":
    raise SystemExit(main())
