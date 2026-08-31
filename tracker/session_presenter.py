"""Console and report presentation for tracker sessions."""

from pathlib import Path

from config import (
    COLOR_ABSENCE_ALERT_AT,
    LINE,
    RANGE_ABSENCE_ALERT_AT,
    SESSION_DRAW_COUNT,
)
from models.number_domain import (
    NUMBER_BANDS,
    NUMBER_COLORS,
    NUMBER_VALUES,
    color_absence_streaks,
    color_counts,
    number_counts,
    range_absence_streaks,
    range_counts,
)
from ui.events import EventBus


class SessionPresenter:
    """Publish session presentation events without owning state or persistence."""

    def __init__(self, events: EventBus | None = None):
        self.events = events
        self._alerted_absent_ranges: set[str] = set()
        self._alerted_absent_colors: set[str] = set()
        self._session_name = ""

    def restore(
        self,
        results: list[tuple[str, int]],
        session_name: str = "",
    ) -> None:
        """Publish restored checkpoint state and any currently active alerts."""
        self.reset()
        self._session_name = session_name
        self._publish_session_update(results)
        self._publish_range_absence_alerts(results)
        self._publish_color_absence_alerts(results)

    def reset(self) -> None:
        self._alerted_absent_ranges = set()
        self._alerted_absent_colors = set()
        self._session_name = ""

    def waiting_for_session(self) -> None:
        self._publish(
            "status",
            message="Waiting for the next session start (draw ID ending in 1).",
        )

    def waiting_draw(self, draw_id: str, position: int) -> None:
        self._publish("waiting", draw_id=draw_id, position=position)

    def session_boundary_found(self) -> None:
        self._publish("status", message="Session boundary found.")

    def session_started(
        self,
        session_name: str,
        start_draw_id: str,
        end_draw_id: str,
        draw_count: int,
    ) -> None:
        self._session_name = session_name
        self._publish(
            "session_started",
            session_name=session_name,
            start_draw_id=start_draw_id,
            end_draw_id=end_draw_id,
            draw_count=draw_count,
        )

    def result_recorded(
        self,
        results: list[tuple[str, int]],
    ) -> None:
        self._publish_session_update(results)
        self._publish_range_absence_alerts(results)
        self._publish_color_absence_alerts(results)

    def session_incomplete(
        self,
        captured_count: int,
        draw_count: int,
        start_draw_id: str | None,
        missing_draw_ids: tuple[str, ...],
        archive_path: Path | None,
    ) -> None:
        message = (
            "Session incomplete: required draw IDs were not captured "
            f"({captured_count}/{draw_count} captured from {start_draw_id})."
        )
        self._publish(
            "session_incomplete",
            message=message,
            missing_draw_ids=missing_draw_ids,
            archive_path=str(archive_path) if archive_path is not None else "",
        )

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
        lines.extend(
            ("", "COLOR COUNTS", "-" * 70, "Color | Count", "------+------")
        )
        color_totals = color_counts(result for _, result in results)
        lines.extend(
            f"{label:<5} | {color_totals[label]:>5}"
            for label, _ in NUMBER_COLORS
        )
        lines.append(LINE)
        return "\n".join(lines)

    def session_finished(self, report_text: str, filename: Path) -> None:
        self._publish(
            "session_finished",
            report_text=report_text,
            filename=str(filename),
        )

    @staticmethod
    def _range_absence_streaks(results: list[tuple[str, int]]) -> dict[str, int]:
        return range_absence_streaks(value for _, value in results)

    @staticmethod
    def _color_absence_streaks(results: list[tuple[str, int]]) -> dict[str, int]:
        return color_absence_streaks(value for _, value in results)

    @staticmethod
    def _color_counts(results: list[tuple[str, int]]) -> dict[str, int]:
        return color_counts(value for _, value in results)

    def _publish(self, kind: str, **payload: object) -> None:
        """Send presentation updates to the dashboard when one is active."""
        if self.events is not None:
            self.events.publish(kind, **payload)

    def _publish_session_update(self, results: list[tuple[str, int]]) -> None:
        self._publish(
            "session_update",
            session_name=self._session_name,
            draw_count=SESSION_DRAW_COUNT,
            results=tuple(results),
            range_counts=range_counts(result for _, result in results),
            color_counts=color_counts(result for _, result in results),
        )

    def _publish_range_absence_alerts(self, results: list[tuple[str, int]]) -> None:
        """Alert once when a range first exceeds the absence threshold."""
        self._publish_absence_alerts(
            "RANGE",
            NUMBER_BANDS,
            self._range_absence_streaks(results),
            self._alerted_absent_ranges,
            RANGE_ABSENCE_ALERT_AT,
        )

    def _publish_color_absence_alerts(self, results: list[tuple[str, int]]) -> None:
        """Alert once when a color first exceeds the absence threshold."""
        self._publish_absence_alerts(
            "COLOR",
            NUMBER_COLORS,
            self._color_absence_streaks(results),
            self._alerted_absent_colors,
            COLOR_ABSENCE_ALERT_AT,
        )

    def _publish_absence_alerts(
        self,
        alert_type: str,
        groups: tuple[tuple[str, range], ...],
        streaks: dict[str, int],
        alerted_groups: set[str],
        alert_at: int,
    ) -> None:
        """Publish a one-time alert when a group reaches its threshold."""
        for label, _ in groups:
            streak = streaks[label]
            if streak == 0:
                alerted_groups.discard(label)
                continue
            if (
                streak >= alert_at
                and label not in alerted_groups
            ):
                message = (
                    f"{alert_type} ALERT | {label} has not appeared for {streak} "
                    "consecutive draws."
                )
                self._publish(
                    "alert",
                    alert_type=alert_type,
                    label=label,
                    streak=streak,
                    message=message,
                )
                alerted_groups.add(label)
