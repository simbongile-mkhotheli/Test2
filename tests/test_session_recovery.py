import json

import pytest

from exceptions import SessionGap
from tracker.session_manager import SessionManager
from storage.storage import Storage


def configure_session_storage(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.storage.RESULTS_FILE", tmp_path / "results.txt")
    monkeypatch.setattr("storage.storage.SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(
        "storage.storage.ACTIVE_SESSION_FILE",
        tmp_path / "sessions" / ".active-session.json",
    )
    monkeypatch.setattr(
        "storage.storage.ABANDONED_SESSIONS_DIR",
        tmp_path / "sessions" / "abandoned",
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


def test_session_manager_finalizes_completed_checkpoint_on_startup(tmp_path, monkeypatch):
    configure_session_storage(tmp_path, monkeypatch)
    results = [
        (str(12608180151 + offset), offset % 19)
        for offset in range(30)
    ]
    Storage().checkpoint_session("draw-12608180151", "12608180151", results)

    manager = SessionManager()

    assert not manager.is_running()
    assert manager.results == []
    assert not (tmp_path / "sessions" / ".active-session.json").exists()
    assert (tmp_path / "sessions" / "draw-12608180151.txt").exists()
    assert "SESSION START : 12608180151" in (tmp_path / "results.txt").read_text(
        encoding="utf-8"
    )


def test_session_gap_archives_checkpoint_and_returns_to_waiting(tmp_path, monkeypatch):
    configure_session_storage(tmp_path, monkeypatch)
    manager = SessionManager()
    manager.start("12608180151")
    manager.add_result("12608180151", 15)

    with pytest.raises(SessionGap) as error:
        manager.add_result("12608180153", 14)

    archived_path = manager.abandon(str(error.value), error.value.observed_draw_id)

    assert not manager.is_running()
    assert manager.results == []
    assert not (tmp_path / "sessions" / ".active-session.json").exists()
    assert archived_path == (
        tmp_path / "sessions" / "abandoned" / "draw-12608180151-after-12608180151.json"
    )
    payload = json.loads(archived_path.read_text(encoding="utf-8"))
    assert payload["status"] == "abandoned"
    assert payload["observed_draw_id"] == "12608180153"
    assert payload["results"] == [["12608180151", 15]]
    assert not (tmp_path / "results.txt").exists() or not (tmp_path / "results.txt").read_text(
        encoding="utf-8"
    )
