from tracker.session_presenter import SessionPresenter
from ui.events import EventBus


def alert_messages(events: EventBus) -> list[str]:
    return [
        event.payload["message"]
        for event in events.drain()
        if event.kind == "alert"
    ]


def test_presenter_publishes_restored_checkpoint_state_for_the_dashboard():
    events = EventBus()
    presenter = SessionPresenter(events)
    presenter.restore(
        [
            ("12608180151", 0),
            ("12608180152", 5),
            ("12608180153", 14),
        ],
        "draw-12608180151",
    )

    updates = [event for event in events.drain() if event.kind == "session_update"]

    assert len(updates) == 1
    assert updates[0].payload["session_name"] == "draw-12608180151"
    assert updates[0].payload["results"] == (
        ("12608180151", 0),
        ("12608180152", 5),
        ("12608180153", 14),
    )


def test_presenter_builds_the_final_report():
    results = [
        ("12608180151", 15),
        ("12608180152", 15),
        ("12608180153", 0),
    ]
    presenter = SessionPresenter()

    report = presenter.report("draw-12608180151", results)

    assert "BETGAMES SESSION REPORT" in report
    assert "draw-12608180151" in report
    assert "RESULT COUNTS" in report
    assert "     0 |     1" in report
    assert "    15 |     2" in report
    assert "Total  |     3" in report
    assert "RANGE COUNTS" in report
    assert "1-6   |     0" in report
    assert "13-18 |     2" in report
    assert "COLOR COUNTS" in report
    assert "Black |     0" in report
    assert "Gray  |     0" in report
    assert "Red   |     2" in report


def test_presenter_alerts_once_when_a_range_is_absent_for_more_than_nine_draws(
):
    events = EventBus()
    presenter = SessionPresenter(events)
    first_nine = [(str(12608180151 + index), 0) for index in range(9)]
    tenth = [*first_nine, ("12608180160", 0)]

    presenter.result_recorded(first_nine)
    assert not alert_messages(events)

    presenter.result_recorded(tenth)
    alert_output = alert_messages(events)
    for label in ("1-6", "7-12", "13-18"):
        assert f"RANGE ALERT | {label} has not appeared for 10 consecutive draws." in alert_output

    presenter.result_recorded([*tenth, ("12608180161", 0)])
    assert not alert_messages(events)


def test_presenter_reports_an_existing_absence_alert_after_restore():
    results = [(str(12608180151 + index), 0) for index in range(10)]
    events = EventBus()
    presenter = SessionPresenter(events)
    presenter.restore(results)

    restore_alerts = alert_messages(events)
    assert "RANGE ALERT | 1-6 has not appeared for 10 consecutive draws." in restore_alerts
    assert "COLOR ALERT | Black has not appeared for 10 consecutive draws." in restore_alerts

    presenter.result_recorded([*results, ("12608180161", 0)])

    assert not alert_messages(events)


def test_presenter_alerts_once_when_a_color_is_absent_for_more_than_nine_draws(
):
    events = EventBus()
    presenter = SessionPresenter(events)
    first_nine = [(str(12608180151 + index), 0) for index in range(9)]
    tenth = [*first_nine, ("12608180160", 0)]

    presenter.result_recorded(first_nine)
    assert not alert_messages(events)

    presenter.result_recorded(tenth)
    alert_output = alert_messages(events)
    for color in ("Black", "Gray", "Red"):
        assert f"COLOR ALERT | {color} has not appeared for 10 consecutive draws." in alert_output

    presenter.result_recorded([*tenth, ("12608180161", 0)])
    assert not alert_messages(events)


def test_presenter_publishes_session_counts_for_the_dashboard():
    events = EventBus()
    presenter = SessionPresenter(events)
    presenter.session_started("draw-12608180151", "12608180151", "12608180180", 30)
    presenter.result_recorded(
        [
            ("12608180151", 1),
            ("12608180152", 2),
            ("12608180153", 3),
        ]
    )

    updates = [event for event in events.drain() if event.kind == "session_update"]

    assert len(updates) == 1
    assert updates[0].payload["range_counts"] == {
        "1-6": 3,
        "7-12": 0,
        "13-18": 0,
    }
    assert updates[0].payload["number_counts"] == {
        **{number: 0 for number in range(19)},
        1: 1,
        2: 1,
        3: 1,
    }
    assert updates[0].payload["color_counts"] == {
        "Black": 1,
        "Gray": 1,
        "Red": 1,
    }
