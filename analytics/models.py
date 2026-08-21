from dataclasses import dataclass

from analytics.analyzers.gaps import GapStatistics


@dataclass(slots=True)
class SessionStatistics:
    total: int
    gaps: GapStatistics
    results: list[tuple[str, int]]
