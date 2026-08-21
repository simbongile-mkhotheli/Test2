from tracker.session_manager import SESSION_DRAW_COUNT, SessionManager


def test_draw_position_uses_last_digit():
    assert SessionManager.draw_position("12608180151") == 1
    assert SessionManager.draw_position("12608180160") == 0
    assert SessionManager.draw_position("12608180169") == 9


def test_session_starts_only_on_draw_id_ending_in_one():
    assert SessionManager.is_session_start_draw("12608180151")
    assert not SessionManager.is_session_start_draw("12608180150")
    assert not SessionManager.is_session_start_draw("12608180152")


def test_session_ends_only_on_thirtieth_draw_at_zero():
    manager = SessionManager()
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


def test_wrong_end_position_does_not_complete():
    manager = SessionManager()
    manager.start_draw_id = "12608180151"
    manager.running = True
    manager.results = [
        (f"126081801{51 + i:02d}", i % 19)
        for i in range(29)
    ]
    manager.results.append(("12608180181", 3))

    assert not manager.is_complete()


def test_session_requires_consecutive_draw_ids():
    manager = SessionManager()
    manager.start_draw_id = "12608180151"
    manager.running = True
    manager.add_result = manager.add_result.__get__(manager)


def test_session_requires_consecutive_draw_ids(monkeypatch):
    manager = SessionManager()
    manager.start_draw_id = "12608180151"
    manager.running = True
    manager.storage.append_result = lambda *args: None

    manager.add_result("12608180151", 15)

    try:
        manager.add_result("12608180153", 14)
    except ValueError as exc:
        assert "expected 12608180152" in str(exc)
    else:
        raise AssertionError("Expected non-consecutive draw ID to be rejected")
