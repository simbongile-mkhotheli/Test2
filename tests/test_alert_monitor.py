from tracker.alert_monitor import AlertMonitor
from config import COLOR_ABSENCE_ALERT_AT, RANGE_ABSENCE_ALERT_AT
from ui.events import EventBus


def alert_messages(events: EventBus, alert_type: str | None = None) -> list[str]:
    return [
        event.payload["message"]
        for event in events.drain()
        if event.kind == "alert"
        and (alert_type is None or event.payload["alert_type"] == alert_type)
    ]


def test_range_alerts_are_tracked_outside_session_boundaries():
    events = EventBus()
    alerts = AlertMonitor(events)

    for _ in range(RANGE_ABSENCE_ALERT_AT - 1):
        alerts.record_result(0)
    assert not alert_messages(events)

    alerts.record_result(0)
    messages = alert_messages(events, "RANGE")
    for label in ("1-6", "7-12", "13-18"):
        assert (
            f"RANGE ALERT | {label} has not appeared for "
            f"{RANGE_ABSENCE_ALERT_AT} consecutive draws."
        ) in messages

    alerts.record_result(0)
    assert not alert_messages(events)


def test_color_alerts_are_tracked_outside_session_boundaries():
    events = EventBus()
    alerts = AlertMonitor(events)

    for _ in range(COLOR_ABSENCE_ALERT_AT - 1):
        alerts.record_result(0)
    assert not alert_messages(events, "COLOR")

    alerts.record_result(0)
    messages = alert_messages(events, "COLOR")
    for label in ("Black", "Gray", "Red"):
        assert (
            f"COLOR ALERT | {label} has not appeared for "
            f"{COLOR_ABSENCE_ALERT_AT} consecutive draws."
        ) in messages


def test_alerts_resume_from_the_live_results_log_without_a_session():
    events = EventBus()
    alerts = AlertMonitor(events)
    results = [
        (str(12608180151 + index), 0)
        for index in range(max(RANGE_ABSENCE_ALERT_AT, COLOR_ABSENCE_ALERT_AT))
    ]

    alerts.restore(results)

    messages = alert_messages(events)
    assert (
        f"RANGE ALERT | 1-6 has not appeared for "
        f"{RANGE_ABSENCE_ALERT_AT} consecutive draws."
    ) in messages
    assert (
        f"COLOR ALERT | Black has not appeared for "
        f"{COLOR_ABSENCE_ALERT_AT} consecutive draws."
    ) in messages
