"""Draw-ID-based 30-draw session manager.

A session always starts on a draw ID ending in ``1`` and contains exactly
30 consecutive draws, ending on an ID whose final digit is ``0``.
"""

from time import sleep

from analytics.analyzers.gaps import GapAnalyzer
from analytics.reports.session import SessionReport
from analytics.statistics import Statistics
from config import LINE, SESSION_DRAW_COUNT
from models.number_domain import NUMBER_BANDS, number_band, validate_number
from storage.storage import Storage


class SessionManager:
    """Own the session state machine and persist captured draws."""

    def __init__(self):
        self.storage = Storage()
        self.session_name = ""
        self.results: list[tuple[str, int]] = []
        self.running = False
        self.start_draw_id: str | None = None
        self.statistics = Statistics()
        self._range_trend_history: list[tuple[int, int, int]] = []

    # --------------------------------------------------
    # Session boundary helpers
    # --------------------------------------------------

    @staticmethod
    def draw_position(draw_id: str) -> int:
        """Return the final digit of a numeric draw ID."""
        if not draw_id or not draw_id.isdigit():
            raise ValueError(f"Invalid draw ID: {draw_id!r}")
        return int(draw_id[-1])

    @classmethod
    def is_session_start_draw(cls, draw_id: str) -> bool:
        """A session starts only on an ID ending in 1."""
        return cls.draw_position(draw_id) == 1

    @classmethod
    def is_session_end_draw(cls, draw_id: str) -> bool:
        """A complete session ends on an ID ending in 0."""
        return cls.draw_position(draw_id) == 0

    def is_complete(self) -> bool:
        """Return True only after exactly 30 consecutive draws are captured."""
        return (
            self.running
            and len(self.results) == SESSION_DRAW_COUNT
            and bool(self.results)
            and self.is_session_end_draw(self.results[-1][0])
        )

    # --------------------------------------------------

    def wait_for_next_session(
        self,
        reader,
        previous_draw: str = "",
        previous_history: tuple[int, ...] | None = None,
    ):
        """Wait until the next observed draw ID ending in 1."""
        print()
        print(LINE)
        print("Waiting for next session start (draw ID ending in 1)...")
        print(LINE)

        last_draw = previous_draw
        last_history = previous_history
        while True:
            snapshot = reader.wait_for_new_draw(last_draw, last_history)
            last_draw = snapshot.draw_id
            last_history = tuple(snapshot.history)

            print(
                f"\rWaiting... draw {snapshot.draw_id} "
                f"(position {self.draw_position(snapshot.draw_id)})",
                end="",
            )

            if self.is_session_start_draw(snapshot.draw_id):
                print()
                return snapshot

            sleep(0.01)

    # --------------------------------------------------

    def start(self, start_draw_id: str):
        """Start a fresh 30-draw session at an ID ending in 1."""
        if not self.is_session_start_draw(start_draw_id):
            raise ValueError(
                f"Session must start on a draw ID ending in 1: {start_draw_id}"
            )

        self.session_name = f"draw-{start_draw_id}"
        self.start_draw_id = start_draw_id
        self.results = []
        self._range_trend_history = []
        self.running = True

        end_draw_id = str(int(start_draw_id) + SESSION_DRAW_COUNT - 1)

        print()
        print(LINE)
        print(f"Started session at draw {start_draw_id}")
        print(f"Session length  : {SESSION_DRAW_COUNT} draws")
        print(f"Ends at draw    : {end_draw_id}")
        print(LINE)

    # --------------------------------------------------

    def add_result(self, draw_id: str, result: int):
        """Record one draw and reject duplicates or gaps."""
        if not self.running:
            raise RuntimeError("Cannot add a result when no session is running")

        validate_number(result)

        if self.results:
            previous_draw_id = self.results[-1][0]
            if draw_id == previous_draw_id:
                return
            if not draw_id.isdigit() or int(draw_id) != int(previous_draw_id) + 1:
                raise ValueError(
                    "Session draw IDs must be consecutive: "
                    f"expected {int(previous_draw_id) + 1}, got {draw_id}"
                )
        elif draw_id != self.start_draw_id:
            raise ValueError(
                f"First session draw must be {self.start_draw_id}, got {draw_id}"
            )

        self.results.append((draw_id, result))
        self.storage.append_result(draw_id, result)
        self._print_live_gap(result)
        self._print_range_trend()

    # --------------------------------------------------

    def live_gap(self, number: int) -> int:
        """Return the current live gap for a number in this session."""
        return GapAnalyzer.current_gap(
            [value for _, value in self.results],
            number,
        )

    def live_last_gap(self, number: int) -> int | None:
        """Return draws between the two most recent appearances."""
        return GapAnalyzer.last_gap(
            [value for _, value in self.results],
            number,
        )

    def _print_live_gap(self, number: int) -> None:
        """Print gap history only when the number repeats in this session."""
        numbers = [value for _, value in self.results]
        positions = [
            index
            for index, value in enumerate(numbers)
            if value == number
        ]

        if len(positions) < 2:
            return

        gaps = [
            positions[index] - positions[index - 1] - 1
            for index in range(1, len(positions))
        ]
        gap_text = " | ".join(
            f"{ordinal}{suffix} gap: {gap}"
            for ordinal, suffix, gap in zip(
                range(1, len(gaps) + 1),
                ["st", "nd", "rd"],
                gaps,
            )
        )

        # For repeats beyond the first three, keep standard ordinal labels.
        if len(gaps) > 3:
            gap_text = " | ".join(
                f"{self._ordinal(index)} gap: {gap}"
                for index, gap in enumerate(gaps, start=1)
            )

        print(f"Live gap | Number {number:>2} | {gap_text}")

    @staticmethod
    def _ordinal(number: int) -> str:
        """Return a compact ordinal label such as '1st' or '22nd'."""
        if 10 <= number % 100 <= 20:
            suffix = "th"
        else:
            suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
        return f"{number}{suffix}"

    def _print_range_trend(self) -> None:
        counts = {label: 0 for label, _ in NUMBER_BANDS}

        for _, value in self.results:
            band = number_band(value)
            if band is not None:
                counts[band] += 1

        self._range_trend_history.append(
            tuple(counts[label] for label, _ in NUMBER_BANDS)
        )

        # Keep the graph compact while retaining recent movement.
        history = self._range_trend_history[-9:]
        maximum = max(max(snapshot) for snapshot in history)
        levels = "▁▂▃▄▅▆▇█"

        def sparkline(index: int) -> str:
            values = [snapshot[index] for snapshot in history]
            if maximum == 0:
                return levels[0] * len(values)
            return "".join(
                levels[min(len(levels) - 1, round(value / maximum * (len(levels) - 1)))]
                for value in values
            )

        print("RANGE TREND")
        for index, (label, _) in enumerate(NUMBER_BANDS):
            print(f"{label:<6} {sparkline(index):<9}     COUNT: {counts[label]:02d}")

    def session_expired(self) -> bool:
        """Backward-compatible alias for the draw-based completion check."""
        return self.is_complete()

    # --------------------------------------------------

    def finish(self):
        """Finalize and save a complete session."""
        if not self.running:
            return

        if not self.is_complete():
            raise RuntimeError(
                f"Cannot finish incomplete session: "
                f"{len(self.results)}/{SESSION_DRAW_COUNT} draws"
            )

        self.running = False

        stats = self.statistics.build(self.results)
        report = SessionReport(self.session_name, self.results, stats)
        report.print()

        filename = self.storage.save_session(
            self.session_name,
            report.text(),
        )
        print(f"\nSaved session -> {filename}")

        self.results.clear()
        self.start_draw_id = None

    # --------------------------------------------------

    def total_results(self) -> int:
        return len(self.results)

    def is_running(self) -> bool:
        return self.running
