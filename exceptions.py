"""
Custom exceptions for the BetGames Tracker.

These exceptions distinguish between recoverable browser
errors and fatal programming errors.
"""

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


class FrameNotFound(RecoverableError):
    """Raised when the Wheel Of Fortune frame cannot be found in time."""


class DOMChanged(RecoverableError):
    """Raised when the game DOM changes during a browser read."""


class SnapshotTimeout(RecoverableError):
    """Raised when a draw snapshot does not stabilize in time."""


class TrackerStopped(TrackerError):
    """Raised internally when the dashboard asks the worker to stop."""
