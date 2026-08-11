"""Storage is the layer where bugs cost the user their data, so these tests are
mostly about the unhappy paths: absent files, empty files, files someone edited
by hand and broke."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from chatterbuddy.errors import StorageError
from chatterbuddy.services.storage import JsonStore


def test_missing_file_returns_the_default(store: JsonStore) -> None:
    assert store.read([]) == []
    assert not store.path.exists()


def test_empty_file_returns_the_default(store: JsonStore) -> None:
    store.path.write_text("", encoding="utf-8")
    assert store.read([]) == []


def test_whitespace_only_file_returns_the_default(store: JsonStore) -> None:
    store.path.write_text("   \n\t ", encoding="utf-8")
    assert store.read([]) == []


def test_write_then_read_round_trips(store: JsonStore) -> None:
    payload = [{"id": 1, "name": "Jo"}]
    store.write(payload)
    assert store.read([]) == payload


def test_write_creates_missing_parent_directories(tmp_path: Path) -> None:
    store = JsonStore(tmp_path / "deep" / "nested" / "contacts.json")
    store.write([{"id": 1}])
    assert store.read([]) == [{"id": 1}]


def test_write_leaves_no_temporary_files_behind(store: JsonStore) -> None:
    store.write([{"id": 1}])
    leftovers = [p.name for p in store.path.parent.iterdir() if p.name != store.path.name]
    assert leftovers == []


def test_corrupt_json_is_quarantined_not_deleted(store: JsonStore) -> None:
    store.path.write_text('[{"id": 1, "name": ', encoding="utf-8")

    assert store.read([]) == []

    assert store.last_quarantine is not None
    assert store.last_quarantine.exists()
    # The user's broken file is still on disk; only the live path was cleared.
    assert "name" in store.last_quarantine.read_text(encoding="utf-8")
    assert not store.path.exists()


def test_valid_json_of_the_wrong_shape_is_quarantined(store: JsonStore) -> None:
    """A dict where a list belongs parses fine but is still unusable."""
    store.path.write_text(json.dumps({"contacts": []}), encoding="utf-8")
    assert store.read([]) == []
    assert store.last_quarantine is not None


def test_read_survives_a_second_corruption(store: JsonStore) -> None:
    store.path.write_text("not json", encoding="utf-8")
    store.read([])
    store.path.write_text("also not json", encoding="utf-8")
    assert store.read([]) == []


def test_unwritable_path_raises_storage_error(tmp_path: Path) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("i am a file, not a directory", encoding="utf-8")
    store = JsonStore(blocker / "contacts.json")
    with pytest.raises(StorageError):
        store.write([])


def test_stored_json_is_human_readable(store: JsonStore) -> None:
    """Indented output is a deliberate choice: the files are meant to be
    inspectable and diffable, which is a large part of why JSON was picked."""
    store.write([{"id": 1, "name": "Jo"}])
    text = store.path.read_text(encoding="utf-8")
    assert "\n" in text and '  "id": 1' in text
