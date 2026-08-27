import pytest

from config import RESULTS_FILE, SESSIONS_DIR
from storage.storage import Storage


def test_default_results_log_is_stored_at_the_project_root():
    assert RESULTS_FILE.parent != SESSIONS_DIR
    assert RESULTS_FILE.name == "results.txt"


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
    assert "RESULT COUNTS" in text
    assert "     0 |     2" in text
    assert "Total  |    30" in text
    assert "RANGE COUNTS" in text
    assert "1-6   |    12" in text
    assert "7-12  |    10" in text
    assert "13-18 |     6" in text


def test_live_results_append_each_new_draw_without_duplicates(tmp_path, monkeypatch):
    results_file = tmp_path / "results.txt"
    monkeypatch.setattr("storage.storage.RESULTS_FILE", results_file)
    storage = Storage()
    start_draw_id = "12608180151"

    assert storage.append_live_results(
        start_draw_id,
        [(start_draw_id, 15)],
    ) == (start_draw_id,)
    assert storage.append_live_results(
        start_draw_id,
        [(start_draw_id, 15), ("12608180152", 16)],
    ) == ("12608180152",)

    text = results_file.read_text(encoding="utf-8")
    assert text.count("SESSION START : 12608180151") == 1
    assert text.count("12608180151") == 2  # header plus its one result row
    assert "  1 | 12608180151         |     15" in text
    assert "  2 | 12608180152         |     16" in text


def test_incomplete_live_session_is_closed_with_its_counts(tmp_path, monkeypatch):
    results_file = tmp_path / "results.txt"
    monkeypatch.setattr("storage.storage.RESULTS_FILE", results_file)
    storage = Storage()
    results = [("12608180151", 0), ("12608180152", 15)]

    storage.append_live_results("12608180151", results)
    storage.mark_live_session_incomplete(
        "12608180151",
        results,
        "12608180180",
        ("12608180153",),
    )

    text = results_file.read_text(encoding="utf-8")
    assert "RESULT COUNTS" in text
    assert "     0 |     1" in text
    assert "    15 |     1" in text
    assert "Total  |     2" in text
    assert "RANGE COUNTS" in text
    assert "13-18 |     1" in text
    assert "Missing draw IDs : 12608180153" in text
    assert "SESSION INCOMPLETE" in text
