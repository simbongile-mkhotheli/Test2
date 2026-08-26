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

from time import monotonic, sleep

from playwright.sync_api import Error
from playwright.sync_api import TimeoutError

from config import (
    GAME_CONTAINER,
    DRAW_CODE_SELECTOR,
    DRAW_POLL_INTERVAL,
    SNAPSHOT_STABILITY_TIMEOUT,
    SNAPSHOT_STABLE_READS,
    TIMER_SELECTOR,
)

from exceptions import DOMChanged, SnapshotTimeout
from models.models import Snapshot
from models.number_domain import is_valid_number


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
            latest=history[0] if history else -1,
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

        if not all(is_valid_number(number) for number in snap.history):
            return False

        return True

    # -------------------------------------------------
    # DOM Stability
    # -------------------------------------------------

    def stable_snapshot(
        self,
        expected_draw: str,
        previous_history: tuple[int, ...] | None,
    ) -> Snapshot | None:
        """
        Return a verified snapshot for ``expected_draw``.

        The draw ID must match the detected draw, and its result history must
        differ from the previous draw before it can be accepted. Three matching
        reads prevent storing data from an in-progress React update.
        """
        previous_signature = None
        stable_reads = 0
        started_at = monotonic()

        while True:
            if monotonic() - started_at >= SNAPSHOT_STABILITY_TIMEOUT:
                raise SnapshotTimeout(
                    f"Snapshot for draw {expected_draw} did not stabilize within "
                    f"{SNAPSHOT_STABILITY_TIMEOUT:g}s"
                )

            snap = self.snapshot()

            # The observed draw advanced while this snapshot was being read.
            # Let wait_for_new_draw observe the new draw ID and begin again.
            if snap.draw_id != expected_draw:
                return None

            if not self.valid_snapshot(snap):
                sleep(DRAW_POLL_INTERVAL)

                continue

            if (
                previous_history is not None
                and tuple(snap.history) == previous_history
            ):
                sleep(DRAW_POLL_INTERVAL)

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

            if stable_reads >= SNAPSHOT_STABLE_READS - 1:
                return snap

            sleep(DRAW_POLL_INTERVAL)

    # -------------------------------------------------
    # Wait for Next Draw
    # -------------------------------------------------

    def wait_for_new_draw(
        self,
        previous_draw: str,
        previous_history: tuple[int, ...] | None = None,
    ) -> Snapshot:
        """
        Blocks until a new draw appears.

        Returns a verified Snapshot whose result history differs from the
        previous draw when a history fingerprint is available.
        """

        while True:
            try:
                current_draw = self.draw_id()

                if current_draw and current_draw != previous_draw:
                    snapshot = self.stable_snapshot(
                        current_draw,
                        previous_history,
                    )
                    if snapshot is not None:
                        return snapshot

            except (Error, TimeoutError):
                raise DOMChanged()

            sleep(DRAW_POLL_INTERVAL)
