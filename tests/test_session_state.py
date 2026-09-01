from config import SESSION_DRAW_COUNT
from tracker.session_state import SessionState


def test_ten_draw_session_starts_at_one_and_ends_at_zero():
    state = SessionState(draw_count=SESSION_DRAW_COUNT)
    state.start("12608180151")

    assert state.end_draw_id == "12608180160"
    assert state.expected_draw_ids == tuple(
        str(12608180151 + offset)
        for offset in range(SESSION_DRAW_COUNT)
    )


def test_state_proposes_results_without_mutating_before_persistence():
    state = SessionState(draw_count=SESSION_DRAW_COUNT)
    state.start("12608180151")

    proposed = state.proposed_results("12608180151", 15)

    assert state.results == []
    assert proposed == [("12608180151", 15)]

    state.commit_results(proposed)
    assert state.results == proposed


def test_state_rejects_an_observed_draw_after_a_skip():
    state = SessionState(draw_count=SESSION_DRAW_COUNT)
    state.start("12608180151")
    state.commit_results(state.proposed_results("12608180151", 15))

    proposed = state.proposed_results("12608180153", 14)

    assert proposed is None
    assert state.results == [("12608180151", 15)]
    assert state.next_draw_id == "12608180152"
    assert state.incomplete_missing_draw_ids("12608180153") == ("12608180152",)


def test_state_does_not_append_a_later_draw_after_a_gap():
    state = SessionState(draw_count=SESSION_DRAW_COUNT)
    start = 12608260571
    state.start(str(start))
    state.commit_results([(str(start + offset), 1) for offset in range(6)])

    proposed = state.proposed_result_from_snapshot(
        "12608260578",
        [8, 17, *([1] * 8)],
    )

    assert proposed is None
    assert state.results[-1] == ("12608260576", 1)
    assert state.incomplete_missing_draw_ids("12608260578") == ("12608260577",)


def test_later_history_values_cannot_overwrite_a_checkpointed_draw():
    state = SessionState(draw_count=SESSION_DRAW_COUNT)
    start = 12608270881
    state.start(str(start))
    state.commit_results(
        [
            (str(start + offset), 8 if offset == 8 else 1)
            for offset in range(9)
        ]
    )

    proposed = state.proposed_result_from_snapshot(
        "12608270890",
        [15, 14, 8, *([1] * 7)],
    )

    assert proposed is not None
    assert dict(proposed)["12608270889"] == 8
    assert dict(proposed)["12608270890"] == 15


def test_state_marks_all_missing_draws_as_incomplete_at_session_end():
    state = SessionState(draw_count=SESSION_DRAW_COUNT)
    start = 12608260571
    state.start(str(start))
    state.commit_results([(str(start + offset), 1) for offset in range(6)])

    assert state.incomplete_missing_draw_ids("12608260581") == (
        *(str(draw_id) for draw_id in range(12608260577, 12608260581)),
    )


def test_state_keeps_the_first_checkpointed_value_for_a_duplicate_draw():
    state = SessionState(draw_count=SESSION_DRAW_COUNT)
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

    state = SessionState(draw_count=SESSION_DRAW_COUNT)
    state.start("12608180151")
    state.commit_results(
        [
            (str(12608180151 + offset), offset % 19)
            for offset in range(SESSION_DRAW_COUNT)
        ]
    )
    assert state.is_complete()


def test_state_cannot_complete_when_ten_results_include_a_wrong_draw_id():
    state = SessionState(draw_count=SESSION_DRAW_COUNT)
    start = 12608180151
    state.start(str(start))
    state.commit_results(
        [
            (str(start + offset), offset % 19)
            for offset in range(SESSION_DRAW_COUNT - 1)
        ]
    )

    assert state.proposed_results(str(start + SESSION_DRAW_COUNT), 3) is None
    assert not state.is_complete()
