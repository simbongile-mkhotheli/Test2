"""Console and report presentation for tracker sessions."""

from pathlib import Path

from analytics.analyzers.gaps import GapAnalyzer
from analytics.reports.session import SessionReport
from config import LINE
from models.number_domain import NUMBER_BANDS, number_band


class SessionPresenter:
    """Render session progress without owning session state or persistence."""

    _SPARKLINE_LEVELS = "▁▂▃▄▅▆▇█"

    def __init__(self):
        self._range_trend_history: list[tuple[int, ...]] = []

    def restore(self, results: list[tuple[str, int]]) -> None:
        """Rebuild display-only trend history after a checkpoint restore."""
        self.reset()
        for index in range(1, len(results) + 1):
            self._range_trend_history.append(self._range_counts(results[:index]))

    def reset(self) -> None:
        self._range_trend_history = []

    def waiting_for_session(self) -> None:
        print()
        print(LINE)
        print("Waiting for next session start (draw ID ending in 1)...")
        print(LINE)

    def waiting_draw(self, draw_id: str, position: int) -> None:
        print(f"\rWaiting... draw {draw_id} (position {position})", end="")

    @staticmethod
    def session_boundary_found() -> None:
        print()

    def session_started(self, start_draw_id: str, draw_count: int) -> None:
        end_draw_id = str(int(start_draw_id) + draw_count - 1)
        print()
        print(LINE)
        print(f"Started session at draw {start_draw_id}")
        print(f"Session length  : {draw_count} draws")
        print(f"Ends at draw    : {end_draw_id}")
        print(LINE)

    def result_recorded(
        self,
        results: list[tuple[str, int]],
        result: int,
    ) -> None:
        self._print_live_gap(results, result)
        self._print_range_trend(results)

    def session_abandoned(
        self,
        captured_count: int,
        draw_count: int,
        start_draw_id: str | None,
        archived_path: Path | None,
    ) -> None:
        print(
            "\nSession abandoned after a missed draw: "
            f"{captured_count}/{draw_count} captured from {start_draw_id}."
        )
        if archived_path is not None:
            print(f"Archived incomplete session -> {archived_path}")

    def report(
        self,
        session_name: str,
        results: list[tuple[str, int]],
        statistics,
    ) -> str:
        return SessionReport(session_name, results, statistics).text()

    def session_finished(self, report_text: str, filename: Path) -> None:
        print(report_text)
        print(f"\nSaved session -> {filename}")

    @staticmethod
    def live_gap(results: list[tuple[str, int]], number: int) -> int:
        return GapAnalyzer.current_gap([value for _, value in results], number)

    @staticmethod
    def live_last_gap(results: list[tuple[str, int]], number: int) -> int | None:
        return GapAnalyzer.last_gap([value for _, value in results], number)

    @staticmethod
    def _ordinal(number: int) -> str:
        if 10 <= number % 100 <= 20:
            suffix = "th"
        else:
            suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
        return f"{number}{suffix}"

    def _print_live_gap(self, results: list[tuple[str, int]], number: int) -> None:
        numbers = [value for _, value in results]
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
            f"{self._ordinal(index)} gap: {gap}"
            for index, gap in enumerate(gaps, start=1)
        )
        print(f"Live gap | Number {number:>2} | {gap_text}")

    @staticmethod
    def _range_counts(results: list[tuple[str, int]]) -> tuple[int, ...]:
        counts = {label: 0 for label, _ in NUMBER_BANDS}
        for _, value in results:
            band = number_band(value)
            if band is not None:
                counts[band] += 1
        return tuple(counts[label] for label, _ in NUMBER_BANDS)

    def _print_range_trend(self, results: list[tuple[str, int]]) -> None:
        counts = self._range_counts(results)
        self._range_trend_history.append(counts)
        history = self._range_trend_history[-9:]
        maximum = max(max(snapshot) for snapshot in history)

        def sparkline(index: int) -> str:
            values = [snapshot[index] for snapshot in history]
            if maximum == 0:
                return self._SPARKLINE_LEVELS[0] * len(values)
            return "".join(
                self._SPARKLINE_LEVELS[
                    min(
                        len(self._SPARKLINE_LEVELS) - 1,
                        round(value / maximum * (len(self._SPARKLINE_LEVELS) - 1)),
                    )
                ]
                for value in values
            )

        print("RANGE TREND")
        for index, (label, _) in enumerate(NUMBER_BANDS):
            print(f"{label:<6} {sparkline(index):<9}     COUNT: {counts[index]:02d}")
