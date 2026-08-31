"""
tracker.py

Coordinates the application.

Responsibilities

- Find the Wheel Of Fortune frame
- Read game state
- Detect new results
- Send results to SessionManager
- Recover if the page reloads
"""

from threading import Event
from traceback import format_exc

from exceptions import RecoverableError, TrackerStopped
from storage.storage import Storage
from tracker.frame_finder import FrameFinder
from tracker.game_reader import GameReader
from utils.logger import Logger
from tracker.session_manager import SessionManager
from ui.events import EventBus


class Tracker:

    def __init__(
        self,
        page,
        events: EventBus | None = None,
        stop_event: Event | None = None,
    ):

        self.page = page
        self.events = events
        self.stop_event = stop_event or Event()
        self.frame = None
        self.reader = None
        self.session = SessionManager(events)
        self.live_results = Storage()
        self.last_round = self.session.last_draw_id()
        self.last_history = self.session.last_history()

    # --------------------------------------------------

    def connect(self):

        finder = FrameFinder(self.page)
        self.frame = finder.find(should_stop=self.stop_event.is_set)
        self.reader = GameReader(self.frame)

        Logger.success("Connected")
        self._publish("connected")

    # --------------------------------------------------

    def reconnect(self):

        delay = 1

        while not self.stop_event.is_set():
            try:
                self.connect()
                return True
            except RecoverableError:
                Logger.warning(f"Reconnect failed. Retry in {delay}s")
                if self.stop_event.wait(delay):
                    break
                delay = min(delay * 2, 30)
        return False

    # --------------------------------------------------

    def _log_result(self, snapshot) -> None:
        Logger.new_result(snapshot.draw_id, snapshot.latest)

    # --------------------------------------------------

    def _record_live_result(self, snapshot) -> None:
        """Record every verified draw independently of session boundaries."""
        if self.live_results.append_live_result(snapshot.draw_id, snapshot.latest):
            self._log_result(snapshot)

    # --------------------------------------------------

    def _remember_snapshot(self, snapshot) -> None:
        """Retain a result fingerprint for the next draw verification."""
        self.last_round = snapshot.draw_id
        self.last_history = tuple(snapshot.history)

    # --------------------------------------------------

    def _publish(self, kind: str, **payload: object) -> None:
        if self.events is not None:
            self.events.publish(kind, **payload)

    # --------------------------------------------------

    def run(self):
        self._publish("tracking_started")
        try:
            self.live_results.prepare_live_results_log()
            self.connect()

            while not self.stop_event.is_set():

                # --------------------------------------------------
                # WAITING: application may start at any time. We only begin
                # when the next draw ID ends in 1.
                # --------------------------------------------------

                if not self.session.is_running():
                    try:
                        snapshot = self.session.wait_for_next_session(
                            self.reader,
                            self.last_round,
                            self.last_history,
                            self.stop_event.is_set,
                            self._record_live_result,
                        )

                        self._remember_snapshot(snapshot)
                        self.session.start(snapshot.draw_id)
                        self.session.add_snapshot(snapshot)

                    except RecoverableError as ex:
                        Logger.warning(str(ex))
                        if not self.reconnect():
                            break
                        continue

                # --------------------------------------------------
                # ACTIVE: collect the fixed 10 draw IDs. Browser history verifies
                # that a new result rolled in, but cannot identify older draw IDs.
                # --------------------------------------------------

                while self.session.is_running() and not self.stop_event.is_set():

                    try:
                        snapshot = self.reader.wait_for_new_draw(
                            self.last_round,
                            self.last_history,
                            self.stop_event.is_set,
                        )
                        self._remember_snapshot(snapshot)
                        self._record_live_result(snapshot)

                        update = self.session.add_snapshot(snapshot)

                        if self.session.is_complete():
                            self.session.finish()
                            break

                        if update.unavailable_draw_ids:
                            Logger.warning(
                                "Required draw IDs are no longer available in "
                                "the verified browser history: "
                                + ", ".join(update.unavailable_draw_ids)
                            )
                            self.session.preserve_incomplete(
                                snapshot.draw_id,
                                update.unavailable_draw_ids,
                            )
                            break

                    except RecoverableError as ex:
                        Logger.warning(str(ex))
                        if not self.reconnect():
                            break

        except TrackerStopped:
            Logger.info("Tracking stopped.")
        except KeyboardInterrupt:
            Logger.info("Tracking stopped.")
        except Exception:
            Logger.error("Fatal programming error")
            Logger.error(format_exc())
            raise
        finally:
            self._publish("tracker_stopped")
