from analytics.analyzers.gaps import GapAnalyzer


def test_current_gap_is_zero_when_number_is_latest():
    result = GapAnalyzer().analyze([1, 5, 7, 3, 7])
    assert result.current_gaps[7] == 0


def test_current_gap_counts_draws_since_latest_appearance():
    result = GapAnalyzer().analyze([7, 1, 2, 3, 4])
    assert result.current_gaps[7] == 4
    assert result.current_gaps[4] == 0


def test_example_3_5_9_3_has_last_gap_two_and_current_zero():
    result = GapAnalyzer().analyze([3, 5, 9, 3])
    assert result.current_gaps[3] == 0
    assert result.last_gaps[3] == 2
    assert result.longest_gaps[3] == 2


def test_last_gap_uses_two_most_recent_occurrences():
    result = GapAnalyzer().analyze([3, 1, 2, 3, 4, 3])
    assert result.last_gaps[3] == 1
    assert result.current_gaps[3] == 0


def test_longest_gap_includes_leading_internal_and_trailing_runs():
    result = GapAnalyzer().analyze([1, 2, 1, 3, 4, 5])
    assert result.longest_gaps[1] == 3
    assert result.longest_gaps[6] == 6
    assert result.current_gaps[6] == 6
    assert result.last_gaps[6] is None


def test_live_gap_helpers():
    numbers = [3, 5, 9, 3]
    assert GapAnalyzer.current_gap(numbers, 3) == 0
    assert GapAnalyzer.current_gap(numbers, 5) == 2
    assert GapAnalyzer.current_gap(numbers, 0) == 4
    assert GapAnalyzer.last_gap(numbers, 3) == 2
    assert GapAnalyzer.last_gap(numbers, 5) is None


def test_empty_session():
    result = GapAnalyzer().analyze([])
    assert all(result.current_gaps[n] == 0 for n in range(19))
    assert all(result.last_gaps[n] is None for n in range(19))
    assert all(result.longest_gaps[n] == 0 for n in range(19))
    assert result.largest_gap == 0
    assert result.gap_leaders == list(range(19))
