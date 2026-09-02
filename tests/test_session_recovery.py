from config import SESSION_DRAW_COUNT
from tracker.session_presenter import SessionPresenter
from tracker.session_manager import SessionManager
from storage.storage import Storage
from models.models import Snapshot
from ui.events import EventBus


def configure_session_storage(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.storage.RESULTS_FILE", tmp_path / "results.txt")
    monkeypatch.setattr("storage.storage.TENDENCIES_FILE", tmp_path / "tendencies.txt")
    monkeypatch.setattr("storage.storage.SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(
        "storage.storage.ACTIVE_SESSION_FILE",
        tmp_path / "sessions" / ".active-session.json",
    )


def add_snapshot_result(manager: SessionManager, draw_id: str, result: int):
    return manager.add_snapshot(
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


def test_session_manager_does_not_append_later_draws_after_a_skip(
    tmp_path,
    monkeypatch,
):
    configure_session_storage(tmp_path, monkeypatch)
    manager = SessionManager()
    manager.start("12608180151")
    add_snapshot_result(manager, "12608180151", 15)

    update = add_snapshot_result(manager, "12608180153", 14)

    assert manager.is_running()
    assert not update.captured_current_draw
    assert update.unavailable_draw_ids == ("12608180152",)
    assert manager.results == [("12608180151", 15)]


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

    assert not update.captured_current_draw
    assert update.unavailable_draw_ids == ("12608260577",)
    assert manager.results[-1] == ("12608260576", 1)


def test_restored_sparse_checkpoint_is_archived_without_resuming(
    tmp_path,
    monkeypatch,
):
    configure_session_storage(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "storage.storage.INCOMPLETE_SESSIONS_DIR",
        tmp_path / "sessions" / "incomplete",
    )
    start = 12608260571
    results = [(str(start + offset), 1) for offset in range(6)]
    results.append(("12608260578", 8))
    Storage().checkpoint_session("draw-12608260571", str(start), results)

    manager = SessionManager()

    assert not manager.is_running()
    assert manager.results == []
    assert not (tmp_path / "sessions" / ".active-session.json").exists()
    archive = tmp_path / "sessions" / "incomplete" / (
        "draw-12608260571-observed-12608260578.json"
    )
    assert archive.exists()


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


def _save_completed_session_with_red_position(
    session_name: str,
    start_draw_id: int,
    red_position: int,
):
    Storage().save_session(
        session_name,
        SessionPresenter().report(
            session_name,
            [
                (
                    str(start_draw_id + offset),
                    3 if offset == red_position - 1 else 1,
                )
                for offset in range(SESSION_DRAW_COUNT)
            ],
        ),
    )


def test_session_manager_alerts_before_a_position_red_in_two_prior_sessions(
    tmp_path,
    monkeypatch,
):
    configure_session_storage(tmp_path, monkeypatch)
    _save_completed_session_with_red_position("draw-12608180151", 12608180151, 2)
    _save_completed_session_with_red_position("draw-12608180161", 12608180161, 2)
    events = EventBus()
    manager = SessionManager(events)
    manager.start("12608180171")
    add_snapshot_result(manager, "12608180171", 1)

    alerts = [event for event in events.drain() if event.kind == "alert"]

    assert len(alerts) == 1
    assert alerts[0].payload["alert_type"] == "POSITION_COLOR"
    assert "Position 2 was Red" in alerts[0].payload["message"]
    assert "draw-12608180151" in alerts[0].payload["message"]
    assert "draw-12608180161" in alerts[0].payload["message"]
    assert manager.results == [("12608180171", 1)]


def test_position_alert_continues_when_the_current_session_keeps_the_pattern(
    tmp_path,
    monkeypatch,
):
    configure_session_storage(tmp_path, monkeypatch)
    _save_completed_session_with_red_position("draw-12608180151", 12608180151, 2)
    _save_completed_session_with_red_position("draw-12608180161", 12608180161, 2)
    manager = SessionManager()
    manager.start("12608180171")
    for offset in range(SESSION_DRAW_COUNT):
        add_snapshot_result(
            manager,
            str(12608180171 + offset),
            3 if offset == 1 else 1,
        )
    manager.finish()

    events = EventBus()
    manager = SessionManager(events)
    manager.start("12608180181")
    add_snapshot_result(manager, "12608180181", 1)

    alerts = [event for event in events.drain() if event.kind == "alert"]
    assert len(alerts) == 1
    assert "Position 2 was Red" in alerts[0].payload["message"]
    assert "draw-12608180161" in alerts[0].payload["message"]
    assert "draw-12608180171" in alerts[0].payload["message"]


def test_position_alert_resets_when_the_latest_session_breaks_the_pattern(
    tmp_path,
    monkeypatch,
):
    configure_session_storage(tmp_path, monkeypatch)
    _save_completed_session_with_red_position("draw-12608180151", 12608180151, 2)
    _save_completed_session_with_red_position("draw-12608180161", 12608180161, 2)
    manager = SessionManager()
    manager.start("12608180171")
    for offset in range(SESSION_DRAW_COUNT):
        add_snapshot_result(
            manager,
            str(12608180171 + offset),
            1,
        )
    manager.finish()

    events = EventBus()
    manager = SessionManager(events)
    manager.start("12608180181")
    add_snapshot_result(manager, "12608180181", 1)

    assert not [event for event in events.drain() if event.kind == "alert"]


def test_session_manager_publishes_next_position_history_from_all_prior_sessions(
    tmp_path,
    monkeypatch,
):
    configure_session_storage(tmp_path, monkeypatch)
    for start_draw_id, third_result in ((12608180151, 3), (12608180161, 7)):
        session_name = f"draw-{start_draw_id}"
        Storage().save_session(
            session_name,
            SessionPresenter().report(
                session_name,
                [
                    (str(start_draw_id + offset), 3 if offset == 0 else 1)
                    if offset < 2
                    else (str(start_draw_id + offset), third_result)
                    if offset == 2
                    else (str(start_draw_id + offset), 1)
                    for offset in range(SESSION_DRAW_COUNT)
                ],
            ),
        )

    events = EventBus()
    manager = SessionManager(events)
    manager.start("12608180171")
    add_snapshot_result(manager, "12608180171", 3)
    add_snapshot_result(manager, "12608180172", 1)

    tendency = [
        event
        for event in events.drain()
        if event.kind == "tendency_update"
    ][0]
    assert "Position 3 after Red → Black" in tendency.payload["color"]
    assert "2 matching sessions" in tendency.payload["color"]
    assert "Black 50% (1)" in tendency.payload["color"]
    assert "Red 50% (1)" in tendency.payload["color"]


def test_session_manager_records_resolved_tendencies_after_the_target_draw(
    tmp_path,
    monkeypatch,
):
    configure_session_storage(tmp_path, monkeypatch)
    for start_draw_id, third_result in ((12608180151, 3), (12608180161, 2)):
        session_name = f"draw-{start_draw_id}"
        Storage().save_session(
            session_name,
            SessionPresenter().report(
                session_name,
                [
                    (str(start_draw_id + offset), 3 if offset == 0 else 1)
                    if offset < 2
                    else (str(start_draw_id + offset), third_result)
                    if offset == 2
                    else (str(start_draw_id + offset), 1)
                    for offset in range(SESSION_DRAW_COUNT)
                ],
            ),
        )

    manager = SessionManager()
    manager.start("12608180171")
    add_snapshot_result(manager, "12608180171", 3)
    add_snapshot_result(manager, "12608180172", 1)
    add_snapshot_result(manager, "12608180173", 3)

    log = (tmp_path / "tendencies.txt").read_text(encoding="utf-8")
    assert "draw-12608180171 | 3 | Color | Red -> Black | 2" in log
    assert "Red | CORRECT | 1" in log
    assert "draw-12608180171 | 3 | Range | 1-6 -> 1-6 | 2" in log
    assert "1-6 | CORRECT | 1" in log
