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
        self.last_round = ""

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
                delay = min(delay * 2, 50)

    # --------------------------------------------------

    def _log_result(self, snapshot) -> None:
        Logger.new_result(snapshot.draw_id, snapshot.latest)

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
                    )

                    self.last_round = snapshot.draw_id
                    self.session.start(snapshot.draw_id)
                    self.session.add_result(snapshot.draw_id, snapshot.latest)
                    self._log_result(snapshot)

                except RecoverableError as ex:
                    Logger.warning(str(ex))
                    self.reconnect()
                    continue

            # --------------------------------------------------
            # ACTIVE: collect exactly 30 consecutive draws.
            # --------------------------------------------------

            while self.session.is_running():

                try:
                    snapshot = self.reader.wait_for_new_draw(self.last_round)
                    self.last_round = snapshot.draw_id

                    self.session.add_result(
                        snapshot.draw_id,
                        snapshot.latest,
                    )
                    self._log_result(snapshot)

                    # The third ...0 boundary is the 30th draw.
                    if self.session.is_complete():
                        self.session.finish()
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
