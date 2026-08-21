"""
frame_finder.py

Responsible for locating the iframe that contains
the active Wheel of Fortune game.
"""

from time import monotonic
from time import sleep

from playwright.sync_api import Error as PlaywrightError

from exceptions import FrameNotFound

from config import (
    GAME_CONTAINER,
    DRAW_CODE_SELECTOR,
    RESULTS_SELECTOR,
    FRAME_SEARCH_INTERVAL,
    SHOW_RECONNECTS,
)


class FrameFinder:

    def __init__(self, page):
        self.page = page

    def find(self, timeout=30):
        """
        Search every Playwright frame until we find
        the one containing the game.

        Returns
        -------
        Frame
        """

        if SHOW_RECONNECTS:
            print("Searching for Wheel Of Fortune...")

        start = monotonic()

        while True:

            for frame in self.page.frames:

                try:

                    game = frame.locator(GAME_CONTAINER)

                    if game.count() == 0:
                        continue

                    draw = game.locator(
                        DRAW_CODE_SELECTOR
                    )

                    history = game.locator(
                        RESULTS_SELECTOR
                    )

                    if (
                        draw.count() == 1
                        and history.count() == 1
                    ):

                        if SHOW_RECONNECTS:
                            print("✓ Wheel Of Fortune found")

                        return frame

                except PlaywrightError:
                    continue

            if monotonic() - start > timeout:
                raise FrameNotFound(
                    "Wheel Of Fortune iframe not found."
                )

            sleep(FRAME_SEARCH_INTERVAL)