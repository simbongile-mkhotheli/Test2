from tracker.session_tendency import SessionTendencyAnalyzer


def test_tendency_uses_matching_prefixes_and_reports_the_next_distribution():
    analyzer = SessionTendencyAnalyzer()
    current_results = [("12608180171", 3), ("12608180172", 1)]
    completed_sessions = (
        (("12608180151", 3), ("12608180152", 1), ("12608180153", 6)),
        (("12608180161", 3), ("12608180162", 1), ("12608180163", 8)),
        (("12608180141", 7), ("12608180142", 1), ("12608180143", 3)),
    )

    color_tendency, range_tendency = analyzer.analyze(
        current_results,
        completed_sessions,
    )

    assert color_tendency is not None
    assert color_tendency.target_position == 3
    assert color_tendency.prefix == ("Red", "Black")
    assert color_tendency.sample_size == 2
    assert dict(color_tendency.outcomes) == {
        "Black": 0,
        "Gray": 1,
        "Red": 1,
        "Zero": 0,
    }
    assert range_tendency is not None
    assert range_tendency.prefix == ("1-6", "1-6")
    assert range_tendency.sample_size == 2
    assert dict(range_tendency.outcomes) == {
        "1-6": 1,
        "7-12": 1,
        "13-18": 0,
        "Zero": 0,
    }


def test_tendency_has_no_next_position_after_a_complete_session():
    analyzer = SessionTendencyAnalyzer()
    results = [(str(12608180151 + index), 1) for index in range(10)]

    assert analyzer.analyze(results, ()) == (None, None)


def test_tendency_adapts_to_only_the_two_latest_positions():
    analyzer = SessionTendencyAnalyzer()
    current_results = [
        ("12608180171", 3),
        ("12608180172", 1),
        ("12608180173", 1),
        ("12608180174", 14),
    ]
    completed_sessions = (
        (
            ("12608180151", 2),
            ("12608180152", 2),
            ("12608180153", 1),
            ("12608180154", 14),
            ("12608180155", 3),
        ),
        (
            ("12608180161", 6),
            ("12608180162", 6),
            ("12608180163", 1),
            ("12608180164", 14),
            ("12608180165", 2),
        ),
    )

    color_tendency, range_tendency = analyzer.analyze(
        current_results,
        completed_sessions,
    )

    assert color_tendency is not None
    assert color_tendency.target_position == 5
    assert color_tendency.prefix == ("Black", "Gray")
    assert color_tendency.sample_size == 2
    assert dict(color_tendency.outcomes)["Red"] == 1
    assert dict(color_tendency.outcomes)["Gray"] == 1
    assert range_tendency is not None
    assert range_tendency.prefix == ("1-6", "13-18")
    assert range_tendency.sample_size == 2
