from analytics.analyzers.gaps import GapAnalyzer


class AnalyticsPipeline:
    def __init__(self):
        self.gaps = GapAnalyzer()

    def analyze(self, numbers: list[int]) -> dict[str, object]:
        return {
            "gaps": self.gaps.analyze(numbers),
        }
