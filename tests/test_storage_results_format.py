from storage.storage import Storage


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
