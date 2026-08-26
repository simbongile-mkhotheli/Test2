"""Console and report presentation for tracker sessions."""

from pathlib import Path

from config import LINE
from models.number_domain import NUMBER_BANDS, NUMBER_VALUES, number_band, number_counts


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

    @staticmethod
    def draws_recovered(draw_ids: tuple[str, ...]) -> None:
        """Tell the operator which in-session rows came from verified history."""
        print(
            "Recovered from verified history -> "
            + ", ".join(draw_ids)
        )

    @staticmethod
    def session_incomplete(
        captured_count: int,
        draw_count: int,
        start_draw_id: str | None,
        missing_draw_ids: tuple[str, ...],
        archive_path: Path | None,
    ) -> None:
        print(
            "\nSession incomplete: required draw IDs are no longer available "
            f"in history ({captured_count}/{draw_count} captured from "
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
        lines.extend(("", f"Total  | {len(results):>5}", LINE))
        return "\n".join(lines)

    def session_finished(self, report_text: str, filename: Path) -> None:
        print(report_text)
        print(f"\nSaved session -> {filename}")

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
