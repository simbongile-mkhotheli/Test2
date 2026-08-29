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
    assert "COLOR COUNTS" in report
    assert "Black |     0" in report
    assert "Gray  |     0" in report
    assert "Red   |     2" in report


def test_presenter_alerts_once_when_a_range_is_absent_for_more_than_nine_draws(
    capsys,
):
    presenter = SessionPresenter()
    first_nine = [(str(12608180151 + index), 0) for index in range(9)]
    tenth = [*first_nine, ("12608180160", 0)]

    presenter.result_recorded(first_nine)
    assert "RANGE ALERT" not in capsys.readouterr().out

    presenter.result_recorded(tenth)
    alert_output = capsys.readouterr().out
    for label in ("1-6", "7-12", "13-18"):
        assert (
            f"RANGE ALERT | {label} has not appeared for 10 consecutive draws."
            in alert_output
        )

    presenter.result_recorded([*tenth, ("12608180161", 0)])
    assert "RANGE ALERT" not in capsys.readouterr().out


def test_presenter_reports_an_existing_absence_alert_after_restore(capsys):
    results = [(str(12608180151 + index), 0) for index in range(10)]
    presenter = SessionPresenter()
    presenter.restore(results)

    restore_output = capsys.readouterr().out
    assert "RANGE ALERT | 1-6 has not appeared for 10 consecutive draws." in restore_output
    assert "COLOR ALERT | Black has not appeared for 10 consecutive draws." in restore_output

    presenter.result_recorded([*results, ("12608180161", 0)])

    next_output = capsys.readouterr().out
    assert "RANGE ALERT" not in next_output
    assert "COLOR ALERT" not in next_output


def test_presenter_alerts_once_when_a_color_is_absent_for_more_than_nine_draws(
    capsys,
):
    presenter = SessionPresenter()
    first_nine = [(str(12608180151 + index), 0) for index in range(9)]
    tenth = [*first_nine, ("12608180160", 0)]

    presenter.result_recorded(first_nine)
    assert "COLOR ALERT" not in capsys.readouterr().out

    presenter.result_recorded(tenth)
    alert_output = capsys.readouterr().out
    for color in ("Black", "Gray", "Red"):
        assert (
            f"COLOR ALERT | {color} has not appeared for 10 consecutive draws."
            in alert_output
        )

    presenter.result_recorded([*tenth, ("12608180161", 0)])
    assert "COLOR ALERT" not in capsys.readouterr().out
