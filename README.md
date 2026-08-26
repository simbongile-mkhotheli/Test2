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
`...1` boundary. If it observes a later draw, it uses the verified
newest-first browser history to backfill any required IDs still present there.

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

`results.txt` is a human-readable session log rather than an unstructured CSV
stream. Each 30-result session is grouped into a table:

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
completed sessions containing all 30 required IDs are written to `results.txt`.
A restart resumes the incomplete session and performs the same verified-history
recovery when the next stable snapshot arrives. If all 30 results were
captured before interruption, startup finalizes the report and results log
without duplicating it.

If a required draw has aged out of browser history, the session is saved under
`sessions/incomplete/` for review and is never written to `results.txt`.

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
