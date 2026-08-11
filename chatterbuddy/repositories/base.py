"""Generic collection-backed-by-a-file behaviour, written once."""

from __future__ import annotations

import threading
from typing import Any, Generic, Protocol, TypeVar, runtime_checkable

from ..errors import NotFoundError
from ..services.storage import JsonStore


@runtime_checkable
class Persistable(Protocol):
    """What the repository needs from a model: an id and JSON conversion."""

    id: int

    def to_dict(self) -> dict[str, Any]: ...


T = TypeVar("T", bound=Persistable)


class JsonRepository(Generic[T]):
    """A list of records loaded from a JSON file, with an id index over it.

    Two data structures are held deliberately: a ``list`` because creation order
    is what the user sees when listing records, and a ``dict`` keyed by id so
    that ``complete task 47`` is a hash lookup rather than a linear scan.
    """

    entity_name = "record"

    def __init__(self, store: JsonStore, model_cls: type[T]) -> None:
        self._store = store
        self._model_cls = model_cls
        self._items: list[T] = []
        self._index: dict[int, T] = {}
        self._next_id = 1
        self._loaded = False
        self.discarded = 0
        # Re-entrant because public methods that take the lock (``add``) call
        # other public methods that take it (``save``). The alarm scheduler
        # thread and the main thread both reach this object.
        self._lock = threading.RLock()

    @property
    def store(self) -> JsonStore:
        return self._store

    def load(self) -> None:
        """Read the file into memory, skipping individual unusable records.

        One malformed record should cost the user that record, not the whole
        file, so failures are counted and reported rather than raised.
        """
        with self._lock:
            raw_records = self._store.read([])
            items: list[T] = []
            discarded = 0
            for raw in raw_records:
                if not isinstance(raw, dict):
                    discarded += 1
                    continue
                try:
                    items.append(self._model_cls.from_dict(raw))
                except Exception:
                    discarded += 1
            self._items = items
            self._index = {item.id: item for item in items}
            self._next_id = max(self._index, default=0) + 1
            self.discarded = discarded
            self._loaded = True

    def all(self) -> list[T]:
        """Every record, in creation order. Returns a copy so callers cannot
        mutate the repository's internal list by accident."""
        with self._lock:
            self._ensure_loaded()
            return list(self._items)

    def get(self, record_id: int) -> T:
        with self._lock:
            self._ensure_loaded()
            try:
                return self._index[record_id]
            except KeyError:
                raise NotFoundError(
                    f"There is no {self.entity_name} with id {record_id}."
                ) from None

    def add(self, item: T) -> T:
        with self._lock:
            self._ensure_loaded()
            self._items.append(item)
            self._index[item.id] = item
            self._next_id = max(self._next_id, item.id + 1)
            self.save()
            return item

    def remove(self, record_id: int) -> T:
        with self._lock:
            item = self.get(record_id)
            self._items.remove(item)
            del self._index[record_id]
            self.save()
            return item

    def save(self) -> None:
        with self._lock:
            self._store.write([item.to_dict() for item in self._items])

    def next_id(self) -> int:
        with self._lock:
            self._ensure_loaded()
            return self._next_id

    def __len__(self) -> int:
        return len(self.all())

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self.load()
