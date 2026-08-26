"""Compact human-readable session report."""

from config import LINE
from models.number_domain import NUMBER_VALUES


class SessionReport:
    def __init__(
        self,
        session_name: str,
        results: list[tuple[str, int]],
        stats,
    ):
        self.session_name = session_name
        self.results = results
        self.stats = stats
        self._lines: list[str] = []

    def append(self, text: str = ""):
        self._lines.append(text)

    def line(self, char: str = "-", length: int = 70):
        self._lines.append(char * length)

    def _add_draw_table(self):
        self.append("DRAWS")
        self.line()
        self.append("Pos  Draw ID             Result")
        self.append("---  -----------------   ------")
        for position, (draw_id, result) in enumerate(self.results, start=1):
            self.append(f"{position:02d}   {draw_id:<19} {result:>6}")
        self.append("")

    def _add_session_shape(self):
        start_id = self.results[0][0] if self.results else "-"
        end_id = self.results[-1][0] if self.results else "-"
        self.append("SESSION")
        self.line()
        self.append(f"Start draw : {start_id}")
        self.append(f"End draw   : {end_id}")
        self.append(f"Draw count : {len(self.results)}")
        self.append("")

    def _add_gaps(self):
        gaps = self.stats.gaps
        self.append("GAPS")
        self.line()
        self.append("Number | Current gap | Longest gap")
        self.append("-------+-------------+------------")

        ranked = sorted(
            NUMBER_VALUES,
            key=lambda number: (
                -gaps.current_gaps[number],
                -gaps.longest_gaps[number],
                number,
            ),
        )

        for number in ranked:
            last_gap = gaps.last_gaps[number]
            last_text = "-" if last_gap is None else str(last_gap)
            self.append(
                f"{number:>6} |"
                f" {gaps.current_gaps[number]:>11} |"
                f" {last_text:>8} |"
                f" {gaps.longest_gaps[number]:>11}"
            )

        self.append("")
        self.append(f"Largest longest gap : {gaps.largest_gap} draws")
        self.append(
            "Longest-gap leaders : "
            + (", ".join(map(str, gaps.gap_leaders)) or "None")
        )
        self.append(
            "Seen in session     : "
            + (", ".join(map(str, gaps.active_numbers)) or "None")
        )
        self.append("")

    def build(self) -> str:
        self._lines = []
        self.append(LINE)
        self.append("BETGAMES SESSION REPORT")
        self.append(LINE)
        self.append(f"Session: {self.session_name}")
        self.append("")

        self._add_session_shape()
        self._add_draw_table()
        self._add_gaps()

        self.append(LINE)
        return "\n".join(self._lines)

    def text(self) -> str:
        return self.build()

    def print(self):
        print(self.text())
