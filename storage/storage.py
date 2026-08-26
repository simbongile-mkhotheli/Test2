"""Persistence for the human-readable draw log and session reports."""

import re

from config import LINE, RESULTS_FILE, SESSIONS_DIR
from models.number_domain import validate_number


_DRAW_LINE_RE = re.compile(r"^\s*(\d{1,3})\s*\|\s*(\d+)\s*\|\s*(-?\d+)\s*$")
_CSV_LINE_RE = re.compile(r"^\s*(\d+)\s*,\s*(-?\d+)\s*$")


class Storage:
    def __init__(self):
        RESULTS_FILE.touch(exist_ok=True)

    def append_result(
        self,
        draw_id: str,
        result: int,
    ) -> None:
        validate_number(result)
        position = int(draw_id[-1])
        if position == 1:
            with RESULTS_FILE.open("a", encoding="utf-8") as file:
                if RESULTS_FILE.stat().st_size:
                    file.write("\n")
                file.write(LINE + "\n")
                file.write(f"SESSION START : {draw_id}\n")
                file.write(LINE + "\n")
                file.write("Pos | Draw ID             | Result\n")
                file.write("----+---------------------+-------\n")

        with RESULTS_FILE.open("a", encoding="utf-8") as file:
            file.write(f"{position:>3} | {draw_id:<19} | {result:>6}\n")

        if position == 0:
            with RESULTS_FILE.open("a", encoding="utf-8") as file:
                file.write(LINE + "\n")
                file.write("SESSION END\n")
                file.write(LINE + "\n")

    def save_session(self, session_name: str, report: str):
        filename = SESSIONS_DIR / f"{session_name}.txt"
        filename.write_text(report, encoding="utf-8")
        return filename

    def clear_results(self):
        RESULTS_FILE.write_text("", encoding="utf-8")

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
