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

from time import sleep
from traceback import format_exc

from exceptions import RecoverableError
from tracker.frame_finder import FrameFinder
from tracker.game_reader import GameReader
from utils.logger import Logger
from tracker.session_manager import SessionManager


class Tracker:

    def __init__(self, page):

        self.page = page
        self.frame = None
        self.reader = None
        self.session = SessionManager()
        self.last_round = self.session.last_draw_id()
        self.last_history = self.session.last_history()

    # --------------------------------------------------

    def connect(self):

        finder = FrameFinder(self.page)
        self.frame = finder.find()
        self.reader = GameReader(self.frame)

        Logger.success("Connected")

    # --------------------------------------------------

    def reconnect(self):

        delay = 1

        while True:
            try:
                self.connect()
                return
            except RecoverableError:
                Logger.warning(f"Reconnect failed. Retry in {delay}s")
                sleep(delay)
                delay = min(delay * 2, 30)

    # --------------------------------------------------

    def _log_result(self, snapshot) -> None:
        Logger.new_result(snapshot.draw_id, snapshot.latest)

    # --------------------------------------------------

    def _remember_snapshot(self, snapshot) -> None:
        """Retain a result fingerprint for the next draw verification."""
        self.last_round = snapshot.draw_id
        self.last_history = tuple(snapshot.history)

    # --------------------------------------------------

    def run(self):

        self.connect()

        while True:

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
                    )

                    self._remember_snapshot(snapshot)
                    self.session.start(snapshot.draw_id)
                    update = self.session.add_snapshot(snapshot)
                    if update.captured_current_draw:
                        self._log_result(snapshot)

                except RecoverableError as ex:
                    Logger.warning(str(ex))
                    self.reconnect()
                    continue

            # --------------------------------------------------
            # ACTIVE: collect the fixed 30 draw IDs. Browser history verifies
            # that a new result rolled in, but cannot identify older draw IDs.
            # --------------------------------------------------

            while self.session.is_running():

                try:
                    snapshot = self.reader.wait_for_new_draw(
                        self.last_round,
                        self.last_history,
                    )
                    self._remember_snapshot(snapshot)

                    update = self.session.add_snapshot(snapshot)
                    if update.captured_current_draw:
                        self._log_result(snapshot)

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
                    self.reconnect()

                except KeyboardInterrupt:
                    print("\nStopping tracker...")
                    return

                except Exception:
                    Logger.error("Fatal programming error")
                    Logger.error(format_exc())
                    raise
