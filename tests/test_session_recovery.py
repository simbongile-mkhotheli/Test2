from config import SESSION_DRAW_COUNT
from tracker.session_manager import SessionManager
from storage.storage import Storage
from models.models import Snapshot


def configure_session_storage(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.storage.RESULTS_FILE", tmp_path / "results.txt")
    monkeypatch.setattr("storage.storage.SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(
        "storage.storage.ACTIVE_SESSION_FILE",
        tmp_path / "sessions" / ".active-session.json",
    )


def add_snapshot_result(manager: SessionManager, draw_id: str, result: int) -> None:
    manager.add_snapshot(
        Snapshot(
            draw_id=draw_id,
            latest=result,
            history=[result],
        )
    )


def test_session_manager_resumes_interrupted_partial_session(tmp_path, monkeypatch):
    configure_session_storage(tmp_path, monkeypatch)
    results = [
        ("12608180151", 15),
        ("12608180152", 16),
    ]
    Storage().checkpoint_session("draw-12608180151", "12608180151", results)

    manager = SessionManager()

    assert manager.is_running()
    assert manager.start_draw_id == "12608180151"
    assert manager.results == results
    assert manager.last_draw_id() == "12608180152"
    assert manager.last_history() is None


def test_session_manager_finalizes_completed_checkpoint_on_startup(tmp_path, monkeypatch):
    configure_session_storage(tmp_path, monkeypatch)
    results = [
        (str(12608180151 + offset), offset % 19)
        for offset in range(SESSION_DRAW_COUNT)
    ]
    Storage().checkpoint_session("draw-12608180151", "12608180151", results)

    manager = SessionManager()

    assert not manager.is_running()
    assert manager.results == []
    assert not (tmp_path / "sessions" / ".active-session.json").exists()
    assert (tmp_path / "sessions" / "draw-12608180151.txt").exists()
    assert (tmp_path / "results.txt").read_text(encoding="utf-8") == ""


def test_session_manager_continues_a_restored_session_after_skipped_draw_ids(
    tmp_path,
    monkeypatch,
):
    configure_session_storage(tmp_path, monkeypatch)
    manager = SessionManager()
    manager.start("12608180151")
    add_snapshot_result(manager, "12608180151", 15)

    add_snapshot_result(manager, "12608180153", 14)

    assert manager.is_running()
    assert manager.results == [
        ("12608180151", 15),
        ("12608180153", 14),
    ]


def test_session_manager_records_only_the_current_draw_from_a_verified_snapshot(
    tmp_path,
    monkeypatch,
):
    configure_session_storage(tmp_path, monkeypatch)
    manager = SessionManager()
    start = 12608260571
    manager.start(str(start))
    for offset in range(6):
        add_snapshot_result(manager, str(start + offset), 1)

    update = manager.add_snapshot(
        Snapshot(
            draw_id="12608260578",
            latest=8,
            history=[8, 17, *([1] * 8)],
        )
    )

    assert update.captured_current_draw
    assert manager.results[-1] == ("12608260578", 8)
    assert "12608260577" in manager.missing_draw_ids


def test_restored_session_keeps_missing_ids_missing_without_draw_id_history(
    tmp_path,
    monkeypatch,
):
    configure_session_storage(tmp_path, monkeypatch)
    start = 12608260571
    results = [(str(start + offset), 1) for offset in range(6)]
    results.append(("12608260578", 8))
    Storage().checkpoint_session("draw-12608260571", str(start), results)

    manager = SessionManager()
    update = manager.add_snapshot(
        Snapshot(
            draw_id="12608260579",
            latest=4,
            history=[4, 8, 17, *([1] * 7)],
        )
    )

    assert update.captured_current_draw
    assert manager.results[-2:] == [
        ("12608260578", 8),
        ("12608260579", 4),
    ]
    assert "12608260577" in manager.missing_draw_ids


def test_session_manager_preserves_an_unrecoverable_partial_session(
    tmp_path,
    monkeypatch,
):
    configure_session_storage(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "storage.storage.INCOMPLETE_SESSIONS_DIR",
        tmp_path / "sessions" / "incomplete",
    )
    manager = SessionManager()
    start = 12608260571
    manager.start(str(start))
    for offset in range(6):
        add_snapshot_result(manager, str(start + offset), 1)

    update = manager.add_snapshot(
        Snapshot(
            draw_id="12608260581",
            latest=2,
            history=[2] * 10,
        )
    )
    archive = manager.preserve_incomplete(
        "12608260581",
        update.unavailable_draw_ids,
    )

    assert update.unavailable_draw_ids == (
        *(str(draw_id) for draw_id in range(12608260577, 12608260581)),
    )
    assert archive is not None
    assert archive.exists()
    assert not manager.is_running()
    assert not (tmp_path / "sessions" / ".active-session.json").exists()
    assert (tmp_path / "results.txt").read_text(encoding="utf-8") == ""
