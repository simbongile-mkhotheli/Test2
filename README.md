# BetGames Tracker

A local Python tracker for the BetGames Wheel of Fortune demo.

The project focuses on reliable draw capture and draw-ID-aligned 10-draw
sessions. Prediction, voting, confidence scoring, adaptive learning, and
model-selection logic are intentionally absent.

## Session model

Sessions are defined by draw IDs, not by the computer clock. A session starts
at a draw ID ending in `1` and contains the next 10 consecutive IDs. For
example, a session beginning at `12608260571` ends at `12608260580`.

The tracker can be launched at any time. It ignores draws until the next valid
`...1` boundary. The compact browser history is used to verify that a result
has rolled in, but it is not used to assign values to older draw IDs because
the website does not expose IDs for those history entries.

## Runtime

```text
main.py
  -> Dashboard (Tkinter, main thread)
  -> Tracker worker (Playwright thread)
      -> FrameFinder
      -> GameReader
      -> SessionManager (orchestration)
          -> SessionState (session rules and state)
          -> Storage
          -> SessionPresenter -> EventBus -> Dashboard
      -> AlertMonitor (live results) -> EventBus -> Dashboard
```

Game results are integers from `0` through `18`. Invalid values are rejected
before they can enter a session or be saved. The tracker intentionally contains
no prediction or statistical analysis.

## Results log

`results.txt` is a single live, human-readable draw table. Every verified draw
is appended atomically as soon as it is captured, including draws observed
while the tracker is waiting for a 10-draw session boundary. It is independent
of sessions: it starts collecting after you click **Start tracking**, keeps
going until you stop the program, and never closes or resets at draw 10.

The detailed report for each completed session, including its result counts,
is stored separately as `sessions/draw-<start-draw-id>.txt`.

```text
Pos | Draw ID             | Result
----+---------------------+-------
  1 | 12608180151         |     15
  2 | 12608180152         |     16
```

Every detailed session report includes a `RESULT COUNTS` table for values `0`
through `18`, plus a `RANGE COUNTS` table for `1–6`, `7–12`, and `13–18`.
Zero remains a valid result but is not included in a range count. It also
includes `COLOR COUNTS`: Black (`1, 4, 7, 10, 13, 16`), Gray
(`2, 5, 8, 11, 14, 17`), and Red (`3, 6, 9, 12, 15, 18`). Zero is not assigned
a color.

The desktop dashboard monitors alerts from every verified live draw, not from
individual sessions. It shows a range alert once a range has missed 10
consecutive draws and a color alert once a color has missed 24. An alert resets
after the group appears again, and an ongoing alert is restored from
`results.txt` when tracking starts. Zero extends every range and color absence
streak because it is outside all three ranges and colors.

## Desktop dashboard

Run `python main.py` to open the dashboard and the Playwright browser. Open
Wheel Of Fortune in that browser, then click **Start tracking** in the
dashboard. The application displays the connection status, current session,
latest draw, recent draw table, range and color counts, plus alerts,
without requiring terminal output. Click **Stop** or close the dashboard to
safely stop the tracking worker; the persisted session checkpoint remains
available for resume.

During a session, the tracker stores an atomic checkpoint in `sessions/`. A
restart resumes a partial session or finalizes a completed checkpoint without
duplicating its session report. The root log is written directly from verified
browser draws, rather than from session checkpoints.

If any required draw ID was not captured by the end of the 10-draw session,
the session is saved under `sessions/incomplete/` for review, including its
captured-result counts and missing IDs.

## Requirements

- Python 3.11+
- Playwright
- Chromium
- Tkinter (bundled with the standard Windows Python installer)

Install:

```bash
pip install -r requirements.txt
playwright install chromium
```

Run:

```bash
python main.py
```

Test:

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```
