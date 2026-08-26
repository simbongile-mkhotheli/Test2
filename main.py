"""
main.py

Entry point for the BetGames tracker.
"""

from playwright.sync_api import sync_playwright

from config import (
    BETGAMES_URL,
    HEADLESS,
    VIEWPORT_WIDTH,
    VIEWPORT_HEIGHT,
)

from tracker.tracker import Tracker


def main():

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=HEADLESS
        )

        context = browser.new_context(
            viewport={
                "width": VIEWPORT_WIDTH,
                "height": VIEWPORT_HEIGHT,
            }
        )

        page = context.new_page()

        print("=" * 60)
        print("Opening BetGames...")
        print("=" * 60)

        page.goto(
            BETGAMES_URL,
            wait_until="domcontentloaded"
        )

        print()
        print("=" * 60)
        print("Open Wheel Of Fortune manually.")
        print("Once the game is visible press ENTER.")
        print("=" * 60)

        input()

        tracker = Tracker(page)

        tracker.run()

        browser.close()


if __name__ == "__main__":
    main()