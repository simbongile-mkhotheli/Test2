import pytest

from config import RESULTS_FILE, SESSIONS_DIR
from storage.storage import Storage


def test_default_results_log_is_stored_at_the_project_root():
    assert RESULTS_FILE.parent != SESSIONS_DIR
    assert RESULTS_FILE.name == "results.txt"


def test_results_log_is_a_single_live_table_independent_of_sessions(tmp_path, monkeypatch):
    results_file = tmp_path / "results.txt"
    sessions_dir = tmp_path / "sessions"

    monkeypatch.setattr("storage.storage.RESULTS_FILE", results_file)
    monkeypatch.setattr("storage.storage.SESSIONS_DIR", sessions_dir)

    storage = Storage()

    storage.prepare_live_results_log()
    assert storage.append_live_result("12608180151", 15)
    assert storage.append_live_result("12608180152", 16)
    assert storage.append_live_result("12608180160", 16)

    text = results_file.read_text(encoding="utf-8")

    assert "Pos | Draw ID             | Result" in text
    assert "  1 | 12608180151         |     15" in text
    assert "  2 | 12608180152         |     16" in text
    assert "  3 | 12608180160         |     16" in text
    assert "SESSION" not in text
    assert "COUNTS" not in text


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

    storage.prepare_live_results_log()
    assert results_file.read_text(encoding="utf-8") == (
        "Pos | Draw ID             | Result\n"
        "----+---------------------+-------\n"
        "  1 | 12608180151         |     15\n"
        "  2 | 12608180152         |     16\n"
        "  3 | 12608180153         |     13\n"
    )


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
    storage.checkpoint_session(
        "draw-12608180151",
        "12608180151",
        results,
        (16, 15, 14),
    )

    recovered = storage.load_active_session()

    assert recovered is not None
    assert recovered.name == "draw-12608180151"
    assert recovered.start_draw_id == "12608180151"
    assert recovered.results == results
    assert recovered.last_history == (16, 15, 14)


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


def test_live_results_append_each_new_draw_without_duplicates(tmp_path, monkeypatch):
    results_file = tmp_path / "results.txt"
    monkeypatch.setattr("storage.storage.RESULTS_FILE", results_file)
    storage = Storage()

    assert storage.append_live_result("12608180151", 15)
    assert not storage.append_live_result("12608180151", 15)
    assert storage.append_live_result("12608180152", 16)

    text = results_file.read_text(encoding="utf-8")
    assert text.count("12608180151") == 1
    assert "  1 | 12608180151         |     15" in text
    assert "  2 | 12608180152         |     16" in text


def test_live_results_rejects_conflicting_repeated_draw(tmp_path, monkeypatch):
    results_file = tmp_path / "results.txt"
    monkeypatch.setattr("storage.storage.RESULTS_FILE", results_file)
    storage = Storage()

    storage.append_live_result("12608180151", 15)

    with pytest.raises(ValueError, match="disagrees"):
        storage.append_live_result("12608180151", 16)
