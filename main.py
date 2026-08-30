"""Launch the browser tracker and its desktop dashboard."""

from threading import Event, Thread
from traceback import format_exc

from playwright.sync_api import sync_playwright

from config import BETGAMES_URL, HEADLESS, VIEWPORT_HEIGHT, VIEWPORT_WIDTH
from tracker.tracker import Tracker
from ui.dashboard import Dashboard
from ui.events import EventBus
from utils.logger import Logger


def _wait_for_start(start_event: Event, stop_event: Event) -> bool:
    """Wait for the dashboard's Start button without blocking shutdown."""
    while not start_event.wait(timeout=0.1):
        if stop_event.is_set():
            return False
    return not stop_event.is_set()


def _run_tracker_worker(
    events: EventBus,
    stop_event: Event,
    start_event: Event,
) -> None:
    """Run every synchronous Playwright operation on one background thread."""
    Logger.configure(events)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=HEADLESS)
            try:
                context = browser.new_context(
                    viewport={
                        "width": VIEWPORT_WIDTH,
                        "height": VIEWPORT_HEIGHT,
                    }
                )
                page = context.new_page()
                page.goto(BETGAMES_URL, wait_until="domcontentloaded")
                events.publish("browser_ready")

                if not _wait_for_start(start_event, stop_event):
                    return

                Tracker(page, events, stop_event).run()
            finally:
                browser.close()
    except Exception:
        events.publish("worker_error", message=format_exc())
    finally:
        events.publish("worker_stopped")
        Logger.configure()


def main() -> None:
    """Create the dashboard on the main thread and tracker on a worker thread."""
    events = EventBus()
    stop_event = Event()
    start_event = Event()
    dashboard = Dashboard(events, stop_event, start_event)
    worker = Thread(
        target=_run_tracker_worker,
        args=(events, stop_event, start_event),
        name="betgames-tracker",
    )
    worker.start()

    try:
        dashboard.run()
    finally:
        stop_event.set()
        start_event.set()
        worker.join(timeout=10)


if __name__ == "__main__":
    main()
