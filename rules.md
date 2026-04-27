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

5. Special-case: Pinpoint
- A game named exactly "pinpoint" (case-insensitive) is treated as a steps-style numeric metric. Values are parsed directly as floats and lower is better.

6. Ranking & scoring
- For each game, players with non-DNF values are ranked by metric (direction depends on game: lower-is-better for times/steps unless otherwise specified).
- Points assignment: If N players are non-DNF, the best place receives N points, 2nd receives N-1, ..., last receives 1.
- Ties: players that tie share the average of the points for the covered positions (standard averaged-tie scoring).
- DNF players receive -1 points (punished) and are excluded from positive-point ordering.

7. Ordering and determinism
- Iteration and report ordering follow the ordering in data.json (players and games). Do not rely on arbitrary dict order from results.json.

8. IO effects & backups
- app.py mutates data.json and results.json. Back up these files before bulk edits.

9. Running the project
- Run the interactive manager: python app.py
- Print scoreboard and persist a weekday-named snapshot: python scoreboard.py
  - The run saves current totals to scores.json under the weekday key (e.g., "Monday"). Running again on the same weekday overwrites that snapshot; scores_summary.json is updated with aggregated stats.
- Run scoring without saving snapshot: python -c "import scoreboard; scoreboard.main(save_snapshot=False)"
- Run scoring via Python: python -c "import scoreboard; scoreboard.main()"

10. Error handling
- Scoreboard functions are defensive: malformed or unparsable results are counted as DNF.

11. Notes for contributors
- Focus logic changes in scoreboard.py; app.py is a thin CLI wrapper.
- If parsing or scoring rules change, update parse_value and compute_scores and add tests if possible.

This summary is intended as a quick reference. For implementation details, open app.py and scoreboard.py.
