"""Thread-safe events shared by the tracker worker and desktop dashboard."""

from dataclasses import dataclass
from queue import Empty, Queue
from typing import Any


@dataclass(frozen=True, slots=True)
class DashboardEvent:
    """One immutable update for the dashboard."""

    kind: str
    payload: dict[str, Any]


class EventBus:
    """Publish worker events without letting worker code touch Tk widgets."""

    def __init__(self) -> None:
        self._events: Queue[DashboardEvent] = Queue()

    def publish(self, kind: str, **payload: Any) -> None:
        """Queue a dashboard event for handling on the Tk main thread."""
        self._events.put(DashboardEvent(kind=kind, payload=payload))

    def drain(self) -> list[DashboardEvent]:
        """Return every event currently waiting without blocking."""
        events: list[DashboardEvent] = []
        while True:
            try:
                events.append(self._events.get_nowait())
            except Empty:
                return events

