"""Coordinate session state, persistence, analytics, and presentation."""

from analytics.statistics import Statistics
from config import SESSION_DRAW_COUNT
from storage.storage import Storage
from tracker.session_presenter import SessionPresenter
from tracker.session_state import SessionState


class SessionManager:
    """Application coordinator for one draw-ID-based tracking session."""

    def __init__(self):
        self.storage = Storage()
        self.statistics = Statistics()
        self.state = SessionState(SESSION_DRAW_COUNT)
        self.presenter = SessionPresenter()
        self._restore_active_session()

    # Compatibility properties retained for the tracker and existing callers.
    @property
    def session_name(self) -> str:
        return self.state.name

    @session_name.setter
    def session_name(self, value: str) -> None:
        self.state.name = value

    @property
    def start_draw_id(self) -> str | None:
        return self.state.start_draw_id

    @start_draw_id.setter
    def start_draw_id(self, value: str | None) -> None:
        self.state.start_draw_id = value

    @property
    def results(self) -> list[tuple[str, int]]:
        return self.state.results

    @results.setter
    def results(self, value: list[tuple[str, int]]) -> None:
        self.state.results = value

    @property
    def running(self) -> bool:
        return self.state.running

    @running.setter
    def running(self, value: bool) -> None:
        self.state.running = value

    def _restore_active_session(self) -> None:
        """Restore an interrupted session, or finalize one already complete."""
        checkpoint = self.storage.load_active_session()
        if checkpoint is None:
            return

        self.state.restore(
            checkpoint.name,
            checkpoint.start_draw_id,
            checkpoint.results,
        )
        self.presenter.restore(self.results)
        if self.is_complete():
            self.finish()

    @staticmethod
    def draw_position(draw_id: str) -> int:
        return SessionState.draw_position(draw_id)

    @staticmethod
    def is_session_start_draw(draw_id: str) -> bool:
        return SessionState.is_session_start_draw(draw_id)

    @staticmethod
    def is_session_end_draw(draw_id: str) -> bool:
        return SessionState.is_session_end_draw(draw_id)

    def is_complete(self) -> bool:
        return self.state.is_complete()

    def wait_for_next_session(
        self,
        reader,
        previous_draw: str = "",
        previous_history: tuple[int, ...] | None = None,
    ):
        """Wait for a verified snapshot at the next ``...1`` boundary."""
        self.presenter.waiting_for_session()
        last_draw = previous_draw
        last_history = previous_history

        while True:
            snapshot = reader.wait_for_new_draw(last_draw, last_history)
            last_draw = snapshot.draw_id
            last_history = tuple(snapshot.history)
            self.presenter.waiting_draw(
                snapshot.draw_id,
                self.draw_position(snapshot.draw_id),
            )

            if self.is_session_start_draw(snapshot.draw_id):
                self.presenter.session_boundary_found()
                return snapshot

    def start(self, start_draw_id: str) -> None:
        """Create a session and checkpoint its initial empty state."""
        self.state.start(start_draw_id)
        self.storage.checkpoint_session(
            self.session_name,
            start_draw_id,
            self.results,
        )
        self.presenter.reset()
        self.presenter.session_started(start_draw_id, SESSION_DRAW_COUNT)

    def add_result(self, draw_id: str, result: int) -> None:
        """Validate, checkpoint, then publish one captured result."""
        updated_results = self.state.proposed_results(draw_id, result)
        if updated_results is None:
            return

        self.storage.checkpoint_session(
            self.session_name,
            self.start_draw_id or "",
            updated_results,
        )
        self.state.commit_results(updated_results)
        self.presenter.result_recorded(self.results, result)

    def abandon(self, reason: str, observed_draw_id: str):
        """Archive an incomplete session and return to the waiting state."""
        if not self.running:
            return None

        captured_count = len(self.results)
        start_draw_id = self.start_draw_id
        archived_path = self.storage.archive_active_session(reason, observed_draw_id)
        self.state.clear()
        self.presenter.reset()
        self.presenter.session_abandoned(
            captured_count,
            SESSION_DRAW_COUNT,
            start_draw_id,
            archived_path,
        )
        return archived_path

    def live_gap(self, number: int) -> int:
        return self.presenter.live_gap(self.results, number)

    def live_last_gap(self, number: int) -> int | None:
        return self.presenter.live_last_gap(self.results, number)

    def session_expired(self) -> bool:
        """Backward-compatible alias for the draw-based completion check."""
        return self.is_complete()

    def finish(self) -> None:
        """Build the final report, persist it, then clear active state."""
        if not self.running:
            return
        if not self.is_complete():
            raise RuntimeError(
                f"Cannot finish incomplete session: "
                f"{len(self.results)}/{SESSION_DRAW_COUNT} draws"
            )

        statistics = self.statistics.build(self.results)
        report_text = self.presenter.report(
            self.session_name,
            self.results,
            statistics,
        )
        filename = self.storage.save_session(self.session_name, report_text)
        self.storage.append_completed_session(self.results)
        self.storage.clear_active_session()
        self.state.clear()
        self.presenter.reset()
        self.presenter.session_finished(report_text, filename)

    def total_results(self) -> int:
        return len(self.results)

    def last_draw_id(self) -> str:
        return self.state.last_draw_id()

    def is_running(self) -> bool:
        return self.running
