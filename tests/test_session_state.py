from tracker.session_state import SessionState


def test_state_proposes_results_without_mutating_before_persistence():
    state = SessionState(draw_count=30)
    state.start("12608180151")

    proposed = state.proposed_results("12608180151", 15)

    assert state.results == []
    assert proposed == [("12608180151", 15)]

    state.commit_results(proposed)
    assert state.results == proposed


def test_state_accepts_new_observed_draw_ids_after_a_skip():
    state = SessionState(draw_count=30)
    state.start("12608180151")
    state.commit_results(state.proposed_results("12608180151", 15))

    proposed = state.proposed_results("12608180153", 14)

    assert proposed == [
        ("12608180151", 15),
        ("12608180153", 14),
    ]


def test_state_recovers_a_missing_draw_from_newest_first_history():
    state = SessionState(draw_count=30)
    start = 12608260571
    state.start(str(start))
    state.commit_results([(str(start + offset), 1) for offset in range(16)])

    proposed = state.proposed_results_from_history(
        "12608260588",
        [8, 17, *([1] * 8)],
    )

    assert proposed is not None
    assert dict(proposed)["12608260587"] == 17
    assert dict(proposed)["12608260588"] == 8
    assert len(proposed) == 18


def test_state_marks_only_aged_out_missing_draws_as_unrecoverable():
    state = SessionState(draw_count=30)
    start = 12608260571
    state.start(str(start))
    state.commit_results([(str(start + offset), 1) for offset in range(16)])

    assert state.unrecoverable_missing_draw_ids("12608260601", 10) == (
        "12608260587",
        "12608260588",
        "12608260589",
        "12608260590",
        "12608260591",
    )


def test_state_rejects_history_that_disagrees_with_a_saved_draw():
    state = SessionState(draw_count=30)
    state.start("12608260571")
    state.commit_results([("12608260571", 3)])

    try:
        state.proposed_results_from_history("12608260571", [4])
    except ValueError as error:
        assert "disagrees" in str(error)
    else:
        raise AssertionError("conflicting history was accepted")


def test_state_completion_depends_on_the_configured_capture_count():
    state = SessionState(draw_count=3)
    state.start("12608180151")
    for draw_id, result in [
        ("12608180151", 1),
        ("12608180152", 2),
        ("12608180153", 3),
    ]:
        state.commit_results(state.proposed_results(draw_id, result))

    assert state.is_complete()

    state = SessionState(draw_count=30)
    state.start("12608180151")
    state.commit_results(
        [(str(12608180151 + offset), offset % 19) for offset in range(30)]
    )
    assert state.is_complete()


def test_state_cannot_complete_when_thirty_results_include_a_wrong_draw_id():
    state = SessionState(draw_count=30)
    start = 12608180151
    state.start(str(start))
    state.commit_results([(str(start + offset), offset % 19) for offset in range(29)])

    assert state.proposed_results("12608180181", 3) is None
    assert not state.is_complete()
