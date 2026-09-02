"""Historical next-position tendencies derived from completed sessions."""

from dataclasses import dataclass
from typing import Callable, Sequence

from config import SESSION_DRAW_COUNT, TENDENCY_LOOKBACK_DRAWS
from models.number_domain import NUMBER_BANDS, NUMBER_COLORS, number_band, number_color


_ZERO_LABEL = "Zero"
_COLOR_OUTCOMES = tuple(label for label, _ in NUMBER_COLORS) + (_ZERO_LABEL,)
_RANGE_OUTCOMES = tuple(label for label, _ in NUMBER_BANDS) + (_ZERO_LABEL,)


@dataclass(frozen=True, slots=True)
class HistoricalTendency:
    """Observed next-result distribution for one current session prefix."""

    kind: str
    target_position: int
    prefix: tuple[str, ...]
    sample_size: int
    outcomes: tuple[tuple[str, int], ...]


@dataclass(frozen=True, slots=True)
class TendencyEvaluation:
    """One resolved historical tendency and its observed outcome."""

    kind: str
    target_position: int
    pattern: tuple[str, ...]
    sample_size: int
    outcomes: tuple[tuple[str, int], ...]
    favored_outcomes: tuple[str, ...]
    actual_outcome: str
    verdict: str


class SessionTendencyAnalyzer:
    """Compare the latest two session positions with completed-session history."""

    def analyze(
        self,
        current_results: Sequence[tuple[str, int]],
        completed_session_results: Sequence[Sequence[tuple[str, int]]],
    ) -> tuple[HistoricalTendency | None, HistoricalTendency | None]:
        """Return tendencies from the two draws immediately before the next one."""
        return (
            self._analyze_kind(
                "Color",
                current_results,
                completed_session_results,
                self._color_label,
                _COLOR_OUTCOMES,
            ),
            self._analyze_kind(
                "Range",
                current_results,
                completed_session_results,
                self._range_label,
                _RANGE_OUTCOMES,
            ),
        )

    def evaluate(
        self,
        tendency: HistoricalTendency | None,
        actual_result: int,
    ) -> TendencyEvaluation | None:
        """Resolve a tendency after its target draw has been captured."""
        if tendency is None:
            return None

        classify = (
            self._color_label
            if tendency.kind == "Color"
            else self._range_label
        )
        actual_outcome = classify(actual_result)
        if tendency.sample_size == 0:
            favored_outcomes: tuple[str, ...] = ()
            verdict = "NO_HISTORY"
        else:
            highest_count = max(count for _, count in tendency.outcomes)
            favored_outcomes = tuple(
                label
                for label, count in tendency.outcomes
                if count == highest_count
            )
            verdict = (
                "CORRECT" if actual_outcome in favored_outcomes else "INCORRECT"
            )

        return TendencyEvaluation(
            kind=tendency.kind,
            target_position=tendency.target_position,
            pattern=tendency.prefix,
            sample_size=tendency.sample_size,
            outcomes=tendency.outcomes,
            favored_outcomes=favored_outcomes,
            actual_outcome=actual_outcome,
            verdict=verdict,
        )

    @staticmethod
    def _color_label(result: int) -> str:
        return number_color(result) or _ZERO_LABEL

    @staticmethod
    def _range_label(result: int) -> str:
        return number_band(result) or _ZERO_LABEL

    @staticmethod
    def _analyze_kind(
        kind: str,
        current_results: Sequence[tuple[str, int]],
        completed_session_results: Sequence[Sequence[tuple[str, int]]],
        classify: Callable[[int], str],
        outcome_labels: tuple[str, ...],
    ) -> HistoricalTendency | None:
        captured_count = len(current_results)
        if not TENDENCY_LOOKBACK_DRAWS <= captured_count < SESSION_DRAW_COUNT:
            return None

        target_position = captured_count + 1
        target_index = captured_count
        window_start = target_index - TENDENCY_LOOKBACK_DRAWS
        prefix = tuple(
            classify(result)
            for _, result in current_results[-TENDENCY_LOOKBACK_DRAWS:]
        )
        counts = {label: 0 for label in outcome_labels}
        sample_size = 0
        for session_results in completed_session_results:
            if len(session_results) < target_position:
                continue
            history_prefix = tuple(
                classify(result)
                for _, result in session_results[window_start:target_index]
            )
            if history_prefix != prefix:
                continue
            sample_size += 1
            counts[classify(session_results[target_index][1])] += 1

        return HistoricalTendency(
            kind=kind,
            target_position=target_position,
            prefix=prefix,
            sample_size=sample_size,
            outcomes=tuple((label, counts[label]) for label in outcome_labels),
        )
