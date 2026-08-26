"""Pure domain state and invariants for one draw-ID-aligned session."""

from collections.abc import Sequence

from models.number_domain import validate_number


class SessionState:
    """Own session boundaries, accepted results, and no I/O concerns."""

    def __init__(self, draw_count: int):
        if draw_count <= 0:
            raise ValueError("Session draw count must be positive")

        self.draw_count = draw_count
        self.name = ""
        self.start_draw_id: str | None = None
        self.results: list[tuple[str, int]] = []
        self.running = False

    @staticmethod
    def draw_position(draw_id: str) -> int:
        """Return the final digit of a numeric draw ID."""
        if not draw_id or not draw_id.isdigit():
            raise ValueError(f"Invalid draw ID: {draw_id!r}")
        return int(draw_id[-1])

    @classmethod
    def is_session_start_draw(cls, draw_id: str) -> bool:
        return cls.draw_position(draw_id) == 1

    @property
    def end_draw_id(self) -> str | None:
        """Return the required final draw ID for this session."""
        if self.start_draw_id is None:
            return None
        return str(int(self.start_draw_id) + self.draw_count - 1)

    @property
    def expected_draw_ids(self) -> tuple[str, ...]:
        """Return every draw ID that must appear in a complete session."""
        if self.start_draw_id is None:
            return ()

        start = int(self.start_draw_id)
        return tuple(str(start + offset) for offset in range(self.draw_count))

    @property
    def missing_draw_ids(self) -> tuple[str, ...]:
        """Return required draw IDs not yet recovered or captured."""
        known = {draw_id for draw_id, _ in self.results}
        return tuple(
            draw_id for draw_id in self.expected_draw_ids if draw_id not in known
        )

    def restore(
        self,
        name: str,
        start_draw_id: str,
        results: list[tuple[str, int]],
    ) -> None:
        """Restore a validated persistence checkpoint into active state."""
        self.name = name
        self.start_draw_id = start_draw_id
        self.results = []
        self.running = True
        self.commit_results(results)

    def start(self, start_draw_id: str) -> None:
        """Start a new session at a valid ``...1`` boundary."""
        if not self.is_session_start_draw(start_draw_id):
            raise ValueError(
                f"Session must start on a draw ID ending in 1: {start_draw_id}"
            )

        self.name = f"draw-{start_draw_id}"
        self.start_draw_id = start_draw_id
        self.results = []
        self.running = True

    def proposed_results(
        self,
        draw_id: str,
        result: int,
    ) -> list[tuple[str, int]] | None:
        """Add one directly captured result without mutating this instance."""
        return self._proposed_results_for_candidates(((draw_id, result),))

    def proposed_results_from_history(
        self,
        observed_draw_id: str,
        history: Sequence[int],
    ) -> list[tuple[str, int]] | None:
        """Map verified newest-first history to draw IDs and merge session rows.

        A stable game snapshot associates ``history[0]`` with its draw ID,
        ``history[1]`` with the immediately previous draw ID, and so on. Only
        IDs inside this session's fixed boundary are considered.
        """
        if not observed_draw_id or not observed_draw_id.isdigit():
            raise ValueError(f"Invalid observed draw ID: {observed_draw_id!r}")
        if not history:
            raise ValueError("Cannot recover results from an empty history")

        observed_number = int(observed_draw_id)
        candidates = tuple(
            (str(observed_number - offset), result)
            for offset, result in enumerate(history)
        )
        return self._proposed_results_for_candidates(candidates)

    def unrecoverable_missing_draw_ids(
        self,
        observed_draw_id: str,
        history_count: int,
    ) -> tuple[str, ...]:
        """Return missing IDs that have aged out of the observed history.

        The test is only meaningful once the game reaches the session's final
        ID. Later snapshots can never include an older row than the one
        already outside the newest-first history window.
        """
        if not observed_draw_id or not observed_draw_id.isdigit():
            raise ValueError(f"Invalid observed draw ID: {observed_draw_id!r}")
        if history_count <= 0 or self.end_draw_id is None:
            return ()
        if int(observed_draw_id) < int(self.end_draw_id):
            return ()

        earliest_available = int(observed_draw_id) - history_count + 1
        return tuple(
            draw_id
            for draw_id in self.missing_draw_ids
            if int(draw_id) < earliest_available
        )

    def _proposed_results_for_candidates(
        self,
        candidates: Sequence[tuple[str, int]],
    ) -> list[tuple[str, int]] | None:
        """Merge in-boundary candidate rows without overwriting known results."""
        if not self.running:
            raise RuntimeError("Cannot add a result when no session is running")
        if self.start_draw_id is None or self.end_draw_id is None:
            raise RuntimeError("Running session is missing draw boundaries")

        start = int(self.start_draw_id)
        end = int(self.end_draw_id)
        merged = dict(self.results)
        changed = False

        for draw_id, result in candidates:
            validate_number(result)
            if not isinstance(draw_id, str) or not draw_id.isdigit():
                raise ValueError(f"Invalid draw ID: {draw_id!r}")

            draw_number = int(draw_id)
            if draw_number < start or draw_number > end:
                continue

            known_result = merged.get(draw_id)
            if known_result is None:
                merged[draw_id] = result
                changed = True
            elif known_result != result:
                raise ValueError(
                    "Verified history disagrees with the stored result for "
                    f"draw {draw_id}: expected {known_result}, got {result}"
                )

        if not changed:
            return None

        return sorted(merged.items(), key=lambda row: int(row[0]))

    def commit_results(self, results: Sequence[tuple[str, int]]) -> None:
        """Apply result rows that have already been durably checkpointed."""
        if self.start_draw_id is None or self.end_draw_id is None:
            raise RuntimeError("Session boundaries must be set before results")

        start = int(self.start_draw_id)
        end = int(self.end_draw_id)
        committed: dict[str, int] = {}
        for draw_id, result in results:
            if not isinstance(draw_id, str) or not draw_id.isdigit():
                raise ValueError(f"Invalid draw ID: {draw_id!r}")
            if not start <= int(draw_id) <= end:
                raise ValueError(
                    f"Draw {draw_id} is outside the session boundary "
                    f"{self.start_draw_id}-{self.end_draw_id}"
                )
            result = validate_number(result)
            previous = committed.get(draw_id)
            if previous is not None and previous != result:
                raise ValueError(f"Conflicting results for draw {draw_id}")
            if previous is not None:
                raise ValueError(f"Duplicate result for draw {draw_id}")
            committed[draw_id] = result

        self.results = sorted(committed.items(), key=lambda row: int(row[0]))

    def is_complete(self) -> bool:
        """Return True only when every required draw ID has a result."""
        return self.running and not self.missing_draw_ids

    def last_draw_id(self) -> str:
        return self.results[-1][0] if self.results else ""

    def clear(self) -> None:
        """Return to inactive state after completion or archival."""
        self.name = ""
        self.start_draw_id = None
        self.results = []
        self.running = False
