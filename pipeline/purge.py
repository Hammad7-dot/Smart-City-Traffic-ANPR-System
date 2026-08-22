# implements D-024 (resolves B-003): 30-day retention purge for vehicle_events
"""CLI: delete vehicle_events rows older than N days.

Usage:
    python -m pipeline.purge --db database/traffic.db --days 30
"""

import argparse

from pipeline.storage import EventStore


def main():
    parser = argparse.ArgumentParser(description="Purge vehicle_events rows older than --days (D-024)")
    parser.add_argument("--db", default="database/traffic.db")
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args()

    store = EventStore(args.db)
    deleted = store.purge_older_than(args.days)
    store.close()
    print(f"Purged {deleted} row(s) older than {args.days} days from {args.db}")


if __name__ == "__main__":
    main()
