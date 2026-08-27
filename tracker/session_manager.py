"""Coordinate session state, persistence, browser verification, and output."""

from dataclasses import dataclass
from pathlib import Path

from config import SESSION_DRAW_COUNT
from storage.storage import Storage
from tracker.session_presenter import SessionPresenter
from tracker.session_state import SessionState


@dataclass(frozen=True, slots=True)
class SnapshotIngest:
    """The effect of one verified browser snapshot on the active session."""

    observed_draw_id: str
    accepted_draw_ids: tuple[str, ...]
    unavailable_draw_ids: tuple[str, ...]

    @property
    def captured_current_draw(self) -> bool:
        return self.observed_draw_id in self.accepted_draw_ids


class SessionManager:
    """Application coordinator for one draw-ID-aligned tracking session."""

    def __init__(self):
        self.storage = Storage()
        self.state = SessionState(SESSION_DRAW_COUNT)
        self.presenter = SessionPresenter()
        self._last_history: tuple[int, ...] | None = None
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
    def end_draw_id(self) -> str | None:
        return self.state.end_draw_id

    @property
    def results(self) -> list[tuple[str, int]]:
        return self.state.results

    @results.setter
    def results(self, value: list[tuple[str, int]]) -> None:
        self.state.commit_results(value)

    @property
    def running(self) -> bool:
        return self.state.running

    @running.setter
    def running(self, value: bool) -> None:
        self.state.running = value

    @property
    def missing_draw_ids(self) -> tuple[str, ...]:
        return self.state.missing_draw_ids

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
        self._last_history = checkpoint.last_history
        self.storage.append_live_results(
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
            self._last_history,
        )
        self.presenter.reset()
        self.presenter.session_started(
            start_draw_id,
            self.end_draw_id or "",
            SESSION_DRAW_COUNT,
        )

    def add_snapshot(self, snapshot) -> SnapshotIngest:
        """Store one verified snapshot under its own draw ID."""
        known_draw_ids = {draw_id for draw_id, _ in self.results}
        updated_results = self.state.proposed_result_from_snapshot(
            snapshot.draw_id,
            snapshot.history,
        )

        accepted_draw_ids: tuple[str, ...] = ()
        if updated_results is not None:
            self.storage.checkpoint_session(
                self.session_name,
                self.start_draw_id or "",
                updated_results,
                tuple(snapshot.history),
            )
            self.storage.append_live_results(
                self.start_draw_id or "",
                updated_results,
            )
            self.state.commit_results(updated_results)
            self._last_history = tuple(snapshot.history)
            accepted_draw_ids = tuple(
                draw_id
                for draw_id, _ in self.results
                if draw_id not in known_draw_ids
            )

            self.presenter.result_recorded(self.results)

        unavailable_draw_ids = self.state.incomplete_missing_draw_ids(snapshot.draw_id)
        return SnapshotIngest(
            observed_draw_id=snapshot.draw_id,
            accepted_draw_ids=accepted_draw_ids,
            unavailable_draw_ids=unavailable_draw_ids,
        )

    def add_result(self, draw_id: str, result: int) -> None:
        """Add one direct result; snapshot ingestion is preferred at runtime."""
        updated_results = self.state.proposed_results(draw_id, result)
        if updated_results is None:
            return

        self.storage.checkpoint_session(
            self.session_name,
            self.start_draw_id or "",
            updated_results,
            self._last_history,
        )
        self.storage.append_live_results(
            self.start_draw_id or "",
            updated_results,
        )
        self.state.commit_results(updated_results)
        self.presenter.result_recorded(self.results)

    def preserve_incomplete(
        self,
        observed_draw_id: str,
        missing_draw_ids: tuple[str, ...],
    ) -> Path | None:
        """Preserve an unrecoverable session without contaminating results.txt."""
        if not self.running:
            return None

        captured_count = len(self.results)
        start_draw_id = self.start_draw_id
        archive_path = self.storage.preserve_incomplete_session(
            observed_draw_id,
            missing_draw_ids,
        )
        self.storage.mark_live_session_incomplete(
            start_draw_id or "",
            self.results,
            observed_draw_id,
            missing_draw_ids,
        )
        self.state.clear()
        self._last_history = None
        self.presenter.reset()
        self.presenter.session_incomplete(
            captured_count,
            SESSION_DRAW_COUNT,
            start_draw_id,
            missing_draw_ids,
            archive_path,
        )
        return archive_path

    def finish(self) -> None:
        """Build the final report, persist it, then clear active state."""
        if not self.running:
            return
        if not self.is_complete():
            raise RuntimeError(
                f"Cannot finish incomplete session: "
                f"{len(self.results)}/{SESSION_DRAW_COUNT} results; "
                f"missing {', '.join(self.missing_draw_ids)}"
            )

        report_text = self.presenter.report(
            self.session_name,
            self.results,
        )
        filename = self.storage.save_session(self.session_name, report_text)
        self.storage.append_completed_session(self.results)
        self.storage.clear_active_session()
        self.state.clear()
        self._last_history = None
        self.presenter.reset()
        self.presenter.session_finished(report_text, filename)

    def total_results(self) -> int:
        return len(self.results)

    def last_draw_id(self) -> str:
        return self.state.last_draw_id()

    def last_history(self) -> tuple[int, ...] | None:
        """Return the checkpointed history fingerprint for restart safety."""
        return self._last_history

    def is_running(self) -> bool:
        return self.running
