from tracker.session_manager import SESSION_DRAW_COUNT, SessionManager


def make_manager(tmp_path, monkeypatch) -> SessionManager:
    monkeypatch.setattr("storage.storage.RESULTS_FILE", tmp_path / "results.txt")
    monkeypatch.setattr(
        "storage.storage.ACTIVE_SESSION_FILE",
        tmp_path / ".active-session.json",
    )
    return SessionManager()


def test_draw_position_uses_last_digit():
    assert SessionManager.draw_position("12608180151") == 1
    assert SessionManager.draw_position("12608180160") == 0
    assert SessionManager.draw_position("12608180169") == 9


def test_session_starts_only_on_draw_id_ending_in_one():
    assert SessionManager.is_session_start_draw("12608180151")
    assert not SessionManager.is_session_start_draw("12608180150")
    assert not SessionManager.is_session_start_draw("12608180152")


def test_session_ends_only_after_every_required_draw_id_is_present(tmp_path, monkeypatch):
    manager = make_manager(tmp_path, monkeypatch)
    manager.start_draw_id = "12608180151"
    manager.running = True

    manager.results = [
        (f"126081801{51 + i:02d}", i % 19)
        for i in range(29)
    ]

    assert not manager.is_complete()

    manager.results.append(("12608180180", 3))
    assert len(manager.results) == SESSION_DRAW_COUNT
    assert manager.is_complete()


def test_session_keeps_a_partial_session_when_a_draw_id_is_missing(
    tmp_path,
    monkeypatch,
):
    manager = make_manager(tmp_path, monkeypatch)
    manager.start_draw_id = "12608180151"
    manager.running = True
    manager.storage.checkpoint_session = lambda *args: None

    manager.add_result("12608180151", 15)
    manager.add_result("12608180153", 14)

    assert manager.results == [
        ("12608180151", 15),
        ("12608180153", 14),
    ]
    assert manager.missing_draw_ids[0] == "12608180152"
