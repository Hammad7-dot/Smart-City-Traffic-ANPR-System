# implements D-024/D-027: 30-day retention for events and generated outputs
"""CLI: preview or delete expired events and generated MP4/CSV outputs.

Usage:
    python -m pipeline.purge --days 30 --dry-run
"""

import argparse
import os
import sqlite3
import stat
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _cutoff(days: int) -> datetime:
    if days < 0:
        raise ValueError("Retention days must be non-negative")
    return datetime.now() - timedelta(days=days)


def _is_link(path: Path) -> bool:
    """Includes Windows junctions/reparse points, not just symbolic links."""
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    )


def purge_outputs(days: int = 30, dry_run: bool = True) -> list[Path]:
    """Preview/remove expired generated files only beneath this repo's output/."""
    cutoff = _cutoff(days).timestamp()
    root = REPO_ROOT / "output"
    if not root.exists():
        return []
    if _is_link(root):
        raise ValueError("Refusing retention on a linked output directory")
    root = root.resolve(strict=True)
    affected = []
    for directory, subdirs, names in os.walk(root, followlinks=False):
        parent = Path(directory)
        subdirs[:] = [name for name in subdirs if not _is_link(parent / name)]
        for name in names:
            path = parent / name
            if path.suffix.lower() not in {".mp4", ".csv"}:
                continue
            if _is_link(path) or not path.is_file():
                continue
            # Resolve and verify the exact target immediately before deletion.
            resolved = path.resolve(strict=True)
            if not resolved.is_relative_to(root) or path.stat().st_mtime >= cutoff:
                continue
            if not dry_run:
                path.unlink()
            affected.append(path)
    return sorted(affected)


def purge_database(db_path: Path, days: int = 30, dry_run: bool = True) -> int:
    """Never creates a database/schema; preview uses a read-only connection."""
    cutoff = _cutoff(days).isoformat()
    path = Path(db_path).resolve()
    if not path.exists():
        return 0
    mode = "ro" if dry_run else "rw"
    with closing(sqlite3.connect(f"{path.as_uri()}?mode={mode}", uri=True)) as conn:
        if dry_run:
            return conn.execute(
                "SELECT COUNT(*) FROM vehicle_events WHERE event_timestamp < ?", (cutoff,)
            ).fetchone()[0]
        with conn:
            return conn.execute(
                "DELETE FROM vehicle_events WHERE event_timestamp < ?", (cutoff,)
            ).rowcount


def main():
    parser = argparse.ArgumentParser(description="Purge expired events and generated output MP4/CSV files")
    parser.add_argument("--db", type=Path, default=REPO_ROOT / "database" / "traffic.db")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--dry-run", action="store_true", help="Preview only; do not delete anything")
    parser.add_argument("--database-only", action="store_true", help="Leave generated files untouched")
    args = parser.parse_args()
    if args.days < 0:
        parser.error("--days must be non-negative")
    deleted = purge_database(args.db, args.days, args.dry_run)
    paths = [] if args.database_only else purge_outputs(args.days, args.dry_run)
    action = "Would purge" if args.dry_run else "Purged"
    print(f"{action} {deleted} event row(s) and {len(paths)} generated file(s) older than {args.days} days")
    for path in paths:
        print(path)


if __name__ == "__main__":
    main()
