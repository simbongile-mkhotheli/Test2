from abc import ABC, abstractmethod


class Analyzer(ABC):

    @abstractmethod
    def analyze(self, numbers: list[int]):
        """Analyze a sequence of numbers."""
        raise NotImplementedError
