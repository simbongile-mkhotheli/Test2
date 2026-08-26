import pytest

from exceptions import SessionGap
from tracker.session_state import SessionState


def test_state_proposes_results_without_mutating_before_persistence():
    state = SessionState(draw_count=30)
    state.start("12608180151")

    proposed = state.proposed_results("12608180151", 15)

    assert state.results == []
    assert proposed == [("12608180151", 15)]

    state.commit_results(proposed)
    assert state.results == proposed


def test_state_rejects_missing_draw_ids():
    state = SessionState(draw_count=30)
    state.start("12608180151")
    state.commit_results(state.proposed_results("12608180151", 15))

    with pytest.raises(SessionGap, match="expected 12608180152"):
        state.proposed_results("12608180153", 14)


def test_state_completion_is_a_domain_rule():
    state = SessionState(draw_count=3)
    state.start("12608180151")
    for draw_id, result in [
        ("12608180151", 1),
        ("12608180152", 2),
        ("12608180153", 3),
    ]:
        state.commit_results(state.proposed_results(draw_id, result))

    assert not state.is_complete()

    state = SessionState(draw_count=30)
    state.start("12608180151")
    state.commit_results(
        [(str(12608180151 + offset), offset % 19) for offset in range(30)]
    )
    assert state.is_complete()
