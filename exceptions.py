"""
Custom exceptions for the BetGames Tracker.

These exceptions distinguish between recoverable browser
errors and fatal programming errors.
"""

from playwright.sync_api import Error as PlaywrightError


class TrackerError(Exception):
    """Base application exception."""


# ----------------------------------------------------
# Recoverable
# ----------------------------------------------------

class RecoverableError(TrackerError):
    """
    Base class for recoverable runtime problems.

    These should trigger a reconnect.
    """


class BrowserDisconnected(RecoverableError):
    pass


class FrameNotFound(RecoverableError):
    pass


class FrameLost(RecoverableError):
    pass


class DOMChanged(RecoverableError):
    pass


class SnapshotTimeout(RecoverableError):
    pass


class GameNotLoaded(RecoverableError):
    pass


class SessionGap(TrackerError):
    """Captured draw IDs skipped ahead, so the active session is incomplete."""

    def __init__(self, expected_draw_id: str, observed_draw_id: str):
        self.expected_draw_id = expected_draw_id
        self.observed_draw_id = observed_draw_id
        super().__init__(
            "Session draw IDs must be consecutive: "
            f"expected {expected_draw_id}, got {observed_draw_id}"
        )


# ----------------------------------------------------
# Fatal
# ----------------------------------------------------

class FatalTrackerError(TrackerError):
    """
    Programming bugs.

    Never reconnect.
    """


class InvalidSnapshot(FatalTrackerError):
    pass


class InvalidHistory(FatalTrackerError):
    pass


# ----------------------------------------------------
# Helpers
# ----------------------------------------------------

RECOVERABLE_PLAYWRIGHT = (
    PlaywrightError,
)

RECOVERABLE_TRACKER = (
    RecoverableError,
)
