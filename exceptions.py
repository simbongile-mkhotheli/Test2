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