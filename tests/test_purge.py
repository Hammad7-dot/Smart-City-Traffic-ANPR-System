"""D-024/D-027: retention previews and deletion never touch source footage."""

import os
import sqlite3
from datetime import datetime, timedelta

import pytest

from pipeline import purge
from pipeline.storage import EventStore


@pytest.fixture
def retention_files(tmp_path, monkeypatch):
    monkeypatch.setattr(purge, "REPO_ROOT", tmp_path, raising=False)
    old = (datetime.now() - timedelta(days=40)).timestamp()
    files = {}
    for name in ("output/old.mp4", "output/nested/old.csv", "output/recent.mp4",
                 "output/keep.txt", "data/source.mp4"):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"synthetic fixture")
        if name != "output/recent.mp4":
            os.utime(path, (old, old))
        files[name] = path
    return files


def test_output_dry_run_lists_only_expired_generated_files(retention_files):
    paths = purge.purge_outputs(days=30, dry_run=True)
    assert set(paths) == {retention_files["output/old.mp4"], retention_files["output/nested/old.csv"]}
    assert all(path.exists() for path in retention_files.values())


def test_output_purge_preserves_sources_recent_and_other_files(retention_files):
    paths = purge.purge_outputs(days=30, dry_run=False)
    assert len(paths) == 2
    assert all(not path.exists() for path in paths)
    assert retention_files["data/source.mp4"].exists()
    assert retention_files["output/recent.mp4"].exists()
    assert retention_files["output/keep.txt"].exists()


def test_negative_retention_does_not_delete_files(retention_files):
    with pytest.raises(ValueError):
        purge.purge_outputs(days=-1, dry_run=False)
    assert all(path.exists() for path in retention_files.values())


def test_output_purge_does_not_follow_symlink(retention_files):
    link = retention_files["output/old.mp4"].parent / "linked"
    try:
        link.symlink_to(retention_files["data/source.mp4"].parent, target_is_directory=True)
    except OSError:
        pytest.skip("Creating symlinks requires OS permission")
    purge.purge_outputs(days=30, dry_run=False)
    assert retention_files["data/source.mp4"].exists()


def test_database_preview_is_read_only(tmp_path):
    db = tmp_path / "traffic.db"
    store = EventStore(str(db))
    store.record_event(1, "car", None, 0.0, True, 0,
                       (datetime.now() - timedelta(days=40)).isoformat())
    store.close()
    assert purge.purge_database(db, days=30, dry_run=True) == 1
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM vehicle_events").fetchone()[0] == 1
    assert purge.purge_database(db, days=30, dry_run=False) == 1


def test_missing_database_is_not_created(tmp_path):
    db = tmp_path / "missing.db"
    assert purge.purge_database(db, days=30, dry_run=True) == 0
    assert not db.exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows junction test")
def test_output_purge_does_not_follow_windows_junction(retention_files):
    import _winapi

    link = retention_files["output/old.mp4"].parent / "junction"
    _winapi.CreateJunction(str(retention_files["data/source.mp4"].parent), str(link))
    try:
        assert purge._is_link(link)
        purge.purge_outputs(days=30, dry_run=False)
        assert retention_files["data/source.mp4"].exists()
    finally:
        link.rmdir()
