"""
logger.py

Simple logging utility for the BetGames Tracker.

No external dependencies.
"""

import traceback
from datetime import datetime
from pathlib import Path
from typing import Protocol

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

LOG_FILE = LOG_DIR / "tracker.log"


class EventPublisher(Protocol):
    """Minimal interface used to forward log entries to the dashboard."""

    def publish(self, kind: str, **payload: object) -> None:
        """Publish one UI event."""


class Logger:

    ENABLE_CONSOLE = False
    ENABLE_FILE = False
    EVENT_PUBLISHER: EventPublisher | None = None

    LINE = "=" * 70

    # ---------------------------------------------------------

    @staticmethod
    def _time():

        return datetime.now().strftime("%H:%M:%S")

    # ---------------------------------------------------------

    @staticmethod
    def configure(event_publisher: EventPublisher | None = None) -> None:
        """Send future log entries to the supplied dashboard event publisher."""
        Logger.EVENT_PUBLISHER = event_publisher

    # ---------------------------------------------------------

    @staticmethod
    def _write(level, message):

        text = f"[{Logger._time()}] [{level}] {message}"

        if Logger.EVENT_PUBLISHER is not None:
            Logger.EVENT_PUBLISHER.publish(
                "log",
                timestamp=Logger._time(),
                level=level,
                message=str(message),
            )

        if Logger.ENABLE_CONSOLE:
            print(text)

        if Logger.ENABLE_FILE:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(text + "\n")

    # ---------------------------------------------------------

    @staticmethod
    def info(message):

        Logger._write("INFO", message)

    # ---------------------------------------------------------

    @staticmethod
    def success(message):

        Logger._write("SUCCESS", message)

    # ---------------------------------------------------------

    @staticmethod
    def warning(message):

        Logger._write("WARNING", message)

    # ---------------------------------------------------------

    @staticmethod
    def error(message):

        Logger._write("ERROR", message)

    # ---------------------------------------------------------

    @staticmethod
    def debug(message):

        Logger._write("DEBUG", message)

    # ---------------------------------------------------------

    @staticmethod
    def exception(ex):

        Logger._write("EXCEPTION", str(ex))

    # ---------------------------------------------------------

    @staticmethod
    def fatal(ex):

        Logger.error(type(ex).__name__)

        Logger.error(str(ex))

        Logger.error(traceback.format_exc())

    # ---------------------------------------------------------

    @staticmethod
    def separator():

        Logger.info(Logger.LINE)

    # ---------------------------------------------------------

    @staticmethod
    def banner(title):

        Logger.info(title)

    # ---------------------------------------------------------

    @staticmethod
    def session_started(name):

        Logger.banner(f"Started Session : {name}")

    # ---------------------------------------------------------

    @staticmethod
    def session_finished(name, total):

        Logger.banner(
            f"Finished Session : {name} | Results : {total}"
        )

    # ---------------------------------------------------------

    @staticmethod
    def new_result(draw_id, result):

        Logger.success(
            f"NEW RESULT -> {draw_id} : {result}"
        )

    # ---------------------------------------------------------

    @staticmethod
    def reconnect():

        Logger.warning("Connection lost. Reconnecting...")

    # ---------------------------------------------------------

    @staticmethod
    def connected():

        Logger.success("Connected to Wheel Of Fortune")

    # ---------------------------------------------------------

    @staticmethod
    def waiting():

        Logger.info("Waiting for next session...")

    # ---------------------------------------------------------

    @staticmethod
    def searching():

        Logger.info("Searching for Wheel Of Fortune...")

    # ---------------------------------------------------------

    @staticmethod
    def live_status(draw, timer, latest):

        Logger.info(f"Round: {draw} | Timer: {timer:02d} | Latest: {latest}")

    # ---------------------------------------------------------

    @staticmethod
    def session_summary(results):

        for draw, result in results:
            Logger.info(f"{draw},{result}")

    # ---------------------------------------------------------

    @staticmethod
    def saved(path):

        Logger.success(f"Saved -> {path}")

    # ---------------------------------------------------------

    @staticmethod
    def startup():

        Logger.banner("BetGames Tracker Started")

    # ---------------------------------------------------------

    @staticmethod
    def shutdown():

        Logger.banner("Tracker Stopped")

    # ---------------------------------------------------------

    @staticmethod
    def blank():

        return None
