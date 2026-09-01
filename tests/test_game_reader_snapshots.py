import pytest

import tracker.game_reader as game_reader_module
from exceptions import SnapshotTimeout, TrackerStopped
from models.models import Snapshot
from tracker.game_reader import GameReader


def make_snapshot(draw_id: str, history: list[int]) -> Snapshot:
    return Snapshot(
        draw_id=draw_id,
        latest=history[0],
        history=history,
    )


def test_stable_snapshot_requires_the_expected_draw_id(monkeypatch):
    reader = GameReader.__new__(GameReader)
    reader.snapshot = lambda: make_snapshot("12608180152", [2] * 10)
    monkeypatch.setattr(game_reader_module, "sleep", lambda _: None)

    assert reader.stable_snapshot("12608180151", (1,) * 10) is None


def test_stable_snapshot_requires_history_to_change(monkeypatch):
    reader = GameReader.__new__(GameReader)
    reader.snapshot = lambda: make_snapshot("12608180152", [1] * 10)
    monotonic_values = iter([0.0, 0.0, 1.0])

    monkeypatch.setattr(game_reader_module, "monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr(game_reader_module, "sleep", lambda _: None)
    monkeypatch.setattr(game_reader_module, "SNAPSHOT_STABILITY_TIMEOUT", 1.0)

    with pytest.raises(SnapshotTimeout, match="12608180152"):
        reader.stable_snapshot("12608180152", (1,) * 10)


def test_stable_snapshot_returns_after_three_matching_verified_reads(monkeypatch):
    reader = GameReader.__new__(GameReader)
    snapshot = make_snapshot("12608180152", [2, *([1] * 9)])
    reader.snapshot = lambda: snapshot
    monkeypatch.setattr(game_reader_module, "sleep", lambda _: None)

    assert reader.stable_snapshot(
        "12608180152",
        (1,) * 10,
        "12608180151",
    ) == snapshot


def test_stable_snapshot_rejects_history_that_does_not_roll_forward(monkeypatch):
    reader = GameReader.__new__(GameReader)
    reader.snapshot = lambda: make_snapshot("12608180152", [2, *([3] * 9)])
    monotonic_values = iter([0.0, 0.0, 1.0])

    monkeypatch.setattr(game_reader_module, "monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr(game_reader_module, "sleep", lambda _: None)
    monkeypatch.setattr(game_reader_module, "SNAPSHOT_STABILITY_TIMEOUT", 1.0)

    with pytest.raises(SnapshotTimeout, match="12608180152"):
        reader.stable_snapshot(
            "12608180152",
            (1,) * 10,
            "12608180151",
        )


def test_wait_for_new_draw_retries_when_the_observed_draw_advances(monkeypatch):
    reader = GameReader.__new__(GameReader)
    observed_draws = iter(["12608180151", "12608180152"])
    verified_snapshot = make_snapshot("12608180152", [2] * 10)
    attempted_draws = []

    reader.draw_id = lambda: next(observed_draws)

    def stable_snapshot(expected_draw, previous_history, previous_draw, should_stop):
        attempted_draws.append((expected_draw, previous_history, previous_draw))
        assert should_stop is None
        return None if expected_draw.endswith("51") else verified_snapshot

    reader.stable_snapshot = stable_snapshot
    monkeypatch.setattr(game_reader_module, "sleep", lambda _: None)

    assert reader.wait_for_new_draw("12608180150", (1,) * 10) == verified_snapshot
    assert attempted_draws == [
        ("12608180151", (1,) * 10, "12608180150"),
        ("12608180152", (1,) * 10, "12608180150"),
    ]


def test_wait_for_new_draw_honors_a_dashboard_stop_request():
    reader = GameReader.__new__(GameReader)

    with pytest.raises(TrackerStopped):
        reader.wait_for_new_draw(
            "12608180151",
            should_stop=lambda: True,
        )
