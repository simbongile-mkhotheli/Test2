import pytest
from models.models import Result, Snapshot
from models.number_domain import (
    NUMBER_BANDS,
    NUMBER_VALUES,
    is_valid_number,
    number_band,
    number_counts,
    validate_number,
)
from storage.storage import Storage
from tracker.game_reader import GameReader
from tracker.session_manager import SessionManager


@pytest.mark.parametrize("number", NUMBER_VALUES)
def test_accepts_every_valid_game_number(number):
    assert is_valid_number(number)
    assert validate_number(number) == number


@pytest.mark.parametrize("value", [-1, 19, "7", True, None])
def test_rejects_values_outside_the_game_number_domain(value):
    assert not is_valid_number(value)
    with pytest.raises(ValueError, match="0 to 18"):
        validate_number(value)


def test_number_bands_cover_each_non_zero_valid_number_once():
    membership_count = {
        number: sum(number in band for _, band in NUMBER_BANDS)
        for number in range(1, 19)
    }
    assert membership_count == {number: 1 for number in range(1, 19)}


def test_zero_is_valid_but_excluded_from_the_range_trend():
    assert is_valid_number(0)
    assert number_band(0) is None


def test_number_counts_include_zero_and_all_domain_values():
    counts = number_counts([0, 0, 6, 18])

    assert counts[0] == 2
    assert counts[6] == 1
    assert counts[18] == 1
    assert counts[1] == 0


def test_result_model_rejects_invalid_result_number():
    with pytest.raises(ValueError, match="0 to 18"):
        Result(draw_id="12608180151", number=-1)


def test_game_reader_rejects_snapshot_with_invalid_history_value():
    reader = GameReader.__new__(GameReader)
    snapshot = Snapshot(
        draw_id="12608180151",
        timer=10,
        latest=19,
        history=[19] * 10,
    )

    assert not reader.valid_snapshot(snapshot)


def test_storage_rejects_invalid_result_before_writing(tmp_path, monkeypatch):
    monkeypatch.setattr("storage.storage.RESULTS_FILE", tmp_path / "results.txt")
    storage = Storage()

    with pytest.raises(ValueError, match="0 to 18"):
        storage.append_result("12608180151", 19)


def test_storage_rejects_invalid_historical_result(tmp_path, monkeypatch):
    results_file = tmp_path / "results.txt"
    results_file.write_text("12608180151,19\n", encoding="utf-8")
    monkeypatch.setattr("storage.storage.RESULTS_FILE", results_file)

    with pytest.raises(ValueError, match="0 to 18"):
        Storage().read_results()


def test_session_manager_rejects_invalid_result_before_persisting(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "storage.storage.ACTIVE_SESSION_FILE",
        tmp_path / ".active-session.json",
    )
    manager = SessionManager()
    manager.start("12608180151")
    manager.storage.checkpoint_session = lambda *_: pytest.fail(
        "invalid result was persisted"
    )

    with pytest.raises(ValueError, match="0 to 18"):
        manager.add_result("12608180151", 19)
