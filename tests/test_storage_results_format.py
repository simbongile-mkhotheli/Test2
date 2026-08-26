from storage.storage import Storage
import pytest


def test_results_log_groups_sessions(tmp_path, monkeypatch):
    results_file = tmp_path / "results.txt"
    sessions_dir = tmp_path / "sessions"

    monkeypatch.setattr("storage.storage.RESULTS_FILE", results_file)
    monkeypatch.setattr("storage.storage.SESSIONS_DIR", sessions_dir)

    storage = Storage()

    storage.append_result("12608180151", 15)
    storage.append_result("12608180152", 16)
    storage.append_result("12608180160", 16)

    text = results_file.read_text(encoding="utf-8")

    assert "SESSION START : 12608180151" in text
    assert "Pos | Draw ID             | Result" in text
    assert "  1 | 12608180151         |     15" in text
    assert "  2 | 12608180152         |     16" in text
    assert "  0 | 12608180160         |     16" in text
    assert "SESSION END" in text


def test_read_results_supports_new_log_and_legacy_csv(tmp_path, monkeypatch):
    results_file = tmp_path / "results.txt"
    monkeypatch.setattr("storage.storage.RESULTS_FILE", results_file)

    results_file.write_text(
        "SESSION START : 12608180151\n"
        "Pos | Draw ID             | Result\n"
        "----+---------------------+-------\n"
        "  1 | 12608180151         |     15\n"
        "  2 | 12608180152         |     16\n"
        "12608180153,13\n",
        encoding="utf-8",
    )

    storage = Storage()

    assert storage.read_results() == [
        ("12608180151", 15),
        ("12608180152", 16),
        ("12608180153", 13),
    ]


def test_active_session_checkpoint_is_recoverable(tmp_path, monkeypatch):
    results_file = tmp_path / "results.txt"
    active_session_file = tmp_path / "sessions" / ".active-session.json"
    monkeypatch.setattr("storage.storage.RESULTS_FILE", results_file)
    monkeypatch.setattr("storage.storage.ACTIVE_SESSION_FILE", active_session_file)

    storage = Storage()
    results = [
        ("12608180151", 15),
        ("12608180152", 16),
    ]
    storage.checkpoint_session("draw-12608180151", "12608180151", results)

    recovered = storage.load_active_session()

    assert recovered is not None
    assert recovered.name == "draw-12608180151"
    assert recovered.start_draw_id == "12608180151"
    assert recovered.results == results


def test_partial_checkpoint_can_preserve_missing_draw_ids_for_later_recovery(
    tmp_path,
    monkeypatch,
):
    active_session_file = tmp_path / "sessions" / ".active-session.json"
    monkeypatch.setattr("storage.storage.RESULTS_FILE", tmp_path / "results.txt")
    monkeypatch.setattr("storage.storage.ACTIVE_SESSION_FILE", active_session_file)
    storage = Storage()

    results = [
        ("12608180151", 15),
        ("12608180153", 14),
    ]
    storage.checkpoint_session("draw-12608180151", "12608180151", results)

    assert storage.load_active_session().results == results


def test_completed_session_rejects_a_shifted_result_sequence(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.storage.RESULTS_FILE", tmp_path / "results.txt")
    storage = Storage()
    results = [
        (str(12608180151 + offset), offset % 19)
        for offset in range(29)
    ]
    results.append(("12608180181", 3))

    with pytest.raises(ValueError, match="outside the session boundary"):
        storage.append_completed_session(results)


def test_completed_session_log_is_atomic_and_idempotent(tmp_path, monkeypatch):
    results_file = tmp_path / "results.txt"
    monkeypatch.setattr("storage.storage.RESULTS_FILE", results_file)

    storage = Storage()
    results = [
        (str(12608180151 + offset), offset % 19)
        for offset in range(30)
    ]

    storage.append_completed_session(results)
    storage.append_completed_session(results)

    text = results_file.read_text(encoding="utf-8")
    assert text.count("SESSION START : 12608180151") == 1
    assert "  1 | 12608180151         |      0" in text
    assert " 30 | 12608180180         |     10" in text
