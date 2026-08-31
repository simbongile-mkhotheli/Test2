from tracker.session_presenter import SessionPresenter
from ui.events import EventBus


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


def test_presenter_publishes_session_counts_for_the_dashboard():
    events = EventBus()
    presenter = SessionPresenter(events)
    presenter.session_started("draw-12608180151", "12608180151", "12608180160", 10)
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
    assert "number_counts" not in updates[0].payload
    assert updates[0].payload["color_counts"] == {
        "Black": 1,
        "Gray": 1,
        "Red": 1,
    }
