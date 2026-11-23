# LinkedIn Games Scoreboard

Track daily results for the LinkedIn puzzle games (Zip, Tango, Queens, Pinpoint, …) and rank players with a points-based scoreboard.

## Setup

Requires Python 3.10+.

```bash
pip install -r requirements.txt
```

## Web app (Streamlit)

```bash
streamlit run streamlit_app.py
```

Then open http://localhost:8501. The app has five tabs:

- **🏆 Scoreboard** – overall winner, top 3, totals chart and a table per game. Use **💾 Save today's snapshot** to store today's results in `games.db` and totals in `scores.json` (keyed by date, e.g. `2026-11-06`) and update `scores_summary.json`.
  The **Weekly** chart sums the days saved this week (Monday–Sunday); **🔄 Start new week** restarts it from today.
- **📊 Weekly stats** – pick a week (Monday–Sunday) and players to see who leads, points through the week, points per game as a heatmap, and each game's times/attempts per day (◆ = hints used). Hover for details; **Table view** shows the numbers. Built from `games.db`, so a day only appears after **💾 Save today's snapshot**.
- **✏️ Register results** – two ways to enter results:
  - **⚡ Quick entry**: pick a player and fill in one time per game, the number of attempts for Pinpoint, and turn on **💡 Hints** for any game where hints were used. Press **Save**.
  - **📋 All results**: edit everyone's results in a grid, tick hints in the checkbox grid below it, and press **Save results**. **Reset all results** clears both grids.

  - **🛠️ Fix a saved day**: pick any saved day, correct results or hints in the same grids and press **Save**. Points for everyone that day are recalculated, and a message shows whose points changed. Days imported from the old `scores.json` only have totals, which you can edit directly. **🗑️ Delete** removes a day saved by mistake.

  Fixing today's results after the snapshot is saved updates the snapshot automatically, so you don't need to save it again.

  Times can be typed as `1:05`, `65` (seconds), `1.05` or `1,05` and are stored as `m:ss`. Leave a game empty or use `-`/`DNF` for did not finish. Nothing is saved if something can't be read; the app tells you which cell is wrong.
- **👥 Players & games** – add or remove players and games. Removing one also removes its results.
- **📈 History** – saved snapshots and the per-player summary.

## Command line

The original CLI still works and uses the same data files:

```bash
python app.py          # interactive menu (see below)
python scoreboard.py   # print the scoreboard and save today's snapshot
python -c "import scoreboard; scoreboard.main(save_snapshot=False)"   # print without saving
```

The `app.py` menu shows on every screen whether today's snapshot is saved, plus a tip line. Options:

| # | Option | Notes |
| --- | --- | --- |
| 1 | Register results | Pick a game or `all`. Enter keeps a value, add `h` for hints (`1:05h`), times like `65` or `1.05` are fine. Unreadable input is asked again. Updates today's snapshot if it is already saved, otherwise reminds you to save it |
| 2–5 | Add/remove player or game | |
| 6 | Show scoreboard | |
| 7 | Reset results | Clears today's results and hints; saved days are kept |
| 8 | Start new week | |
| 9 | Save today's snapshot | Writes today to `games.db` and `scores.json` |
| 10 | Fix a saved day | Shows that day's results, lets you re-enter any game and recalculates everyone's points, then prints whose points changed. Totals-only days (old `scores.json`) are edited as totals |
| 11 | Delete a saved day | Asks for confirmation |
| 12 | Weekly stats | This week's points per day, total, hints used and a bar per player |
| 0 / q | Exit | (Exit used to be 9) |

## Data files

| File | Contents |
| --- | --- |
| `data.json` | Ordered lists of `players` and `games` |
| `results.json` | Raw results per game and player |
| `hints.json` | Which results used hints (`{game: {player: true}}`) |
| `scores.json` | Saved daily totals, keyed by date |
| `games.db` | SQLite history of every saved day: each result per game and player (time in seconds or attempts, hints, rank, points) and daily totals. Created automatically; old `scores.json` days are imported as totals only |
| `week.json` | Date a new week was started manually (optional) |
| `scores_summary.json` | Aggregated stats per player across snapshots |

## Scoring

Lower time (or fewer Pinpoint guesses) is better. A sole winner gets 10 points, joint winners 9, and every other position *n* gets `10 - n` (minimum 1). DNF scores 0. Using hints costs 3 points (never below 1, so it always beats a DNF) without changing anyone's position. See [rules.md](rules.md) for the full rules.
