"""Forward tracker activity to the desktop dashboard."""

from datetime import datetime
from typing import Protocol


class EventPublisher(Protocol):
    """Minimal interface used to forward log entries to the dashboard."""

    def publish(self, kind: str, **payload: object) -> None:
        """Publish one UI event."""


class Logger:
    EVENT_PUBLISHER: EventPublisher | None = None

    @staticmethod
    def configure(event_publisher: EventPublisher | None = None) -> None:
        """Send future log entries to the supplied dashboard event publisher."""
        Logger.EVENT_PUBLISHER = event_publisher

    @staticmethod
    def _write(level: str, message: object) -> None:
        if Logger.EVENT_PUBLISHER is not None:
            Logger.EVENT_PUBLISHER.publish(
                "log",
                timestamp=datetime.now().strftime("%H:%M:%S"),
                level=level,
                message=str(message),
            )

    @staticmethod
    def info(message: object) -> None:
        Logger._write("INFO", message)

    @staticmethod
    def success(message: object) -> None:
        Logger._write("SUCCESS", message)

    @staticmethod
    def warning(message: object) -> None:
        Logger._write("WARNING", message)

    @staticmethod
    def error(message: object) -> None:
        Logger._write("ERROR", message)

    @staticmethod
    def new_result(draw_id: str, result: int) -> None:
        Logger.success(
            f"NEW RESULT -> {draw_id} : {result}"
        )
