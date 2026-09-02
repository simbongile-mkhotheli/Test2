"""Coordinate session state, persistence, browser verification, and output."""

from dataclasses import dataclass
from pathlib import Path

from config import (
    POSITION_COLOR_ALERT_COLOR,
    SESSION_DRAW_COUNT,
    TENDENCY_LOOKBACK_DRAWS,
)
from models.number_domain import number_color
from storage.storage import CompletedSession, Storage
from tracker.session_presenter import SessionPresenter
from tracker.session_state import SessionState
from tracker.session_tendency import HistoricalTendency, SessionTendencyAnalyzer
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
        self.tendency_analyzer = SessionTendencyAnalyzer()
        self._last_history: tuple[int, ...] | None = None
        self._previous_completed_sessions: (
            tuple[CompletedSession, CompletedSession] | None
        ) = None
        self._completed_sessions: tuple[CompletedSession, ...] = ()
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

        try:
            self.state.restore(
                checkpoint.name,
                checkpoint.start_draw_id,
                checkpoint.results,
            )
        except ValueError:
            missing_draw_ids = self._first_checkpoint_gap(checkpoint)
            archive_path = self.storage.preserve_incomplete_session(
                checkpoint.results[-1][0],
                missing_draw_ids,
            )
            self.state.clear()
            self.presenter.session_incomplete(
                len(checkpoint.results),
                SESSION_DRAW_COUNT,
                checkpoint.start_draw_id,
                missing_draw_ids,
                archive_path,
            )
            return

        self._last_history = checkpoint.last_history
        self._load_completed_session_history()
        self.presenter.restore(self.results, checkpoint.name)
        self._synchronize_tendency_evaluations()
        self._publish_historical_tendencies()
        self._alert_upcoming_repeated_position_color(len(self.results) + 1)
        if self.is_complete():
            self.finish()

    @staticmethod
    def _first_checkpoint_gap(checkpoint) -> tuple[str, ...]:
        """Return the earliest missing ID from an old sparse checkpoint."""
        expected_draw = int(checkpoint.start_draw_id)
        for draw_id, _ in checkpoint.results:
            if int(draw_id) != expected_draw:
                return (str(expected_draw),)
            expected_draw += 1
        return (str(expected_draw),)

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
        self._load_completed_session_history()
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
        self._alert_upcoming_repeated_position_color(position=1)

    def add_snapshot(self, snapshot) -> SnapshotIngest:
        """Store one verified snapshot under its own draw ID."""
        known_draw_ids = {draw_id for draw_id, _ in self.results}
        pending_tendencies = self._historical_tendencies()
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

            self._record_tendency_evaluations(pending_tendencies, snapshot.latest)
            self.presenter.result_recorded(self.results)
            self._publish_historical_tendencies()
            self._alert_upcoming_repeated_position_color(len(self.results) + 1)

        unavailable_draw_ids = self.state.incomplete_missing_draw_ids(snapshot.draw_id)
        return SnapshotIngest(
            observed_draw_id=snapshot.draw_id,
            accepted_draw_ids=accepted_draw_ids,
            unavailable_draw_ids=unavailable_draw_ids,
        )

    def _load_completed_session_history(self) -> None:
        """Load finalized reports used by alerts and history tendencies."""
        start_draw_id = self.start_draw_id
        self._completed_sessions = (
            self.storage.completed_sessions_before(start_draw_id)
            if start_draw_id is not None
            else ()
        )
        self._previous_completed_sessions = (
            self.storage.two_consecutive_completed_sessions_before(start_draw_id)
            if start_draw_id is not None
            else None
        )

    def _publish_historical_tendencies(self) -> None:
        """Show what completed sessions historically did after this prefix."""
        color_tendency, range_tendency = self._historical_tendencies()
        self.presenter.historical_tendencies(color_tendency, range_tendency)

    def _historical_tendencies(
        self,
    ) -> tuple[HistoricalTendency | None, HistoricalTendency | None]:
        """Calculate the next-position tendencies for the current draw prefix."""
        return self.tendency_analyzer.analyze(
            self.results,
            tuple(session.results for session in self._completed_sessions),
        )

    def _record_tendency_evaluations(
        self,
        tendencies: tuple[HistoricalTendency | None, HistoricalTendency | None],
        actual_result: int,
    ) -> None:
        """Persist color and range verdicts after their target draw is durable."""
        for tendency in tendencies:
            evaluation = self.tendency_analyzer.evaluate(tendency, actual_result)
            if evaluation is None:
                continue
            self.storage.append_tendency_evaluation(
                self.session_name,
                evaluation.target_position,
                evaluation.kind,
                evaluation.pattern,
                evaluation.sample_size,
                evaluation.outcomes,
                evaluation.actual_outcome,
                evaluation.verdict,
            )

    def _synchronize_tendency_evaluations(self) -> None:
        """Recover any tendency rows interrupted after a checkpoint commit."""
        for captured_count in range(
            TENDENCY_LOOKBACK_DRAWS + 1,
            len(self.results) + 1,
        ):
            tendencies = self.tendency_analyzer.analyze(
                self.results[: captured_count - 1],
                tuple(session.results for session in self._completed_sessions),
            )
            _, actual_result = self.results[captured_count - 1]
            self._record_tendency_evaluations(tendencies, actual_result)

    def _alert_upcoming_repeated_position_color(self, position: int) -> None:
        """Alert before a position red in both immediately prior sessions."""
        previous = self._previous_completed_sessions
        if previous is None or not 1 <= position <= SESSION_DRAW_COUNT:
            return

        older_session, newer_session = previous
        _, older_result = older_session.results[position - 1]
        _, newer_result = newer_session.results[position - 1]
        if (
            number_color(older_result) == POSITION_COLOR_ALERT_COLOR
            and number_color(newer_result) == POSITION_COLOR_ALERT_COLOR
        ):
            self.presenter.upcoming_position_color_alert(
                position,
                POSITION_COLOR_ALERT_COLOR,
                older_session.name,
                newer_session.name,
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
        self._previous_completed_sessions = None
        self._completed_sessions = ()
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
        self._previous_completed_sessions = None
        self._completed_sessions = ()
        self.presenter.reset()
        self.presenter.session_finished(report_text, filename)

    def last_draw_id(self) -> str:
        return self.state.last_draw_id()

    def last_history(self) -> tuple[int, ...] | None:
        """Return the checkpointed history fingerprint for restart safety."""
        return self._last_history

    def is_running(self) -> bool:
        return self.running
