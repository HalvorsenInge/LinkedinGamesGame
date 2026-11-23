# LinkedinGame — Rules Summary

This file summarizes the core rules, data formats, scoring, and CLI usage for the LinkedinGame project.

1. Overview
- app.py: CLI manager. Reads/writes data.json and results.json and calls scoreboard for computation.
- scoreboard.py: Pure scoring and reporting logic. Exposes load_files, compute_scores, print_report, main().

2. Data files
- data.json: root JSON with two ordered arrays: "players" (ordered list) and "games" (ordered list). Order is significant for reporting.
- results.json: maps game name -> { player: raw_result_string }. Raw strings are preserved; parsing happens in scoreboard.

3. Allowed DNF markers
- Values treated as DNF / missing: "-", "-1", "DNF" (case-insensitive), or empty string. These are parsed to None.

4. Parsing rules
- scoreboard.parse_value interprets:
  - Colon-separated times as decimal-like values: e.g., "3:11" -> 3.11, "1:05" -> 1.05.
  - Plain numeric strings parse to float.
- Unparsable entries are treated as DNF.
- When results are entered through the app or CLI, scoreboard.normalize_result tidies them before saving: times become m:ss ("65" -> "1:05", "1.05"/"1,05" -> "1:05"), Pinpoint becomes a whole number of attempts, and DNF markers become "-". Input that can't be read is rejected instead of being saved.

5. Special-case: Pinpoint
- A game named exactly "pinpoint" (case-insensitive) is treated as a steps-style numeric metric. Values are parsed directly as floats and lower is better.

6. Ranking & scoring
- For each game, players with non-DNF values are ranked by metric (direction depends on game: lower-is-better for times/steps unless otherwise specified).
- Points are a flat table based on finishing position only. Field size does not affect them: winning a game three people finished is worth the same as winning one everybody finished.

  | Position        | Points |
  | --------------- | ------ |
  | 1st, outright   | 10     |
  | 1st, tied       | 9      |
  | 2nd             | 8      |
  | 3rd             | 7      |
  | 4th             | 6      |
  | nth             | 10 - n |
  | DNF             | 0      |

- Positions below 9th are floored at 1 point. A DNF scores 0, so finishing last always beats not finishing.
- Ties take the points of the best position the tie group occupies, and the group consumes the positions it spans: two players tied for 2nd both score 8, and the next player is at position 4 and scores 6. Joint winners are the one exception called out separately above, scoring 9 rather than 10.
- DNF players receive 0 points and are excluded from positive-point ordering.
- Hints: a finisher who used hints loses HINT_PENALTY (3) points, never going below 1, so finishing with hints always beats not playing. They keep their position by time, so nobody else's points change. Hints are stored in hints.json as { game: { player: true } }. Toggle them in the Streamlit app, or add "h" after the result in the CLI (e.g. "1:05h").
- The constants live at the top of scoreboard.py (WIN_POINTS, MIN_FINISHER_POINTS, DNF_POINTS, HINT_PENALTY); change them there rather than in compute_scores.

7. Ordering and determinism
- Iteration and report ordering follow the ordering in data.json (players and games). Do not rely on arbitrary dict order from results.json.

8. IO effects & backups
- app.py mutates data.json and results.json. Back up these files before bulk edits.

9. Running the project
- Run the interactive manager: python app.py
- Print scoreboard and persist a dated snapshot: python scoreboard.py
  - The run saves current totals to scores.json under today's date (e.g., "2026-11-06"). Running again on the same day overwrites that snapshot; scores_summary.json is updated with aggregated stats.
- Run scoring without saving snapshot: python -c "import scoreboard; scoreboard.main(save_snapshot=False)"
- Run scoring via Python: python -c "import scoreboard; scoreboard.main()"

10. Error handling
- Scoreboard functions are defensive: malformed or unparsable results are counted as DNF.

11. Notes for contributors
- Focus logic changes in scoreboard.py; app.py is a thin CLI wrapper.
- If parsing or scoring rules change, update parse_value and compute_scores and add tests if possible.

This summary is intended as a quick reference. For implementation details, open app.py and scoreboard.py.

12. Local database (games.db)
- db.py keeps a SQLite file, games.db, with two tables: results (day, game, player, raw, value, is_steps, hints, rank, points) and daily_totals (day, player, points). value is seconds for timed games and attempts for Pinpoint; NULL means DNF.
- Saving today's snapshot (Streamlit button or python scoreboard.py) writes the day to games.db, replacing anything already saved for that date.
- Days in scores.json that are missing from games.db are imported into daily_totals automatically (no per-game detail for those).
- The Streamlit "Weekly stats" tab reads only from games.db.
- Corrections: Register results -> "Fix a saved day" edits any saved day and recalculates every player's points for it, updating games.db, scores.json and scores_summary.json together. Saving today's results after today's snapshot exists refreshes the snapshot as well. Deleting a day removes it from games.db and scores.json.

13. Weekly score
- The report ends with a "<b>Weekly:</b>" ranking: each player's daily totals summed over the current week (Monday–Sunday), including today's live totals.
- Only snapshots dated in the current week count, so the first day after a weekend or a longer break starts a new week.
- A missing day, or a "-"/"DNF"/non-numeric entry, counts as 0.
- To start a new week early, use "Start new week" (app.py menu option 8, or the Streamlit Scoreboard tab). It writes today's date to week.json; Weekly then counts from today (today included) until the next Monday, when the normal Monday–Sunday week takes over again.
