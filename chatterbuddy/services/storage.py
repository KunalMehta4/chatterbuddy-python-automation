"""The only class in the project that touches the filesystem.

Centralising file access means the awkward cases -- a missing file, an empty
file, hand-edited JSON that no longer parses, a crash halfway through a write --
are handled once, correctly, instead of three times, differently.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any

from ..errors import StorageError
from ..utils import now


class JsonStore:
    """Reads and writes one JSON file, and refuses to lose data doing it."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.last_quarantine: Path | None = None
        self._lock = threading.Lock()

    def read(self, default: Any) -> Any:
        """Return the file's contents, or ``default`` if it is unusable.

        Anything unreadable is moved aside rather than overwritten. A user who
        hand-edited their tasks and broke the syntax gets a clean start *and*
        keeps the file they broke.
        """
        with self._lock:
            if not self.path.exists():
                return default
            try:
                raw = self.path.read_text(encoding="utf-8")
            except OSError as exc:
                raise StorageError(f"Could not read {self.path}: {exc}") from exc

            if not raw.strip():
                return default

            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                self._quarantine()
                return default

            # A syntactically valid file of the wrong shape is just as unusable.
            if not isinstance(payload, type(default)):
                self._quarantine()
                return default

            return payload

    def write(self, data: Any) -> None:
        """Write atomically: full write to a sibling temp file, then rename.

        ``os.replace`` is atomic on POSIX and Windows, so a crash mid-write
        leaves the previous good file untouched instead of a truncated one.
        """
        with self._lock:
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                descriptor, temp_name = tempfile.mkstemp(
                    dir=self.path.parent, prefix=f".{self.path.name}.", suffix=".tmp"
                )
                try:
                    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                        json.dump(data, handle, indent=2, ensure_ascii=False)
                        handle.write("\n")
                        handle.flush()
                        os.fsync(handle.fileno())
                    os.replace(temp_name, self.path)
                except BaseException:
                    # Never leave a half-written temp file lying next to real data.
                    Path(temp_name).unlink(missing_ok=True)
                    raise
            except OSError as exc:
                raise StorageError(f"Could not write {self.path}: {exc}") from exc

    def _quarantine(self) -> None:
        target = self.path.with_name(f"{self.path.name}.corrupt-{now().strftime('%Y%m%d-%H%M%S')}")
        try:
            self.path.replace(target)
        except OSError as exc:
            raise StorageError(
                f"{self.path} is unreadable and could not be moved aside: {exc}"
            ) from exc
        self.last_quarantine = target
