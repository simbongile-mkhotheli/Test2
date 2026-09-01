"""
models.py

Application models used throughout the tracker.
"""

from dataclasses import dataclass


# ---------------------------------------------------------
# Snapshot
# ---------------------------------------------------------


@dataclass(slots=True)
class Snapshot:
    """
    Represents the current state of the game.
    """

    draw_id: str
    latest: int
    history: list[int]
