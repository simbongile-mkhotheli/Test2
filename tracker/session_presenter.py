"""Console and report presentation for tracker sessions."""

from pathlib import Path

from config import LINE, RANGE_ABSENCE_ALERT_AFTER
from models.number_domain import (
    NUMBER_BANDS,
    NUMBER_VALUES,
    number_counts,
    range_absence_streaks,
    range_counts,
)


class SessionPresenter:
    """Render session progress without owning session state or persistence."""

    _SPARKLINE_LEVELS = "▁▂▃▄▅▆▇█"

    def __init__(self):
        self._range_trend_history: list[tuple[int, ...]] = []
        self._alerted_absent_ranges: set[str] = set()

    def restore(self, results: list[tuple[str, int]]) -> None:
        """Rebuild display-only trend history after a checkpoint restore."""
        self.reset()
        for index in range(1, len(results) + 1):
            self._range_trend_history.append(self._range_counts(results[:index]))
        self._print_range_absence_alerts(results)

    def reset(self) -> None:
        self._range_trend_history = []
        self._alerted_absent_ranges = set()

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

    def session_started(
        self,
        start_draw_id: str,
        end_draw_id: str,
        draw_count: int,
    ) -> None:
        print()
        print(LINE)
        print(f"Started session at draw {start_draw_id}")
        print(f"Session length  : {draw_count} draws")
        print(f"Ends at draw    : {end_draw_id}")
        print(LINE)

    def result_recorded(
        self,
        results: list[tuple[str, int]],
    ) -> None:
        self._print_range_trend(results)
        self._print_range_absence_alerts(results)

    @staticmethod
    def session_incomplete(
        captured_count: int,
        draw_count: int,
        start_draw_id: str | None,
        missing_draw_ids: tuple[str, ...],
        archive_path: Path | None,
    ) -> None:
        print(
            "\nSession incomplete: required draw IDs were not captured "
            f"({captured_count}/{draw_count} captured from "
            f"{start_draw_id})."
        )
        print("Missing draw IDs -> " + ", ".join(missing_draw_ids))
        if archive_path is not None:
            print(f"Saved incomplete session -> {archive_path}")

    def report(
        self,
        session_name: str,
        results: list[tuple[str, int]],
    ) -> str:
        lines = [LINE, "BETGAMES SESSION REPORT", LINE, f"Session: {session_name}", ""]
        start_draw_id = results[0][0] if results else "-"
        end_draw_id = results[-1][0] if results else "-"
        lines.extend(
            (
                "SESSION",
                "-" * 70,
                f"Start draw : {start_draw_id}",
                f"End draw   : {end_draw_id}",
                f"Draw count : {len(results)}",
                "",
                "DRAWS",
                "-" * 70,
                "Pos  Draw ID             Result",
                "---  -----------------   ------",
            )
        )
        lines.extend(
            f"{position:02d}   {draw_id:<19} {result:>6}"
            for position, (draw_id, result) in enumerate(results, start=1)
        )
        lines.extend(("", "RESULT COUNTS", "-" * 70, "Number | Count"))
        lines.append("-------+------")
        counts = number_counts(result for _, result in results)
        lines.extend(
            f"{number:>6} | {counts[number]:>5}"
            for number in NUMBER_VALUES
        )
        lines.extend(("", f"Total  | {len(results):>5}", "", "RANGE COUNTS", "-" * 70))
        lines.extend(
            (
                "Range | Count",
                "------+------",
            )
        )
        range_totals = range_counts(result for _, result in results)
        lines.extend(
            f"{label:<5} | {range_totals[label]:>5}"
            for label, _ in NUMBER_BANDS
        )
        lines.append(LINE)
        return "\n".join(lines)

    def session_finished(self, report_text: str, filename: Path) -> None:
        print(report_text)
        print(f"\nSaved session -> {filename}")

    @staticmethod
    def _range_counts(results: list[tuple[str, int]]) -> tuple[int, ...]:
        counts = range_counts(value for _, value in results)
        return tuple(counts[label] for label, _ in NUMBER_BANDS)

    @staticmethod
    def _range_absence_streaks(results: list[tuple[str, int]]) -> dict[str, int]:
        return range_absence_streaks(value for _, value in results)

    def _print_range_absence_alerts(self, results: list[tuple[str, int]]) -> None:
        """Alert once when a range first exceeds the absence threshold."""
        streaks = self._range_absence_streaks(results)
        for label, _ in NUMBER_BANDS:
            streak = streaks[label]
            if streak == 0:
                self._alerted_absent_ranges.discard(label)
                continue
            if (
                streak > RANGE_ABSENCE_ALERT_AFTER
                and label not in self._alerted_absent_ranges
            ):
                print(
                    f"RANGE ALERT | {label} has not appeared for {streak} "
                    "consecutive draws."
                )
                self._alerted_absent_ranges.add(label)

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
