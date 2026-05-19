"""Checkpointer backend factory (short-term memory, M7).

``make_checkpointer`` returns the langgraph checkpoint saver selected by
``Settings.checkpointer_backend``:

- ``memory`` (default)  -> ``InMemorySaver`` (no persistence, used by every
  test and the prior 58 -> unchanged behavior).
- ``sqlite`` (explicit) -> a process-lifetime ``SqliteSaver`` bound to
  ``settings.travel_agent_sqlite_path``.

Sqlite lifecycle
----------------
``SqliteSaver.from_conn_string`` is a ``@contextmanager`` that wraps the
connection in ``contextlib.closing`` and CLOSES it on ``__exit__``
(verified by reading
``.venv/lib/python3.11/site-packages/langgraph/checkpoint/sqlite/__init__.py``).
Calling ``.__enter__()`` on it would either leak a never-closed CM or close
the connection the moment the CM is GC'd -- unusable across multiple
``.invoke()`` calls. We therefore build the saver directly from a long-lived
``sqlite3.connect(path, check_same_thread=False)`` connection (exactly the
form the SqliteSaver docstring recommends; the saver guards it with an
internal lock). The connection stays open for the process lifetime, which is
what short-term memory across turns requires.

msgpack / strict mode (scope item 9)
------------------------------------
Persisting ``trip_request`` / ``structured_response`` serializes the custom
types ``travel_assistant.models.ComfortLevel`` / ``TripRequest`` /
``TripPlan``. langgraph-checkpoint's default serde only WARNS on these
("Deserializing unregistered type ... add to allowed_msgpack_modules to allow
explicitly") and HARD-BLOCKS them under ``LANGGRAPH_STRICT_MSGPACK=true`` or a
future langgraph. The clean registration API exists:
``JsonPlusSerializer(allowed_msgpack_modules=[...])`` (each entry is a class,
normalized to a ``(module, name)`` key). We wire exactly our three model
classes into the sqlite saver's serde, so the sqlite path is safe even under
strict mode -- WITHOUT enabling strict mode ourselves and WITHOUT silently
swallowing the issue (covered by an explicit strict-mode test).

Version-compat shim
-------------------
The pinned ``langgraph-checkpoint-sqlite==2.0.10`` ``SqliteSaver`` serializes
checkpoint metadata via ``self.jsonplus_serde.dumps()`` / ``.loads()`` (see
its ``put``/``get_tuple``), but ``langgraph-checkpoint==4.1.0``'s
``JsonPlusSerializer`` exposes only ``dumps_typed`` / ``loads_typed`` -- so a
vanilla ``SqliteSaver(conn)`` raises ``AttributeError: 'JsonPlusSerializer'
object has no attribute 'dumps'`` on the first checkpoint write (verified
empirically; reproduces with the default serde and no strict mode -- it is a
pre-existing pin incompatibility, NOT introduced here). ``_MetadataSerde``
below is a minimal adapter exposing ``dumps``/``loads`` on top of
``dumps_typed``/``loads_typed`` (metadata is always a plain JSON-able dict, so
the round-trip is exact). It also carries the same msgpack allowlist.
"""
import sqlite3
from pathlib import Path
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite import SqliteSaver

from travel_assistant.config import Settings
from travel_assistant.models import ComfortLevel, TripPlan, TripRequest

# Custom (non-builtin, non-langchain) types that get persisted in the agent
# state. Everything else langgraph persists (messages, Command, etc.) is
# already in langgraph's built-in SAFE_MSGPACK_TYPES allowlist.
_ALLOWED_MSGPACK_MODULES: list[type] = [ComfortLevel, TripRequest, TripPlan]


class _MetadataSerde:
    """Adapt ``dumps_typed``/``loads_typed`` -> ``dumps``/``loads``.

    Bridges the langgraph-checkpoint-sqlite 2.0.10 <-> langgraph-checkpoint
    4.1.0 metadata-serde API gap (see module docstring). Metadata is always a
    plain JSON-able mapping, and ``dumps_typed`` tags such payloads
    ``"msgpack"``, so a fixed ``"msgpack"`` tag on ``loads`` is exact.
    """

    def __init__(self, inner: JsonPlusSerializer) -> None:
        self._inner = inner

    def dumps(self, obj: Any) -> bytes:
        return self._inner.dumps_typed(obj)[1]

    def loads(self, data: bytes) -> Any:
        return self._inner.loads_typed(("msgpack", data))

    def dumps_typed(self, obj: Any) -> tuple[str, bytes]:
        return self._inner.dumps_typed(obj)

    def loads_typed(self, data: tuple[str, bytes]) -> Any:
        return self._inner.loads_typed(data)


def _make_sqlite_saver(path: str) -> SqliteSaver:
    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    serde = JsonPlusSerializer(allowed_msgpack_modules=_ALLOWED_MSGPACK_MODULES)
    saver = SqliteSaver(conn, serde=serde)
    # Replace SqliteSaver's internal metadata serde (a bare JsonPlusSerializer
    # whose .dumps/.loads do not exist in checkpoint 4.1.0) with the adapter,
    # which also carries the msgpack allowlist.
    saver.jsonplus_serde = _MetadataSerde(  # type: ignore[assignment]
        JsonPlusSerializer(allowed_msgpack_modules=_ALLOWED_MSGPACK_MODULES)
    )
    # Materialize the schema now so the db file exists immediately (and any
    # error surfaces at construction, not on first invoke).
    saver.setup()
    return saver


def make_checkpointer(settings: Settings) -> BaseCheckpointSaver[Any]:
    """Build the short-term-memory checkpoint saver for ``settings``.

    Raises ``ValueError`` (via ``Settings.validated``) for an unknown backend.
    Default backend is ``memory`` -> ``InMemorySaver`` (unchanged behavior).
    """
    settings.validated()
    if settings.checkpointer_backend == "sqlite":
        return _make_sqlite_saver(settings.travel_agent_sqlite_path)
    return InMemorySaver()
