"""Build descriptive statistics for one completed session."""

from analytics.models import SessionStatistics
from analytics.pipeline import AnalyticsPipeline


class Statistics:
    def __init__(self):
        self.pipeline = AnalyticsPipeline()

    def build(self, results: list[tuple[str, int]]) -> SessionStatistics:
        numbers = [value for _, value in results]
        analytics = self.pipeline.analyze(numbers)

        return SessionStatistics(
            total=len(numbers),
            gaps=analytics["gaps"],
            results=results,
        )
