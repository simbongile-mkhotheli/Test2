import pytest

from config import RESULTS_FILE, SESSIONS_DIR
from storage.storage import Storage
from tracker.session_presenter import SessionPresenter


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


def test_tendency_log_records_tied_outcomes_and_tracks_a_pattern_streak(
    tmp_path,
    monkeypatch,
):
    color_tendencies_file = tmp_path / "color_tendencies.txt"
    monkeypatch.setattr("storage.storage.RESULTS_FILE", tmp_path / "results.txt")
    monkeypatch.setattr(
        "storage.storage.COLOR_TENDENCIES_FILE",
        color_tendencies_file,
    )
    storage = Storage()
    outcomes = (("Black", 0), ("Gray", 1), ("Red", 1), ("Zero", 0))

    assert storage.append_tendency_evaluation(
        "draw-12608180171",
        3,
        "Color",
        ("Red", "Black"),
        2,
        outcomes,
        "Red",
        "CORRECT",
    )
    assert storage.append_tendency_evaluation(
        "draw-12608180181",
        3,
        "Color",
        ("Red", "Black"),
        2,
        outcomes,
        "Gray",
        "CORRECT",
    )
    assert storage.append_tendency_evaluation(
        "draw-12608180191",
        3,
        "Color",
        ("Red", "Black"),
        2,
        outcomes,
        "Black",
        "INCORRECT",
    )
    assert not storage.append_tendency_evaluation(
        "draw-12608180191",
        3,
        "Color",
        ("Red", "Black"),
        2,
        outcomes,
        "Black",
        "INCORRECT",
    )

    rows = color_tendencies_file.read_text(encoding="utf-8")
    assert "Previous two | Matches | Distribution" in rows
    table_lines = rows.splitlines()
    assert "+" in table_lines[1]
    assert [field.strip() for field in table_lines[2].split(" | ")] == [
        "draw-12608180171",
        "3",
        "Red -> Black",
        "2",
        "Black 0%, Gray 50%, Red 50%, Zero 0%",
        "Red",
        "CORRECT",
        "1",
    ]
    assert [field.strip() for field in table_lines[3].split(" | ")][-3:] == [
        "Gray",
        "CORRECT",
        "2",
    ]
    assert [field.strip() for field in table_lines[4].split(" | ")][-3:] == [
        "Black",
        "INCORRECT",
        "0",
    ]
    assert sum("draw-12608180191" in line for line in table_lines) == 1


def test_legacy_combined_tendency_log_is_split_without_losing_rows(
    tmp_path,
    monkeypatch,
):
    legacy_file = tmp_path / "tendencies.txt"
    color_file = tmp_path / "color_tendencies.txt"
    range_file = tmp_path / "range_tendencies.txt"
    monkeypatch.setattr("storage.storage.RESULTS_FILE", tmp_path / "results.txt")
    monkeypatch.setattr("storage.storage.LEGACY_TENDENCIES_FILE", legacy_file)
    monkeypatch.setattr("storage.storage.COLOR_TENDENCIES_FILE", color_file)
    monkeypatch.setattr("storage.storage.RANGE_TENDENCIES_FILE", range_file)
    legacy_file.write_text(
        "Session | Pos | Type | Previous two | Matches | Distribution | Actual | Verdict | Correct streak\n"
        "--------+-----+------+--------------+---------+--------------+--------+---------+---------------\n"
        "draw-12608180171 | 3 | Color | Red -> Black | 2 | Red 50%, Gray 50% | Red | CORRECT | 1\n"
        "draw-12608180171 | 3 | Range | 1-6 -> 7-12 | 2 | 1-6 50%, 7-12 50% | 1-6 | CORRECT | 1\n",
        encoding="utf-8",
    )

    Storage()

    assert "Red -> Black" in color_file.read_text(encoding="utf-8")
    assert "1-6 -> 7-12" in range_file.read_text(encoding="utf-8")
    assert not legacy_file.exists()
    assert (tmp_path / "tendencies.legacy.txt").exists()


def test_storage_reads_the_two_consecutive_sessions_before_the_current_one(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr("storage.storage.RESULTS_FILE", tmp_path / "results.txt")
    monkeypatch.setattr("storage.storage.SESSIONS_DIR", tmp_path / "sessions")
    storage = Storage()
    presenter = SessionPresenter()

    storage.save_session(
        "draw-12608180151",
        presenter.report(
            "draw-12608180151",
            [
                (str(12608180151 + offset), (offset + 1) % 19)
                for offset in range(10)
            ],
        ),
    )
    storage.save_session(
        "draw-12608180161",
        presenter.report(
            "draw-12608180161",
            [
                (str(12608180161 + offset), (offset + 2) % 19)
                for offset in range(10)
            ],
        ),
    )

    previous = storage.two_consecutive_completed_sessions_before("12608180171")

    assert previous is not None
    older, newer = previous
    assert older.name == "draw-12608180151"
    assert newer.name == "draw-12608180161"
    assert newer.results == tuple(
        (str(12608180161 + offset), (offset + 2) % 19)
        for offset in range(10)
    )
    assert [
        session.name
        for session in storage.completed_sessions_before("12608180171")
    ] == ["draw-12608180151", "draw-12608180161"]


def test_storage_resets_the_position_pattern_when_a_prior_session_is_missing(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr("storage.storage.RESULTS_FILE", tmp_path / "results.txt")
    monkeypatch.setattr("storage.storage.SESSIONS_DIR", tmp_path / "sessions")
    storage = Storage()
    session = "draw-12608180161"
    storage.save_session(
        session,
        SessionPresenter().report(
            session,
            [(str(12608180161 + offset), 3) for offset in range(10)],
        ),
    )

    assert storage.two_consecutive_completed_sessions_before("12608180171") is None
