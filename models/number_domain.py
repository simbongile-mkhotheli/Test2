"""Authoritative Wheel of Fortune result-number domain."""

from collections.abc import Iterable


NUMBER_MIN = 0
NUMBER_MAX = 18
NUMBER_VALUES = range(NUMBER_MIN, NUMBER_MAX + 1)

# Zero is a valid game result, but the range trend intentionally excludes it.
# Every non-zero valid result belongs to exactly one display band.
NUMBER_BANDS: tuple[tuple[str, range], ...] = (
    ("1-6", range(1, 7)),
    ("7-12", range(7, 13)),
    ("13-18", range(13, 19)),
)


def is_valid_number(value: object) -> bool:
    """Return whether *value* is a valid game result number."""
    return type(value) is int and value in NUMBER_VALUES


def validate_number(value: object) -> int:
    """Return a valid result number or raise a clear input error."""
    if not is_valid_number(value):
        raise ValueError(
            f"Result number must be an integer from {NUMBER_MIN} to {NUMBER_MAX}: "
            f"{value!r}"
        )
    return value


def validate_numbers(values: Iterable[object]) -> None:
    """Validate each value in a sequence of game results."""
    for value in values:
        validate_number(value)


def number_counts(values: Iterable[object]) -> dict[int, int]:
    """Count valid game result numbers, including zero-valued results."""
    counts = {number: 0 for number in NUMBER_VALUES}
    for value in values:
        counts[validate_number(value)] += 1
    return counts


def range_counts(values: Iterable[object]) -> dict[str, int]:
    """Count valid non-zero results in the configured display ranges."""
    counts = {label: 0 for label, _ in NUMBER_BANDS}
    for value in values:
        band = number_band(value)
        if band is not None:
            counts[band] += 1
    return counts


def range_absence_streaks(values: Iterable[object]) -> dict[str, int]:
    """Return current consecutive-absence lengths for every display range.

    A zero is a valid game result but belongs to no range, so it extends the
    absence streak of all three display ranges.
    """
    streaks = {label: 0 for label, _ in NUMBER_BANDS}
    for value in values:
        observed_band = number_band(value)
        for label, _ in NUMBER_BANDS:
            if label == observed_band:
                streaks[label] = 0
            else:
                streaks[label] += 1
    return streaks


def number_band(value: object) -> str | None:
    """Return a range-trend band, or None when the valid result is zero."""
    number = validate_number(value)
    for label, values in NUMBER_BANDS:
        if number in values:
            return label
    return None
