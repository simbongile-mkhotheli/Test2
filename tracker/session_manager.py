"""Coordinate session state, persistence, browser verification, and output."""

from dataclasses import dataclass
from pathlib import Path

from config import SESSION_DRAW_COUNT
from storage.storage import Storage
from tracker.session_presenter import SessionPresenter
from tracker.session_state import SessionState
from ui.events import EventBus


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

    def __init__(self, events: EventBus | None = None):
        self.storage = Storage()
        self.state = SessionState(SESSION_DRAW_COUNT)
        self.presenter = SessionPresenter(events)
        self._last_history: tuple[int, ...] | None = None
        self._restore_active_session()

    @property
    def session_name(self) -> str:
        return self.state.name

    @property
    def start_draw_id(self) -> str | None:
        return self.state.start_draw_id

    @property
    def end_draw_id(self) -> str | None:
        return self.state.end_draw_id

    @property
    def results(self) -> list[tuple[str, int]]:
        return self.state.results

    @property
    def running(self) -> bool:
        return self.state.running

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
        self.presenter.restore(self.results, checkpoint.name)
        if self.is_complete():
            self.finish()

    def is_complete(self) -> bool:
        return self.state.is_complete()

    def wait_for_next_session(
        self,
        reader,
        previous_draw: str = "",
        previous_history: tuple[int, ...] | None = None,
        should_stop=None,
        on_snapshot=None,
    ):
        """Wait for a verified snapshot at the next ``...1`` boundary."""
        self.presenter.waiting_for_session()
        last_draw = previous_draw
        last_history = previous_history

        while True:
            snapshot = reader.wait_for_new_draw(
                last_draw,
                last_history,
                should_stop,
            )
            last_draw = snapshot.draw_id
            last_history = tuple(snapshot.history)
            if on_snapshot is not None:
                on_snapshot(snapshot)
            self.presenter.waiting_draw(
                snapshot.draw_id,
                SessionState.draw_position(snapshot.draw_id),
            )

            if SessionState.is_session_start_draw(snapshot.draw_id):
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
            self.session_name,
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
        self.storage.clear_active_session()
        self.state.clear()
        self._last_history = None
        self.presenter.reset()
        self.presenter.session_finished(report_text, filename)

    def last_draw_id(self) -> str:
        return self.state.last_draw_id()

    def last_history(self) -> tuple[int, ...] | None:
        """Return the checkpointed history fingerprint for restart safety."""
        return self._last_history

    def is_running(self) -> bool:
        return self.running
