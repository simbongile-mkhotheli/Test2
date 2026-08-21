"""Gap analysis for the active session.

Definitions
-----------
- current_gap[number]:
    Draws since the most recent appearance. A number drawn on the latest
    result has current_gap == 0.

- last_gap[number]:
    Draws between the two most recent appearances. None when a number has
    appeared fewer than two times.

- longest_gap[number]:
    Longest consecutive run of draws in which the number was absent,
    including leading and trailing gaps.

These are measured in completed draws, never draw-ID distance.
"""

from dataclasses import dataclass, field

from analytics.analyzers.base import Analyzer


@dataclass(slots=True)
class GapStatistics:
    current_gaps: dict[int, int] = field(default_factory=dict)
    last_gaps: dict[int, int | None] = field(default_factory=dict)
    longest_gaps: dict[int, int] = field(default_factory=dict)
    active_numbers: list[int] = field(default_factory=list)
    largest_gap: int = 0
    gap_leaders: list[int] = field(default_factory=list)


class GapAnalyzer(Analyzer):
    """Calculate current/live, last, and longest gaps for 0-18."""

    NUMBER_MIN = 0
    NUMBER_MAX = 18

    def analyze(self, numbers: list[int]) -> GapStatistics:
        total = len(numbers)
        current: dict[int, int] = {}
        last: dict[int, int | None] = {}
        longest: dict[int, int] = {}
        active: list[int] = []

        for target in range(self.NUMBER_MIN, self.NUMBER_MAX + 1):
            positions = [
                index
                for index, number in enumerate(numbers)
                if number == target
            ]

            if not positions:
                current[target] = total
                last[target] = None
                longest[target] = total
                continue

            active.append(target)

            latest = positions[-1]
            current[target] = total - 1 - latest

            last[target] = (
                positions[-1] - positions[-2] - 1
                if len(positions) >= 2
                else None
            )

            previous = -1
            max_gap = 0

            for position in positions:
                max_gap = max(max_gap, position - previous - 1)
                previous = position

            max_gap = max(max_gap, total - previous - 1)
            longest[target] = max_gap

        largest_gap = max(longest.values(), default=0)
        gap_leaders = sorted(
            number
            for number, gap in longest.items()
            if gap == largest_gap
        )

        return GapStatistics(
            current_gaps=current,
            last_gaps=last,
            longest_gaps=longest,
            active_numbers=sorted(active),
            largest_gap=largest_gap,
            gap_leaders=gap_leaders,
        )

    @classmethod
    def current_gap(cls, numbers: list[int], target: int) -> int:
        """Return the current live gap for one target."""
        total = len(numbers)
        for index in range(total - 1, -1, -1):
            if numbers[index] == target:
                return total - 1 - index
        return total

    @classmethod
    def last_gap(cls, numbers: list[int], target: int) -> int | None:
        """Return draws between the two most recent appearances."""
        positions = [
            index
            for index, number in enumerate(numbers)
            if number == target
        ]
        if len(positions) < 2:
            return None
        return positions[-1] - positions[-2] - 1
