"""Console and report presentation for tracker sessions."""

from pathlib import Path

from config import LINE, SESSION_DRAW_COUNT
from models.number_domain import (
    NUMBER_BANDS,
    NUMBER_COLORS,
    NUMBER_VALUES,
    color_counts,
    number_counts,
    range_counts,
)
from tracker.session_tendency import HistoricalTendency
from ui.events import EventBus


class SessionPresenter:
    """Publish session presentation events without owning state or persistence."""

    def __init__(self, events: EventBus | None = None):
        self.events = events
        self._session_name = ""

    def restore(
        self,
        results: list[tuple[str, int]],
        session_name: str = "",
    ) -> None:
        """Publish restored checkpoint state for the session dashboard."""
        self.reset()
        self._session_name = session_name
        self._publish_session_update(results)

    def reset(self) -> None:
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

    def upcoming_position_color_alert(
        self,
        position: int,
        color: str,
        older_session_name: str,
        newer_session_name: str,
    ) -> None:
        """Notify before a position whose two-session color pattern repeats."""
        self._publish(
            "alert",
            alert_type="POSITION_COLOR",
            label=f"Position {position}",
            message=(
                f"UPCOMING POSITION ALERT | Position {position} was {color} "
                f"in the previous two consecutive sessions "
                f"{older_session_name} and {newer_session_name}."
            ),
        )

    def historical_tendencies(
        self,
        color_tendency: HistoricalTendency | None,
        range_tendency: HistoricalTendency | None,
    ) -> None:
        """Publish history-based next-position summaries for the dashboard."""
        self._publish(
            "tendency_update",
            color=self._format_tendency(color_tendency),
            range=self._format_tendency(range_tendency),
        )

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

    def _publish(self, kind: str, **payload: object) -> None:
        """Send presentation updates to the dashboard when one is active."""
        if self.events is not None:
            self.events.publish(kind, **payload)

    @staticmethod
    def _format_tendency(tendency: HistoricalTendency | None) -> str:
        if tendency is None:
            return "Capture two draws to compare completed-session history."
        prefix = " → ".join(tendency.prefix)
        if tendency.sample_size == 0:
            return (
                f"Position {tendency.target_position} after {prefix}: "
                "no matching completed sessions."
            )

        order = {label: index for index, (label, _) in enumerate(tendency.outcomes)}
        outcomes = sorted(
            tendency.outcomes,
            key=lambda outcome: (-outcome[1], order[outcome[0]]),
        )
        distribution = ", ".join(
            f"{label} {count / tendency.sample_size:.0%} ({count})"
            for label, count in outcomes
        )
        return (
            f"Position {tendency.target_position} after {prefix} • "
            f"{tendency.sample_size} matching sessions • {distribution}"
        )

    def _publish_session_update(self, results: list[tuple[str, int]]) -> None:
        self._publish(
            "session_update",
            session_name=self._session_name,
            draw_count=SESSION_DRAW_COUNT,
            results=tuple(results),
            range_counts=range_counts(result for _, result in results),
            color_counts=color_counts(result for _, result in results),
        )
