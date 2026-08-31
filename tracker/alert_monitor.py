"""Live range and color absence alerts, independent of session boundaries."""

from collections.abc import Iterable

from config import COLOR_ABSENCE_ALERT_AT, RANGE_ABSENCE_ALERT_AT
from models.number_domain import (
    NUMBER_BANDS,
    NUMBER_COLORS,
    color_absence_streaks,
    number_band,
    number_color,
    range_absence_streaks,
)
from ui.events import EventBus


class AlertMonitor:
    """Track live absence streaks from every verified browser result."""

    def __init__(self, events: EventBus | None = None) -> None:
        self.events = events
        self._range_streaks = {label: 0 for label, _ in NUMBER_BANDS}
        self._color_streaks = {label: 0 for label, _ in NUMBER_COLORS}
        self._alerted_ranges: set[str] = set()
        self._alerted_colors: set[str] = set()

    def restore(self, results: Iterable[tuple[str, int]]) -> None:
        """Restore streaks from the root live-results log on application start."""
        values = tuple(result for _, result in results)
        self._range_streaks = range_absence_streaks(values)
        self._color_streaks = color_absence_streaks(values)
        self._alerted_ranges = set()
        self._alerted_colors = set()
        self._publish_active_alerts(
            "RANGE",
            NUMBER_BANDS,
            self._range_streaks,
            self._alerted_ranges,
            RANGE_ABSENCE_ALERT_AT,
        )
        self._publish_active_alerts(
            "COLOR",
            NUMBER_COLORS,
            self._color_streaks,
            self._alerted_colors,
            COLOR_ABSENCE_ALERT_AT,
        )

    def record_result(self, result: int) -> None:
        """Update alert streaks from one newly persisted live result."""
        self._advance_streaks(
            "RANGE",
            NUMBER_BANDS,
            number_band(result),
            self._range_streaks,
            self._alerted_ranges,
            RANGE_ABSENCE_ALERT_AT,
        )
        self._advance_streaks(
            "COLOR",
            NUMBER_COLORS,
            number_color(result),
            self._color_streaks,
            self._alerted_colors,
            COLOR_ABSENCE_ALERT_AT,
        )

    def _advance_streaks(
        self,
        alert_type: str,
        groups: tuple[tuple[str, range], ...],
        observed_group: str | None,
        streaks: dict[str, int],
        alerted_groups: set[str],
        alert_at: int,
    ) -> None:
        for label, _ in groups:
            if label == observed_group:
                streaks[label] = 0
                alerted_groups.discard(label)
                continue

            streaks[label] += 1
            if streaks[label] >= alert_at and label not in alerted_groups:
                self._publish_alert(alert_type, label, streaks[label])
                alerted_groups.add(label)

    def _publish_active_alerts(
        self,
        alert_type: str,
        groups: tuple[tuple[str, range], ...],
        streaks: dict[str, int],
        alerted_groups: set[str],
        alert_at: int,
    ) -> None:
        for label, _ in groups:
            if streaks[label] >= alert_at:
                self._publish_alert(alert_type, label, streaks[label])
                alerted_groups.add(label)

    def _publish_alert(self, alert_type: str, label: str, streak: int) -> None:
        if self.events is None:
            return
        message = (
            f"{alert_type} ALERT | {label} has not appeared for {streak} "
            "consecutive draws."
        )
        self.events.publish(
            "alert",
            alert_type=alert_type,
            label=label,
            streak=streak,
            message=message,
        )
