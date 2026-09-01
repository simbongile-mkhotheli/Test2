from tracker.session_manager import SESSION_DRAW_COUNT, SessionManager
from tracker.session_state import SessionState
from models.models import Snapshot


def make_manager(tmp_path, monkeypatch) -> SessionManager:
    monkeypatch.setattr("storage.storage.RESULTS_FILE", tmp_path / "results.txt")
    monkeypatch.setattr(
        "storage.storage.ACTIVE_SESSION_FILE",
        tmp_path / ".active-session.json",
    )
    return SessionManager()


def add_snapshot_result(manager: SessionManager, draw_id: str, result: int):
    return manager.add_snapshot(
        Snapshot(
            draw_id=draw_id,
            latest=result,
            history=[result],
        )
    )


def test_draw_position_uses_last_digit():
    assert SessionState.draw_position("12608180151") == 1
    assert SessionState.draw_position("12608180160") == 0
    assert SessionState.draw_position("12608180169") == 9


def test_session_starts_only_on_draw_id_ending_in_one():
    assert SessionState.is_session_start_draw("12608180151")
    assert not SessionState.is_session_start_draw("12608180150")
    assert not SessionState.is_session_start_draw("12608180152")


def test_session_ends_only_after_every_required_draw_id_is_present(tmp_path, monkeypatch):
    manager = make_manager(tmp_path, monkeypatch)
    start_draw_id = "12608180151"
    manager.start(start_draw_id)

    for offset in range(SESSION_DRAW_COUNT - 1):
        add_snapshot_result(
            manager,
            str(int(start_draw_id) + offset),
            offset % 19,
        )

    assert not manager.is_complete()

    add_snapshot_result(
        manager,
        str(int(start_draw_id) + SESSION_DRAW_COUNT - 1),
        3,
    )
    assert len(manager.results) == SESSION_DRAW_COUNT
    assert manager.is_complete()


def test_session_keeps_a_partial_session_when_a_draw_id_is_missing(
    tmp_path,
    monkeypatch,
):
    manager = make_manager(tmp_path, monkeypatch)
    manager.start("12608180151")
    manager.storage.checkpoint_session = lambda *args: None

    add_snapshot_result(manager, "12608180151", 15)
    update = add_snapshot_result(manager, "12608180153", 14)

    assert not update.captured_current_draw
    assert update.unavailable_draw_ids == ("12608180152",)
    assert manager.results == [("12608180151", 15)]
