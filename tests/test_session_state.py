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


def test_state_never_assigns_an_older_history_value_to_a_draw_id():
    state = SessionState(draw_count=30)
    start = 12608260571
    state.start(str(start))
    state.commit_results([(str(start + offset), 1) for offset in range(16)])

    proposed = state.proposed_result_from_snapshot(
        "12608260588",
        [8, 17, *([1] * 8)],
    )

    assert proposed is not None
    assert dict(proposed)["12608260588"] == 8
    assert "12608260587" not in dict(proposed)
    assert len(proposed) == 17


def test_later_history_values_cannot_overwrite_a_checkpointed_draw():
    state = SessionState(draw_count=30)
    start = 12608270881
    state.start(str(start))
    state.commit_results(
        [
            (str(start + offset), 8 if offset == 9 else 1)
            for offset in range(10)
        ]
    )

    proposed = state.proposed_result_from_snapshot(
        "12608270891",
        [15, 14, 8, *([1] * 7)],
    )

    assert proposed is not None
    assert dict(proposed)["12608270890"] == 8
    assert dict(proposed)["12608270891"] == 15


def test_state_marks_all_missing_draws_as_incomplete_at_session_end():
    state = SessionState(draw_count=30)
    start = 12608260571
    state.start(str(start))
    state.commit_results([(str(start + offset), 1) for offset in range(16)])

    assert state.incomplete_missing_draw_ids("12608260601") == (
        *(str(draw_id) for draw_id in range(12608260587, 12608260601)),
    )


def test_state_keeps_the_first_checkpointed_value_for_a_duplicate_draw():
    state = SessionState(draw_count=30)
    state.start("12608260571")
    state.commit_results([("12608260571", 3)])

    assert state.proposed_result_from_snapshot("12608260571", [4]) is None
    assert state.results == [("12608260571", 3)]


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
