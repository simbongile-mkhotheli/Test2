"""
game_reader.py

Reads the current Wheel Of Fortune state.

Strategy
--------

1. Wait for the draw id to change.
2. Wait until the DOM becomes stable.
3. Return one verified snapshot.

This avoids race conditions while the UI is still updating.
"""

from time import sleep

from playwright.sync_api import Error
from playwright.sync_api import TimeoutError

from config import (
    GAME_CONTAINER,
    DRAW_CODE_SELECTOR,
    TIMER_SELECTOR,
)

from exceptions import DOMChanged
from models.models import Snapshot


class GameReader:
    def __init__(self, frame):

        self.game = frame.locator(GAME_CONTAINER)

    # -------------------------------------------------
    # Individual Readers
    # -------------------------------------------------

    def draw_id(self):

        return (
            self.game.locator(DRAW_CODE_SELECTOR).inner_text().replace("#", "").strip()
        )

    # -------------------------------------------------

    def timer(self) -> int:
        """
        Read the countdown timer.

        During React updates the timer can briefly be blank.
        That is a recoverable browser state.
        """

        text = self.game.locator(TIMER_SELECTOR).inner_text().strip()

        if not text:
            return -1

        if not text.isdigit():
            return -1

        return int(text)

    # -------------------------------------------------

    def history(self):

        container = self.game.locator('[data-qa="last-results-compact"]')

        items = container.locator('[data-qa^="area-game-item-"]')

        history = []

        for i in range(items.count()):
            qa = items.nth(i).get_attribute("data-qa")

            if qa:
                history.append(int(qa.split("-")[-1]))

        return history

    # -------------------------------------------------
    # Snapshot
    # -------------------------------------------------

    def snapshot(self):

        history = self.history()

        return Snapshot(
            draw_id=self.draw_id(),
            timer=self.timer(),
            latest=history[0],
            history=history,
        )

    # -------------------------------------------------
    # Validation
    # -------------------------------------------------

    def valid_snapshot(self, snap: Snapshot):

        if not snap.draw_id.isdigit():
            return False

        if len(snap.history) < 10:
            return False

        if snap.latest not in range(19):
            return False

        return True

    # -------------------------------------------------
    # DOM Stability
    # -------------------------------------------------

    def stable_snapshot(self):
        """
        Wait until three consecutive reads are identical.

        This guarantees React has finished updating.
        """

        previous_signature = None

        stable_reads = 0

        while True:
            snap = self.snapshot()

            if not self.valid_snapshot(snap):
                sleep(0.05)

                continue

            signature = (
                snap.draw_id,
                tuple(snap.history),
            )

            if signature == previous_signature:
                stable_reads += 1

            else:
                previous_signature = signature

                stable_reads = 0

            if stable_reads >= 2:
                return snap

            sleep(0.05)

    # -------------------------------------------------
    # Wait for Next Draw
    # -------------------------------------------------

    def wait_for_new_draw(self, previous_draw):
        """
        Blocks until a new draw appears.

        Returns a verified Snapshot.
        """

        while True:
            try:
                current_draw = self.draw_id()

                if current_draw and current_draw != previous_draw:
                    return self.stable_snapshot()

            except (Error, TimeoutError):
                raise DOMChanged()

            sleep(0.05)
