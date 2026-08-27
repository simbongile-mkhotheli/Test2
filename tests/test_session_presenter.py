from tracker.session_presenter import SessionPresenter


def test_presenter_rebuilds_range_trend_history_when_restoring():
    presenter = SessionPresenter()
    presenter.restore(
        [
            ("12608180151", 0),
            ("12608180152", 5),
            ("12608180153", 14),
        ]
    )

    assert presenter._range_trend_history == [
        (0, 0, 0),
        (1, 0, 0),
        (1, 0, 1),
    ]


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
