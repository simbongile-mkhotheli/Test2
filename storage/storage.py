"""Persistence for the human-readable draw log and session reports."""

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile

from config import (
    ACTIVE_SESSION_FILE,
    COLOR_TENDENCIES_FILE,
    INCOMPLETE_SESSIONS_DIR,
    LEGACY_TENDENCIES_FILE,
    RESULTS_FILE,
    SESSIONS_DIR,
    SESSION_DRAW_COUNT,
    RANGE_TENDENCIES_FILE,
)
from models.number_domain import validate_number


_DRAW_LINE_RE = re.compile(r"^\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(-?\d+)\s*$")
_CSV_LINE_RE = re.compile(r"^\s*(\d+)\s*,\s*(-?\d+)\s*$")
_SESSION_REPORT_NAME_RE = re.compile(r"^draw-(\d+)\.txt$")
_SESSION_REPORT_DRAW_RE = re.compile(r"^\s*(\d+)\s+(\d+)\s+(-?\d+)\s*$")
_RESULTS_LOG_HEADER = (
    "Pos | Draw ID             | Result",
    "----+---------------------+-------",
)
_TENDENCY_LOG_COLUMNS = (
    "Session",
    "Pos",
    "Previous two",
    "Matches",
    "Distribution",
    "Actual",
    "Verdict",
    "Correct streak",
)


@dataclass(frozen=True, slots=True)
class ActiveSession:
    """Durable state required to resume a session after an interruption."""

    name: str
    start_draw_id: str
    results: list[tuple[str, int]]
    last_history: tuple[int, ...] | None


@dataclass(frozen=True, slots=True)
class CompletedSession:
    """A finalized session report used for cross-session position alerts."""

    name: str
    results: tuple[tuple[str, int], ...]


