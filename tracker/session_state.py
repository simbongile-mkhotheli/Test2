"""Pure domain state and invariants for one draw-ID-based session."""

from exceptions import SessionGap
from models.number_domain import validate_number


class SessionState:
    """Own session boundaries, accepted results, and no I/O concerns."""

    def __init__(self, draw_count: int):
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

    @classmethod
    def is_session_end_draw(cls, draw_id: str) -> bool:
        return cls.draw_position(draw_id) == 0

    def restore(
        self,
        name: str,
        start_draw_id: str,
        results: list[tuple[str, int]],
    ) -> None:
        """Restore a validated persistence checkpoint into active state."""
        self.name = name
        self.start_draw_id = start_draw_id
        self.results = list(results)
        self.running = True

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
        """Validate a draw and return new state without mutating this instance."""
        if not self.running:
            raise RuntimeError("Cannot add a result when no session is running")

        validate_number(result)

        if self.results:
            previous_draw_id = self.results[-1][0]
            if draw_id == previous_draw_id:
                return None
            if not draw_id.isdigit() or int(draw_id) != int(previous_draw_id) + 1:
                raise SessionGap(str(int(previous_draw_id) + 1), draw_id)
        elif draw_id != self.start_draw_id:
            raise SessionGap(self.start_draw_id or "", draw_id)

        return [*self.results, (draw_id, result)]

    def commit_results(self, results: list[tuple[str, int]]) -> None:
        """Apply a result list that has been durably checkpointed."""
        self.results = results

    def is_complete(self) -> bool:
        """Return True after exactly the configured consecutive draw count."""
        return (
            self.running
            and len(self.results) == self.draw_count
            and bool(self.results)
            and self.is_session_end_draw(self.results[-1][0])
        )

    def last_draw_id(self) -> str:
        return self.results[-1][0] if self.results else ""

    def clear(self) -> None:
        """Return to inactive state after completion or abandonment."""
        self.name = ""
        self.start_draw_id = None
        self.results = []
        self.running = False
