"""Export raw structured messages to JSON array."""

import argparse
from db import DiscordDB


def main() -> None:
    parser = argparse.ArgumentParser(description="Export raw messages to JSON")
    parser.add_argument("--db", default="discord_messages.db", help="Path to SQLite database")
    parser.add_argument("--out", default="raw_messages.json", help="Output JSON path")
    parser.add_argument("--channel", type=int, default=None, help="Filter by channel ID")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of messages")
    parser.add_argument("--offset", type=int, default=0, help="Offset for pagination")
    args = parser.parse_args()

    db = DiscordDB(args.db)
    try:
        count = db.export_raw_messages_json(
            output_path=args.out,
            channel_id=args.channel,
            limit=args.limit,
            offset=args.offset,
        )
        print(f"Exported {count} messages to {args.out}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
