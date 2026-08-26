# BetGames Tracker

A local Python tracker for the BetGames Wheel of Fortune demo.

The project focuses on reliable draw capture and draw-ID-based 30-draw
sessions. Prediction, voting, confidence scoring, adaptive learning, and
model-selection logic are intentionally absent.

## Session model

Sessions are defined by the draw ID, not by the computer clock.

A session starts at a draw ID ending in `1` and contains exactly 30 consecutive
draws, ending at an ID ending in `0`:

```text
12608180151  # 01
12608180152  # 02
...
12608180160  # 10
...
12608180170  # 20
...
12608180180  # 30 / session end
```

The tracker can be launched at any time. It ignores draws until the next valid
`...1` boundary and rejects gaps in the active 30-draw sequence.

## Runtime

```text
main.py
  -> Tracker
      -> FrameFinder
      -> GameReader
      -> SessionManager (orchestration)
          -> SessionState (session rules and state)
          -> Storage
          -> Statistics
              -> AnalyticsPipeline -> Gaps
          -> SessionPresenter -> SessionReport
```

## Analytics retained

Only descriptive analytics that remain useful for understanding the captured
session are kept:

- Gaps — longest gaps and active numbers.

Game results are integers from `0` through `18`. Invalid values are rejected
before they can enter a session, be saved, or be analyzed.

Removed analytics include frequency, transition matrices, next-number
prediction, recency, clusters, mirrors, streak summaries, rare numbers, heat,
and prediction/learning infrastructure.

## Results log

`results.txt` is now a human-readable session log rather than an unstructured
CSV stream. Each 30-draw session is grouped into a table:

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

The parser remains compatible with the previous `draw_id,result` format so
existing historical data can still be read.

During a session, the tracker stores an atomic checkpoint in `sessions/`; only
completed 30-draw sessions are written to `results.txt`. A restart resumes the
incomplete session when its next draw is still available; if all 30 draws were
captured before interruption, startup finalizes the report and results log
without duplicating it.

If the tracker misses one or more draw IDs, the incomplete session cannot be
completed reliably. It is saved to `sessions/abandoned/` with the reason and
first observed draw after the gap, then the tracker waits for the next valid
`...1` session boundary instead of stopping.

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
python -m pytest -q
```

Gap semantics:
- Current gap = completed draws since the number last appeared.
- Longest gap = longest consecutive absence run within the session.
- A number not seen in the session has a current and longest gap equal to the session draw count.
