"""Persistence for the human-readable draw log and session reports."""

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile

from config import (
    ACTIVE_SESSION_FILE,
    INCOMPLETE_SESSIONS_DIR,
    LINE,
    RESULTS_FILE,
    SESSIONS_DIR,
    SESSION_DRAW_COUNT,
)
from models.number_domain import NUMBER_VALUES, number_counts, validate_number


_DRAW_LINE_RE = re.compile(r"^\s*(\d{1,3})\s*\|\s*(\d+)\s*\|\s*(-?\d+)\s*$")
_CSV_LINE_RE = re.compile(r"^\s*(\d+)\s*,\s*(-?\d+)\s*$")


@dataclass(frozen=True, slots=True)
class ActiveSession:
    """Durable state required to resume a session after an interruption."""

    name: str
    start_draw_id: str
    results: list[tuple[str, int]]


class Storage:
    def __init__(self):
        RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        RESULTS_FILE.touch(exist_ok=True)

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

    @classmethod
    def _completed_session_rows(
        cls,
        results: list[tuple[str, int]],
    ) -> list[tuple[str, int]]:
        """Validate a complete, draw-ID-aligned session before finalizing it."""
        if not results:
            raise ValueError("Cannot persist an empty completed session")

        start_draw_id = results[0][0]
        validated_results = cls._validated_results(results, start_draw_id)
        if len(validated_results) != SESSION_DRAW_COUNT:
            raise ValueError(
                f"Completed sessions must contain {SESSION_DRAW_COUNT} draws"
            )
        expected_draw_ids = [
            str(int(start_draw_id) + offset)
            for offset in range(SESSION_DRAW_COUNT)
        ]
        if [draw_id for draw_id, _ in validated_results] != expected_draw_ids:
            raise ValueError(
                "Completed session must contain every consecutive draw ID in "
                "its fixed session boundary"
            )
        return validated_results

    def checkpoint_session(
        self,
        session_name: str,
        start_draw_id: str,
        results: list[tuple[str, int]],
    ) -> None:
        """Atomically save the active session after each accepted draw."""
        validated_results = self._validated_results(results, start_draw_id)
        payload = {
            "version": 1,
            "name": session_name,
            "start_draw_id": start_draw_id,
            "results": validated_results,
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
        if not isinstance(session_name, str) or not isinstance(raw_results, list):
            raise ValueError("Active session checkpoint is missing required fields")

        results = self._validated_results(raw_results, start_draw_id)
        return ActiveSession(
            name=session_name,
            start_draw_id=start_draw_id,
            results=results,
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
        """Keep an unrecoverable partial session without writing a result log."""
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
    def _result_count_lines(results: list[tuple[str, int]]) -> list[str]:
        """Render the completed-session frequency table for the live log."""
        counts = number_counts(result for _, result in results)
        lines = ["RESULT COUNTS", "Number | Count", "-------+------"]
        lines.extend(
            f"{number:>6} | {counts[number]:>5}"
            for number in NUMBER_VALUES
        )
        lines.append(f"Total  | {len(results):>5}")
        return lines

    def append_live_results(
        self,
        start_draw_id: str,
        results: list[tuple[str, int]],
    ) -> tuple[str, ...]:
        """Atomically append newly verified draw rows to the live results log.

        The session checkpoint is the authoritative recovery record. This log
        is idempotent, so a restart can safely call this method again to fill
        any rows written before an interruption.
        """
        validated_results = self._validated_session_rows(
            results,
            start_draw_id,
            require_start_draw=False,
        )
        if not validated_results:
            return ()

        existing = RESULTS_FILE.read_text(encoding="utf-8")
        marker = f"SESSION START : {start_draw_id}"
        seen_draw_ids = {
            match.group(2)
            for line in existing.splitlines()
            if (match := _DRAW_LINE_RE.match(line.strip()))
        }
        new_results = [
            (draw_id, result)
            for draw_id, result in validated_results
            if draw_id not in seen_draw_ids
        ]
        if not new_results:
            return ()

        lines: list[str] = []
        if marker not in existing:
            if existing:
                lines.append("")
            lines.extend(
                (
                    LINE,
                    marker,
                    LINE,
                    "Pos | Draw ID             | Result",
                    "----+---------------------+-------",
                )
            )

        session_start = int(start_draw_id)
        lines.extend(
            f"{int(draw_id) - session_start + 1:>3} | {draw_id:<19} | {result:>6}"
            for draw_id, result in new_results
        )
        self._atomic_write_text(
            RESULTS_FILE,
            existing + "\n".join(lines) + "\n",
        )
        return tuple(draw_id for draw_id, _ in new_results)

    def close_live_session(
        self,
        start_draw_id: str,
        results: list[tuple[str, int]],
    ) -> None:
        """Append count totals and a closing marker once a session is complete."""
        validated_results = self._completed_session_rows(results)
        existing = RESULTS_FILE.read_text(encoding="utf-8")
        marker = f"SESSION START : {start_draw_id}"
        session_start = existing.find(marker)
        if session_start < 0:
            raise ValueError(f"Live session marker is missing: {start_draw_id}")

        next_session = existing.find("SESSION START :", session_start + len(marker))
        session_text = existing[session_start: next_session if next_session >= 0 else None]
        if "SESSION END" in session_text:
            return

        lines = ["", *self._result_count_lines(validated_results), LINE, "SESSION END", LINE]
        self._atomic_write_text(
            RESULTS_FILE,
            existing + "\n".join(lines) + "\n",
        )

    def mark_live_session_incomplete(
        self,
        start_draw_id: str,
        results: list[tuple[str, int]],
        observed_draw_id: str,
        missing_draw_ids: tuple[str, ...],
    ) -> None:
        """Close a live partial session without presenting it as complete."""
        validated_results = self._validated_session_rows(
            results,
            start_draw_id,
            require_start_draw=True,
        )
        existing = RESULTS_FILE.read_text(encoding="utf-8")
        marker = f"SESSION START : {start_draw_id}"
        session_start = existing.find(marker)
        if session_start < 0:
            raise ValueError(f"Live session marker is missing: {start_draw_id}")

        next_session = existing.find("SESSION START :", session_start + len(marker))
        session_text = existing[session_start: next_session if next_session >= 0 else None]
        if "SESSION END" in session_text or "SESSION INCOMPLETE" in session_text:
            return

        lines = [
            "",
            *self._result_count_lines(validated_results),
            f"Missing draw IDs : {', '.join(missing_draw_ids)}",
            f"Observed at      : {observed_draw_id}",
            LINE,
            "SESSION INCOMPLETE",
            LINE,
        ]
        self._atomic_write_text(
            RESULTS_FILE,
            existing + "\n".join(lines) + "\n",
        )

    def append_result(
        self,
        draw_id: str,
        result: int,
    ) -> None:
        """Legacy per-draw writer retained for compatibility callers.

        The runtime uses ``append_live_results`` after every verified draw and
        ``close_live_session`` only when the session reaches completion.
        """
        validate_number(result)
        position = int(draw_id[-1])
        existing = RESULTS_FILE.read_text(encoding="utf-8")
        lines: list[str] = []
        if position == 1:
            if existing:
                lines.append("")
            lines.extend(
                (
                    LINE,
                    f"SESSION START : {draw_id}",
                    LINE,
                    "Pos | Draw ID             | Result",
                    "----+---------------------+-------",
                )
            )

        lines.append(f"{position:>3} | {draw_id:<19} | {result:>6}")

        if position == 0:
            lines.extend((LINE, "SESSION END", LINE))

        suffix = "\n".join(lines) + "\n"
        self._atomic_write_text(RESULTS_FILE, existing + suffix)

    def append_completed_session(self, results: list[tuple[str, int]]) -> None:
        """Finalize a complete session; retained for compatibility callers."""
        validated_results = self._completed_session_rows(results)
        start_draw_id = validated_results[0][0]
        self.append_live_results(start_draw_id, validated_results)
        self.close_live_session(start_draw_id, validated_results)

    def save_session(self, session_name: str, report: str):
        filename = SESSIONS_DIR / f"{session_name}.txt"
        self._atomic_write_text(filename, report)
        return filename

    def clear_results(self):
        self._atomic_write_text(RESULTS_FILE, "")

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