class Storage:
    def __init__(self):
        RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        RESULTS_FILE.touch(exist_ok=True)
        self._migrate_legacy_tendency_log()
        self._reformat_tendency_logs()

    @staticmethod
    def _atomic_write_text(path: Path, text: str) -> None:
        """Replace a text file only after its complete contents are durable."""
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None

        try:
            with NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                temporary_file.write(text)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())

            os.replace(temporary_path, path)
        except Exception:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()
            raise

    @staticmethod
    def _validated_history(
        history: tuple[int, ...] | list[int] | None,
    ) -> list[int] | None:
        """Validate optional browser history retained for restart verification."""
        if history is None:
            return None
        if not isinstance(history, (tuple, list)):
            raise ValueError("Persisted browser history must be a list of results")
        return [validate_number(result) for result in history]

    @staticmethod
    def _validated_session_rows(
        results: list[tuple[str, int]],
        start_draw_id: str,
        *,
        require_start_draw: bool,
    ) -> list[tuple[str, int]]:
        if not start_draw_id or not start_draw_id.isdigit():
            raise ValueError(f"Invalid session start draw ID: {start_draw_id!r}")
        if start_draw_id[-1] != "1":
            raise ValueError(
                "Session start draw ID must end in 1: "
                f"{start_draw_id}"
            )

        session_start = int(start_draw_id)
        session_end = session_start + SESSION_DRAW_COUNT - 1
        validated: list[tuple[str, int]] = []
        seen_draw_ids: set[str] = set()
        for position, row in enumerate(results):
            try:
                draw_id, result = row
            except (TypeError, ValueError) as error:
                raise ValueError(f"Invalid persisted result at position {position}") from error

            if not isinstance(draw_id, str) or not draw_id.isdigit():
                raise ValueError(f"Invalid draw ID at position {position}: {draw_id!r}")
            if not session_start <= int(draw_id) <= session_end:
                raise ValueError(
                    f"Persisted draw {draw_id} is outside the session boundary "
                    f"{start_draw_id}-{session_end}"
                )
            if draw_id in seen_draw_ids:
                raise ValueError(f"Duplicate persisted draw ID: {draw_id}")

            validated.append((draw_id, validate_number(result)))
            seen_draw_ids.add(draw_id)

        validated.sort(key=lambda row: int(row[0]))
        if require_start_draw and validated and validated[0][0] != start_draw_id:
            raise ValueError(
                f"First persisted draw must be {start_draw_id}, got {validated[0][0]}"
            )

        return validated

    @classmethod
    def _validated_results(
        cls,
        results: list[tuple[str, int]],
        start_draw_id: str,
    ) -> list[tuple[str, int]]:
        """Validate checkpoint rows, which must include the session start."""
        return cls._validated_session_rows(
            results,
            start_draw_id,
            require_start_draw=True,
        )

    def checkpoint_session(
        self,
        session_name: str,
        start_draw_id: str,
        results: list[tuple[str, int]],
        last_history: tuple[int, ...] | list[int] | None = None,
    ) -> None:
        """Atomically save the active session after each accepted draw."""
        validated_results = self._validated_results(results, start_draw_id)
        validated_history = self._validated_history(last_history)
        payload = {
            "version": 1,
            "name": session_name,
            "start_draw_id": start_draw_id,
            "results": validated_results,
            "last_history": validated_history,
        }
        self._atomic_write_text(
            ACTIVE_SESSION_FILE,
            json.dumps(payload, separators=(",", ":")),
        )

    def load_active_session(self) -> ActiveSession | None:
        """Load a complete checkpoint, if an interruption left one behind."""
        if not ACTIVE_SESSION_FILE.exists():
            return None

        try:
            payload = json.loads(ACTIVE_SESSION_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError("Active session checkpoint is not valid JSON") from error

        if not isinstance(payload, dict) or payload.get("version") != 1:
            raise ValueError("Active session checkpoint has an unsupported format")

        session_name = payload.get("name")
        start_draw_id = payload.get("start_draw_id")
        raw_results = payload.get("results")
        raw_history = payload.get("last_history")
        if not isinstance(session_name, str) or not isinstance(raw_results, list):
            raise ValueError("Active session checkpoint is missing required fields")

        results = self._validated_results(raw_results, start_draw_id)
        return ActiveSession(
            name=session_name,
            start_draw_id=start_draw_id,
            results=results,
            last_history=(
                tuple(self._validated_history(raw_history))
                if raw_history is not None
                else None
            ),
        )

    def clear_active_session(self) -> None:
        """Remove a checkpoint only after its complete session is persisted."""
        try:
            ACTIVE_SESSION_FILE.unlink()
        except FileNotFoundError:
            pass

    def preserve_incomplete_session(
        self,
        observed_draw_id: str,
        missing_draw_ids: tuple[str, ...],
    ) -> Path | None:
        """Keep an incomplete partial session without changing the root log."""
        checkpoint = self.load_active_session()
        if checkpoint is None:
            return None
        if not observed_draw_id.isdigit():
            raise ValueError(f"Invalid observed draw ID: {observed_draw_id!r}")
        if not missing_draw_ids:
            raise ValueError("Incomplete session must identify missing draw IDs")

        archive_path = INCOMPLETE_SESSIONS_DIR / (
            f"{checkpoint.name}-observed-{observed_draw_id}.json"
        )
        payload = {
            "version": 1,
            "status": "incomplete",
            "observed_draw_id": observed_draw_id,
            "missing_draw_ids": list(missing_draw_ids),
            "name": checkpoint.name,
            "start_draw_id": checkpoint.start_draw_id,
            "end_draw_id": str(int(checkpoint.start_draw_id) + SESSION_DRAW_COUNT - 1),
            "results": checkpoint.results,
        }
        self._atomic_write_text(
            archive_path,
            json.dumps(payload, separators=(",", ":")),
        )
        self.clear_active_session()
        return archive_path

    @staticmethod
    def _validate_live_result(draw_id: str, result: int) -> tuple[str, int]:
        if not isinstance(draw_id, str) or not draw_id.isdigit():
            raise ValueError(f"Invalid draw ID: {draw_id!r}")
        return draw_id, validate_number(result)

    def _write_live_results(self, results: list[tuple[str, int]]) -> None:
        lines = [*_RESULTS_LOG_HEADER]
        lines.extend(
            f"{position:>3} | {draw_id:<19} | {result:>6}"
            for position, (draw_id, result) in enumerate(results, start=1)
        )
        self._atomic_write_text(RESULTS_FILE, "\n".join(lines) + "\n")

    def prepare_live_results_log(self) -> None:
        """Convert any legacy session-formatted root log to one live table."""
        normalized: list[tuple[str, int]] = []
        known_results: dict[str, int] = {}
        for draw_id, result in self.read_results():
            prior_result = known_results.get(draw_id)
            if prior_result is None:
                normalized.append((draw_id, result))
                known_results[draw_id] = result
            elif prior_result != result:
                raise ValueError(
                    f"The results log has conflicting values for draw {draw_id}"
                )
        self._write_live_results(normalized)

    def append_live_result(self, draw_id: str, result: int) -> bool:
        """Atomically add one verified draw to the root live-results table.

        The log is independent of 10-draw sessions. A repeated observation of
        the same draw with the same value is ignored; a conflicting value is
        treated as an integrity error.
        """
        draw_id, result = self._validate_live_result(draw_id, result)
        results = self.read_results()
        for existing_draw_id, existing_result in results:
            if existing_draw_id != draw_id:
                continue
            if existing_result != result:
                raise ValueError(
                    f"The results log disagrees with draw {draw_id}: "
                    f"expected {existing_result}, got {result}"
                )
            return False

        self._write_live_results([*results, (draw_id, result)])
        return True

    def save_session(self, session_name: str, report: str):
        filename = SESSIONS_DIR / f"{session_name}.txt"
        self._atomic_write_text(filename, report)
        return filename

    def two_consecutive_completed_sessions_before(
        self,
        start_draw_id: str,
    ) -> tuple[CompletedSession, CompletedSession] | None:
        """Return the two sessions immediately before *start_draw_id*.

        Both reports must be complete and directly adjacent in the draw-ID
        sequence. A missing, partial, or malformed report resets the position
        pattern instead of letting older sessions create a false alert.
        """
        if not isinstance(start_draw_id, str) or not start_draw_id.isdigit():
            raise ValueError(f"Invalid session start draw ID: {start_draw_id!r}")
        if start_draw_id[-1] != "1":
            raise ValueError(
                "Session start draw ID must end in 1: "
                f"{start_draw_id}"
            )

        current_start = int(start_draw_id)
        previous_starts = (
            current_start - (2 * SESSION_DRAW_COUNT),
            current_start - SESSION_DRAW_COUNT,
        )
        sessions: list[CompletedSession] = []
        for previous_start in previous_starts:
            path = SESSIONS_DIR / f"draw-{previous_start}.txt"
            if not path.exists():
                return None
            results = self._read_completed_session_results(path)
            if not results:
                return None
            sessions.append(CompletedSession(path.stem, results))

        return sessions[0], sessions[1]

    def completed_sessions_before(
        self,
        start_draw_id: str,
    ) -> tuple[CompletedSession, ...]:
        """Return every valid completed session that predates this session."""
        if not isinstance(start_draw_id, str) or not start_draw_id.isdigit():
            raise ValueError(f"Invalid session start draw ID: {start_draw_id!r}")

        current_start = int(start_draw_id)
        sessions: list[tuple[int, CompletedSession]] = []
        for path in SESSIONS_DIR.glob("draw-*.txt"):
            match = _SESSION_REPORT_NAME_RE.match(path.name)
            if match is None or int(match.group(1)) >= current_start:
                continue
            results = self._read_completed_session_results(path)
            if results:
                sessions.append((int(match.group(1)), CompletedSession(path.stem, results)))

        return tuple(session for _, session in sorted(sessions))

    def append_tendency_evaluation(
        self,
        session_name: str,
        position: int,
        kind: str,
        pattern: tuple[str, ...],
        sample_size: int,
        outcomes: tuple[tuple[str, int], ...],
        actual_outcome: str,
        verdict: str,
    ) -> bool:
        """Atomically append one resolved tendency unless it is already logged."""
        if position < 1:
            raise ValueError(f"Invalid tendency position: {position}")
        if sample_size < 0:
            raise ValueError(f"Invalid tendency sample size: {sample_size}")
        if verdict not in {"CORRECT", "INCORRECT", "NO_HISTORY"}:
            raise ValueError(f"Invalid tendency verdict: {verdict!r}")

        pattern_text = " -> ".join(pattern)
        tendency_file = self._tendency_file_for(kind)
        existing_lines = (
            tendency_file.read_text(encoding="utf-8").splitlines()
            if tendency_file.exists()
            else []
        )
        key = (session_name, str(position))
        parsed_entries = self._read_tendency_entries(existing_lines)
        if any(entry[:2] == key for entry in parsed_entries):
            return False

        streak = self._tendency_correct_streak(
            parsed_entries,
            pattern_text,
            verdict,
        )
        distribution = self._format_tendency_distribution(outcomes, sample_size)
        parsed_entries.append(
            (
                session_name,
                str(position),
                pattern_text,
                str(sample_size),
                distribution,
                actual_outcome,
                verdict,
                str(streak),
            )
        )
        self._atomic_write_text(tendency_file, self._tendency_log_text(parsed_entries))
        return True

    def _migrate_legacy_tendency_log(self) -> None:
        """Split the old combined tendency log without discarding its rows."""
        if (
            not LEGACY_TENDENCIES_FILE.exists()
            or LEGACY_TENDENCIES_FILE.parent != RESULTS_FILE.parent
        ):
            return

        destination_entries: dict[Path, list[tuple[str, ...]]] = {}
        known_keys: dict[Path, set[tuple[str, str]]] = {}
        changed_files: set[Path] = set()
        for line in LEGACY_TENDENCIES_FILE.read_text(encoding="utf-8").splitlines():
            parts = tuple(part.strip() for part in line.split(" | "))
            if len(parts) != 9 or not parts[1].isdigit():
                continue
            try:
                tendency_file = self._tendency_file_for(parts[2])
            except ValueError:
                continue

            if tendency_file not in destination_entries:
                lines = (
                    tendency_file.read_text(encoding="utf-8").splitlines()
                    if tendency_file.exists()
                    else []
                )
                destination_entries[tendency_file] = self._read_tendency_entries(lines)
                known_keys[tendency_file] = {
                    (entry[0], entry[1])
                    for entry in destination_entries[tendency_file]
                }

            key = (parts[0], parts[1])
            if key in known_keys[tendency_file]:
                continue
            destination_entries[tendency_file].append((
                parts[0],
                parts[1],
                parts[3],
                parts[4],
                parts[5],
                parts[6],
                parts[7],
                parts[8],
            ))
            known_keys[tendency_file].add(key)
            changed_files.add(tendency_file)

        for tendency_file in changed_files:
            self._atomic_write_text(
                tendency_file,
                self._tendency_log_text(destination_entries[tendency_file]),
            )

        archive_path = LEGACY_TENDENCIES_FILE.with_name("tendencies.legacy.txt")
        if not archive_path.exists():
            LEGACY_TENDENCIES_FILE.replace(archive_path)

    @staticmethod
    def _tendency_file_for(kind: str) -> Path:
        if kind == "Color":
            return COLOR_TENDENCIES_FILE
        if kind == "Range":
            return RANGE_TENDENCIES_FILE
        raise ValueError(f"Invalid tendency type: {kind!r}")

    @staticmethod
    def _read_tendency_entries(lines: list[str]) -> list[tuple[str, ...]]:
        """Read valid data rows from the tracker-owned tendency log."""
        entries: list[tuple[str, ...]] = []
        for line in lines:
            parts = tuple(part.strip() for part in line.split(" | "))
            if len(parts) != 8 or not parts[1].isdigit():
                continue
            entries.append(parts)
        return entries

    def _reformat_tendency_logs(self) -> None:
        """Keep both human-readable tendency logs as aligned text tables."""
        for tendency_file in (COLOR_TENDENCIES_FILE, RANGE_TENDENCIES_FILE):
            if not tendency_file.exists():
                continue
            entries = self._read_tendency_entries(
                tendency_file.read_text(encoding="utf-8").splitlines()
            )
            self._atomic_write_text(tendency_file, self._tendency_log_text(entries))

    @staticmethod
    def _tendency_log_text(entries: list[tuple[str, ...]]) -> str:
        """Render entries as a fixed-width table suitable for plain-text editors."""
        widths = [
            max(len(title), *(len(entry[index]) for entry in entries))
            if entries
            else len(title)
            for index, title in enumerate(_TENDENCY_LOG_COLUMNS)
        ]
        header = " | ".join(
            title.ljust(widths[index])
            for index, title in enumerate(_TENDENCY_LOG_COLUMNS)
        )
        separator = "-+-".join("-" * width for width in widths)
        rows = [
            " | ".join(
                value.rjust(widths[index]) if index in {1, 3, 7}
                else value.ljust(widths[index])
                for index, value in enumerate(entry)
            )
            for entry in entries
        ]
        return "\n".join((header, separator, *rows)) + "\n"

    @staticmethod
    def _tendency_correct_streak(
        entries: list[tuple[str, ...]],
        pattern: str,
        verdict: str,
    ) -> int:
        """Count prior consecutive correct evaluations of this exact pattern."""
        if verdict != "CORRECT":
            return 0

        streak = 1
        for entry in reversed(entries):
            previous_pattern = entry[2]
            previous_verdict = entry[6]
            if previous_pattern != pattern:
                continue
            if previous_verdict != "CORRECT":
                break
            streak += 1
        return streak

    @staticmethod
    def _format_tendency_distribution(
        outcomes: tuple[tuple[str, int], ...],
        sample_size: int,
    ) -> str:
        if sample_size == 0:
            return "No history"
        return ", ".join(
            f"{label} {count / sample_size:.0%}"
            for label, count in outcomes
        )

    @staticmethod
    def _read_completed_session_results(path: Path) -> tuple[tuple[str, int], ...]:
        """Read one complete, ordered session report, or reject it."""
        name_match = _SESSION_REPORT_NAME_RE.match(path.name)
        if name_match is None:
            return ()

        results: list[tuple[str, int]] = []
        expected_position = 1
        expected_draw_id = int(name_match.group(1))
        for line in path.read_text(encoding="utf-8").splitlines():
            match = _SESSION_REPORT_DRAW_RE.match(line)
            if match is None:
                continue

            position_text, draw_id, result_text = match.groups()
            position = int(position_text)
            if position != expected_position or int(draw_id) != expected_draw_id:
                return ()
            try:
                result = validate_number(int(result_text))
            except ValueError:
                return ()
            results.append((draw_id, result))
            expected_position += 1
            expected_draw_id += 1

        if len(results) != SESSION_DRAW_COUNT:
            return ()
        return tuple(results)

    def read_results(self):
        if not RESULTS_FILE.exists():
            return []

        rows: list[tuple[str, int]] = []
        with RESULTS_FILE.open(encoding="utf-8") as file:
            for line in file:
                stripped = line.strip()

                match = _DRAW_LINE_RE.match(stripped)
                if match:
                    _, draw_id, result = match.groups()
                    rows.append((draw_id, validate_number(int(result))))
                    continue

                # Backward-compatible reader for old raw CSV logs.
                match = _CSV_LINE_RE.match(stripped)
                if match:
                    draw_id, result = match.groups()
                    rows.append((draw_id, validate_number(int(result))))

        return rows
