"""
models.py

Application models used throughout the tracker.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List


# ---------------------------------------------------------
# Snapshot
# ---------------------------------------------------------


@dataclass(slots=True)
class Snapshot:
    """
    Represents the current state of the game.
    """

    draw_id: str
    timer: int
    latest: int
    history: List[int]

    @property
    def history_count(self) -> int:
        return len(self.history)

    def __str__(self) -> str:
        return (
            f"Snapshot(draw={self.draw_id}, timer={self.timer}, latest={self.latest})"
        )


# ---------------------------------------------------------
# Result
# ---------------------------------------------------------


@dataclass(slots=True)
class Result:
    """
    Represents one completed draw.
    """

    draw_id: str
    number: int
    captured_at: datetime = field(default_factory=datetime.now)

    def csv(self) -> str:
        return f"{self.draw_id},{self.number}"

    def __str__(self):
        return self.csv()


# ---------------------------------------------------------
# Session
# ---------------------------------------------------------


@dataclass(slots=True)
class Session:
    """
    Represents one 30-minute tracking session.
    """

    name: str

    started_at: datetime

    results: List[Result] = field(default_factory=list)

    def add(self, draw_id: str, number: int):

        self.results.append(
            Result(
                draw_id=draw_id,
                number=number,
            )
        )

    @property
    def total_results(self):

        return len(self.results)

    @property
    def numbers(self):

        return [r.number for r in self.results]

    @property
    def draw_ids(self):

        return [r.draw_id for r in self.results]

    def clear(self):

        self.results.clear()

    def to_csv(self):

        return "\n".join(r.csv() for r in self.results)

    def __len__(self):

        return len(self.results)

    def __iter__(self):

        return iter(self.results)


# ---------------------------------------------------------
# Tracker State
# ---------------------------------------------------------

# Removed: TrackerState was unused and not part of the active runtime path.
