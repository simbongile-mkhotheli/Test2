"""
Application configuration.

Keeping all constants here makes the rest of the project
easy to maintain.
"""

from pathlib import Path


# -----------------------------------------------------
# Website
# -----------------------------------------------------

BETGAMES_URL = "https://demo.betgames.tv"


# -----------------------------------------------------
# Playwright
# -----------------------------------------------------

HEADLESS = False

VIEWPORT_WIDTH = 1500
VIEWPORT_HEIGHT = 900


# -----------------------------------------------------
# Polling
# -----------------------------------------------------

# Wait while looking for iframe
FRAME_SEARCH_INTERVAL = 1.00

# Poll interval while waiting for a draw or DOM stabilization.
DRAW_POLL_INTERVAL = 0.05

# A draw must produce three matching DOM snapshots within this period.
SNAPSHOT_STABILITY_TIMEOUT = 10.0
SNAPSHOT_STABLE_READS = 3


# -----------------------------------------------------
# Selectors
# -----------------------------------------------------

GAME_CONTAINER = "section.game-content"

DRAW_CODE_SELECTOR = '[data-qa="text-game-draw-code"]'

TIMER_SELECTOR = '[data-qa="text-time-string"]'

RESULTS_SELECTOR = '[data-qa="last-results-compact"]'


# -----------------------------------------------------
# Files
# -----------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

SESSIONS_DIR = BASE_DIR / "sessions"

SESSIONS_DIR.mkdir(exist_ok=True)

# Live, consolidated draw log. Detailed session reports remain in SESSIONS_DIR.
RESULTS_FILE = BASE_DIR / "results.txt"

# Atomic checkpoint for a session that has started but is not yet finalized.
ACTIVE_SESSION_FILE = SESSIONS_DIR / ".active-session.json"

# Sessions that cannot be completed because required draw IDs were missed are
# kept here for review. The browser's compact history has no draw IDs, so it
# cannot safely reconstruct them after an interruption.
INCOMPLETE_SESSIONS_DIR = SESSIONS_DIR / "incomplete"

# -----------------------------------------------------
# Session boundaries
# -----------------------------------------------------

# Sessions are defined by draw IDs, not wall-clock time. A session begins on an
# ID ending in 1 and ends at the 30th consecutive draw ID.
SESSION_DRAW_COUNT = 30


# -----------------------------------------------------
# Logging
# -----------------------------------------------------

SHOW_RECONNECTS = True


# -----------------------------------------------------
# Console formatting
# -----------------------------------------------------

LINE = "=" * 70
