# BetGames Tracker

A local Python tracker for the BetGames Wheel of Fortune demo.

The project focuses on reliable draw capture and draw-ID-aligned 30-draw
sessions. Prediction, voting, confidence scoring, adaptive learning, and
model-selection logic are intentionally absent.

## Session model

Sessions are defined by draw IDs, not by the computer clock. A session starts
at a draw ID ending in `1` and contains the next 30 consecutive IDs. For
example, a session beginning at `12608260571` must end at `12608260600`.

The tracker can be launched at any time. It ignores draws until the next valid
`...1` boundary. The compact browser history is used to verify that a result
has rolled in, but it is not used to assign values to older draw IDs because
the website does not expose IDs for those history entries.

## Runtime

```text
main.py
  -> Tracker
      -> FrameFinder
      -> GameReader
      -> SessionManager (orchestration)
          -> SessionState (session rules and state)
          -> Storage
          -> SessionPresenter
```

Game results are integers from `0` through `18`. Invalid values are rejected
before they can enter a session or be saved. The tracker intentionally contains
no prediction or statistical analysis.

## Results log

`results.txt` is the live, human-readable draw log. Every verified result is
appended atomically as soon as it is captured. The detailed report for the
same completed session, including its result counts, is stored as
`sessions/draw-<start-draw-id>.txt`.

```text
======================================================================
SESSION START : 12608180151
======================================================================
Pos | Draw ID             | Result
----+---------------------+-------
  1 | 12608180151         |     15
  2 | 12608180152         |     16
...
 30 | 12608180180         |      3
======================================================================
SESSION END
======================================================================
```

Each completed section in `results.txt` and every detailed session report
includes a `RESULT COUNTS` table for values `0` through `18`, plus a `RANGE
COUNTS` table for `1–6`, `7–12`, and `13–18`. Zero remains a valid result but
is not included in a range count.

The console prints a `RANGE ALERT` once when a range has not appeared for more
than 9 consecutive captured draws. This means the alert triggers at 10
consecutive draws without that range. The alert resets after that range appears
again, and an ongoing alert is shown again when a partial session is restored.
Zero extends the absence streak of every range because it is outside all three
ranges.

During a session, the tracker stores an atomic checkpoint in `sessions/`. A
restart synchronizes any checkpointed rows that were not yet written to
`results.txt`, without duplicating them. If all 30 required IDs were captured
before interruption, startup finalizes the report and completes the live-log
section.

If any required draw ID was not captured by the end of the 30-draw session,
the session is saved under `sessions/incomplete/` for review. Its live-log
section is marked `SESSION INCOMPLETE` and includes the captured-result counts
and missing IDs.

## Requirements

- Python 3.11+
- Playwright
- Chromium

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
