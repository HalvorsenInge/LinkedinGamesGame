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

Then open http://localhost:8501. The app has four tabs:

- **🏆 Scoreboard** – overall winner, top 3, totals chart and a table per game. Use **💾 Save today's snapshot** to store today's totals in `scores.json` (keyed by date, e.g. `2026-11-06`) and update `scores_summary.json`.
  The **Weekly** chart sums the days saved this week (Monday–Sunday); **🔄 Start new week** restarts it from today.
- **✏️ Register results** – edit everyone's results in a grid and press **Save results**. Enter times as `m:ss` and Pinpoint as number of guesses; use `-` or `DNF` for did not finish. **Reset all results** clears the grid.
- **👥 Players & games** – add or remove players and games. Removing one also removes its results.
- **📈 History** – saved snapshots and the per-player summary.

## Command line

The original CLI still works and uses the same data files:

```bash
python app.py          # interactive menu: register results, manage players/games, show scoreboard
python scoreboard.py   # print the scoreboard and save today's snapshot
python -c "import scoreboard; scoreboard.main(save_snapshot=False)"   # print without saving
```

## Data files

| File | Contents |
| --- | --- |
| `data.json` | Ordered lists of `players` and `games` |
| `results.json` | Raw results per game and player |
| `scores.json` | Saved daily totals, keyed by date |
| `week.json` | Date a new week was started manually (optional) |
| `scores_summary.json` | Aggregated stats per player across snapshots |

## Scoring

Lower time (or fewer Pinpoint guesses) is better. A sole winner gets 10 points, joint winners 9, and every other position *n* gets `10 - n` (minimum 1). DNF scores 0. See [rules.md](rules.md) for the full rules.
