"""Small local SQLite store of every saved day, used for the weekly graphs.

results.json / hints.json stay the place where today's results are edited.
Saving a snapshot copies the day into games.db (and keeps scores.json and
scores_summary.json in step, since the Weekly score is read from there):

- results:       one row per day, game and player (raw result, seconds or
                 attempts, hints, rank and points)
- daily_totals:  one row per day and player. Days imported from the old
                 scores.json only exist here, without per-game detail.
"""
import sqlite3
from datetime import date
from pathlib import Path

import scoreboard

DB_PATH = Path("games.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS results (
    day     TEXT NOT NULL,
    game    TEXT NOT NULL,
    player  TEXT NOT NULL,
    raw     TEXT,
    value   REAL,              -- seconds for timed games, attempts for Pinpoint; NULL = DNF
    is_steps INTEGER NOT NULL DEFAULT 0,
    hints   INTEGER NOT NULL DEFAULT 0,
    rank    INTEGER,
    points  REAL NOT NULL,
    PRIMARY KEY (day, game, player)
);
CREATE TABLE IF NOT EXISTS daily_totals (
    day     TEXT NOT NULL,
    player  TEXT NOT NULL,
    points  REAL NOT NULL,
    PRIMARY KEY (day, player)
);
"""


def connect(path=DB_PATH):
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    return con


def to_seconds(raw):
    """'1:05' -> 65, '1:02:03' -> 3723, DNF/unreadable -> None."""
    if scoreboard.is_dnf_value(raw):
        return None
    try:
        parts = [int(x) for x in str(raw).strip().split(":")]
    except ValueError:
        return None
    secs = 0
    for x in parts:
        secs = secs * 60 + x
    return float(secs)


def save_day(data, results, hints, day=None, path=DB_PATH):
    """Store one day's results and totals, replacing anything saved for that day.

    Used both for today's snapshot and for correcting an earlier day: points
    for every player are recalculated from the results passed in.
    """
    day_date = day or date.today()
    day = day_date.isoformat()
    per_game, totals = scoreboard.compute_scores(data, results, hints)
    rows = []
    for game, info in per_game.items():
        for p in data.get("players", []):
            raw = info["raw"].get(p)
            if info["is_steps"]:
                value = info["parsed"].get(p)
            else:
                value = to_seconds(raw)
            rows.append((day, game, p, raw, value, int(info["is_steps"]),
                         int(info["hints"].get(p, False)), info["ranks"].get(p), info["points"][p]))
    with connect(path) as con:
        con.execute("DELETE FROM results WHERE day = ?", (day,))
        con.execute("DELETE FROM daily_totals WHERE day = ?", (day,))
        con.executemany("INSERT INTO results VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
        con.executemany("INSERT INTO daily_totals VALUES (?, ?, ?)",
                        [(day, p, v) for p, v in totals.items()])
    con.close()
    _update_scores_json(day_date, totals)
    return day


def save_totals(day, totals, path=DB_PATH):
    """Correct the totals of a day that has no per-game results (imported from scores.json)."""
    with connect(path) as con:
        con.execute("DELETE FROM daily_totals WHERE day = ?", (day.isoformat(),))
        con.executemany("INSERT INTO daily_totals VALUES (?, ?, ?)",
                        [(day.isoformat(), p, float(v)) for p, v in totals.items()])
    con.close()
    _update_scores_json(day, totals)


def delete_day(day, path=DB_PATH):
    """Remove a saved day everywhere (games.db and scores.json)."""
    with connect(path) as con:
        con.execute("DELETE FROM results WHERE day = ?", (day.isoformat(),))
        con.execute("DELETE FROM daily_totals WHERE day = ?", (day.isoformat(),))
    con.close()
    scoreboard.delete_scores_snapshot(day)
    scoreboard.summarize_scores()


def _update_scores_json(day, totals):
    scoreboard.save_scores_snapshot(totals, day=day)
    scoreboard.summarize_scores()


def saved_days(path=DB_PATH):
    """[(date, has_per_game_results)], newest first."""
    _, rows = query(
        "SELECT t.day, EXISTS (SELECT 1 FROM results r WHERE r.day = t.day) "
        "FROM (SELECT DISTINCT day FROM daily_totals) t ORDER BY t.day DESC", path=path)
    return [(date.fromisoformat(d), bool(detail)) for d, detail in rows]


def load_day(day, current=None, path=DB_PATH):
    """A saved day as (data, results, hints), in the same shape as the JSON files.

    Players and games follow the current data.json order, with any that have
    since been removed added at the end.
    """
    _, rows = query("SELECT game, player, raw, hints FROM results WHERE day = ? ORDER BY rowid",
                    (day.isoformat(),), path=path)
    current = current or {}

    def ordered(names, preferred):
        names = list(dict.fromkeys(names))
        return [n for n in preferred if n in names] + [n for n in names if n not in preferred]

    data = {
        "players": ordered([r[1] for r in rows], current.get("players", [])),
        "games": ordered([r[0] for r in rows], current.get("games", [])),
    }
    results, hints = {}, {}
    for game, player, raw, hint in rows:
        results.setdefault(game, {})[player] = raw or ""
        if hint:
            hints.setdefault(game, {})[player] = True
    return data, results, hints


def load_totals(day, path=DB_PATH):
    _, rows = query("SELECT player, points FROM daily_totals WHERE day = ?", (day.isoformat(),), path=path)
    return dict(rows)


def import_scores_json(scores=None, path=DB_PATH):
    """Copy old scores.json snapshots into daily_totals. Days already in the db are left alone."""
    scores = scoreboard.load_scores() if scores is None else scores
    rows = []
    for key, snap in scores.items():
        if scoreboard._snapshot_date(key) is None:
            continue
        rows += [(key, p, scoreboard._to_points(v)) for p, v in snap.items()]
    with connect(path) as con:
        known = {d for (d,) in con.execute("SELECT DISTINCT day FROM daily_totals")}
        con.executemany("INSERT INTO daily_totals VALUES (?, ?, ?)",
                        [r for r in rows if r[0] not in known])
    con.close()


def query(sql, params=(), path=DB_PATH):
    """Run a SELECT and return (column names, rows)."""
    con = connect(path)
    try:
        cur = con.execute(sql, params)
        return [c[0] for c in cur.description], cur.fetchall()
    finally:
        con.close()
