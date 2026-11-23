import json
import sys
from pathlib import Path
from datetime import date, timedelta

DATA_PATH = Path("data.json")
RESULTS_PATH = Path("results.json")
HINTS_PATH = Path("hints.json")

# Scoring table: sole winner takes WIN_POINTS, everyone else takes
# WIN_POINTS - position (so joint winners 9, 2nd 8, 3rd 7, ...), never
# dropping below MIN_FINISHER_POINTS. A DNF simply scores DNF_POINTS, so
# finishing last is still worth more than not finishing.
WIN_POINTS = 10
MIN_FINISHER_POINTS = 1
DNF_POINTS = 0.0
# Finishing with hints costs HINT_PENALTY points, but never below
# MIN_FINISHER_POINTS, so finishing with hints always beats a DNF.
# The player keeps their place by time, so nobody else's points change.
HINT_PENALTY = 3.0


def is_steps_game(game):
    """Pinpoint is scored in attempts/guesses rather than time."""
    return str(game).strip().lower() == "pinpoint"


def is_dnf_value(val):
    return val is None or str(val).strip().lower() in ("", "-", "-1", "dnf")


def normalize_result(val, is_steps=False):
    """Tidy a typed result into the stored form. Returns (value, error).

    Empty stays "" and any DNF marker becomes "-". Attempts become a whole
    number. Times become m:ss and also accept "65" (seconds), "1.05", "1,05"
    and "1 05". error is None when the input was understood.
    """
    s = "" if val is None else str(val).strip().replace('\u00A0', '').replace('：', ':')
    if s == "":
        return "", None
    if is_dnf_value(s):
        return "-", None
    if is_steps:
        try:
            n = float(s.replace(',', '.'))
        except ValueError:
            return None, f"'{s}' is not a number of attempts"
        if n < 1 or not n.is_integer():
            return None, f"'{s}' is not a number of attempts"
        return str(int(n)), None

    for sep in ('.', ',', ' '):
        s = s.replace(sep, ':')
    try:
        parts = [int(x) for x in s.split(':')]
    except ValueError:
        return None, f"'{val}' is not a time (use m:ss)"
    if any(x < 0 for x in parts):
        return None, f"'{val}' is not a time (use m:ss)"
    if len(parts) == 1:
        m, sec = divmod(parts[0], 60)
        return f"{m}:{sec:02d}", None
    if len(parts) == 2 and parts[1] < 60:
        return f"{parts[0]}:{parts[1]:02d}", None
    if len(parts) == 3 and parts[1] < 60 and parts[2] < 60:
        return f"{parts[0]}:{parts[1]:02d}:{parts[2]:02d}", None
    return None, f"'{val}' is not a time (use m:ss)"


def load_hints(path=HINTS_PATH):
    """{game: {player: True}} for every result where hints were used."""
    try:
        return json.loads(path.read_text()) if path.exists() and path.stat().st_size > 0 else {}
    except json.JSONDecodeError:
        return {}


def save_hints(hints, path=HINTS_PATH):
    """Store only the results where hints were used."""
    clean = {g: {p: True for p, used in ps.items() if used} for g, ps in hints.items()}
    path.write_text(json.dumps({g: ps for g, ps in clean.items() if ps}, indent=2))


def used_hints(hints, game, player):
    return bool((hints or {}).get(game, {}).get(player))


def parse_time(val):
    # kept for backward compatibility but not used in new float-based comparison
    return parse_value(val)


def parse_value(val, is_steps=False):
    """Parse input into a float for comparison, while preserving the raw input.
    Rules:
    - "3" -> 3.0
    - "3:11" -> 3.11 (float)
    - "1:05" -> 1.05
    - "-", "-1", "DNF", empty -> None
    - For steps (Pinpoint), integers/floats parsed directly to float
    """
    if val is None:
        return None
    s = str(val).strip()
    if s == "" or s in ("-", "-1") or s.lower() == "dnf":
        return None
    s = s.replace('\u00A0', '').replace('：', ':').strip()

    # For steps mode just parse as float if possible
    if is_steps:
        try:
            return float(s)
        except Exception:
            return None

    # If contains ':' -> m:ss or h:mm:ss; flatten to m.ss (seconds as two digits)
    if ':' in s:
        parts = s.split(':')
        try:
            parts = [int(p) for p in parts]
        except Exception:
            return None
        if len(parts) == 2:
            m, sec = parts
            return float(f"{m}.{sec:02d}")
        elif len(parts) == 3:
            h, m, sec = parts
            # convert to total minutes representation h*60 + m.ss? user requested m:ss -> m.ss approach,
            # for hours convert to minutes with hours*60 then append seconds as two digits
            total_minutes = h * 60 + m
            return float(f"{total_minutes}.{sec:02d}")
        else:
            return None

    # plain numeric
    try:
        return float(s)
    except Exception:
        return None


def format_time(seconds):
    if seconds is None:
        return "-"
    try:
        seconds = int(seconds)
        m = seconds // 60
        s = seconds % 60
        return f"{m}:{s:02d}" if m > 0 else f"0:{s:02d}" if s < 60 else str(seconds)
    except Exception:
        return str(seconds)


def load_files(data_path=DATA_PATH, results_path=RESULTS_PATH):
    if not data_path.exists():
        raise SystemExit(f"Missing {data_path}. Create it with players and games arrays.")
    data = json.loads(data_path.read_text())
    if results_path.exists() and results_path.stat().st_size > 0:
        results = json.loads(results_path.read_text())
    else:
        results = {}
    return data, results


def compute_scores(data, results, hints=None):
    players = data.get("players", [])
    games = data.get("games", [])

    totals = {p: 0.0 for p in players}
    per_game_results = {}

    for game in games:
        game_results = results.get(game, {})
        parsed = {}
        raw_inputs = {}
        # special-case: Pinpoint is counted in steps where lower is better and values are numeric
        is_steps = is_steps_game(game)
        for p in players:
            raw = game_results.get(p)
            raw_s = None if raw is None else str(raw).strip()
            raw_inputs[p] = raw_s if raw_s not in ("",) else None

            if raw_s is None or raw_s in ("", "-", "-1") or (isinstance(raw_s, str) and raw_s.lower() == "dnf"):
                parsed[p] = None
            else:
                if is_steps:
                    try:
                        parsed[p] = float(raw_s)
                    except Exception:
                        parsed[p] = None
                else:
                    parsed[p] = parse_value(raw_s, is_steps=False)

        # sort: None (DNF) last; lower value is better
        sorted_players = sorted(players, key=lambda x: (parsed[x] is None, parsed[x] if parsed[x] is not None else float('inf')))

        # Assign ranks and points using new rules:
        # - Single winner (position 1 alone): 10 points
        # - Joint winners (tie including position 1 with >1 players): 9 points each
        # - Every other placing: 10 - position, i.e. 2nd -> 8, 3rd -> 7, 4th -> 6, ...
        # - Never below MIN_FINISHER_POINTS, so a large field cannot score 0 or negative
        # - DNF: 0 points
        # A tie group consumes the positions it spans: two players tied for 2nd both
        # take 8, and the next player sits at position 4 and takes 6.
        non_dnfs = [p for p in sorted_players if parsed[p] is not None]
        n = len(non_dnfs)

        ranks = {}
        points = {p: 0.0 for p in players}

        i = 0
        while i < n:
            p = non_dnfs[i]
            same_time_group = [p]
            j = i + 1
            while j < n and parsed[non_dnfs[j]] == parsed[p]:
                same_time_group.append(non_dnfs[j])
                j += 1
            # positions covered: i+1 .. j
            min_pos = i + 1
            group_size = len(same_time_group)
            # decide points for the group based on the (minimum) position they occupy
            if min_pos == 1 and group_size == 1:
                grp_pts = float(WIN_POINTS)
            else:
                # joint winners fall out of this as 10 - 1 = 9
                grp_pts = float(max(WIN_POINTS - min_pos, MIN_FINISHER_POINTS))

            for gp in same_time_group:
                points[gp] = grp_pts
                ranks[gp] = min_pos
            i = j

        # DNF players keep rank as None and score DNF_POINTS
        for p in players:
            if parsed[p] is None:
                ranks[p] = None
                points[p] = DNF_POINTS

        # Hints cost points but not position
        hinted = {p: used_hints(hints, game, p) for p in players}
        for p in players:
            if hinted[p] and parsed[p] is not None:
                points[p] = max(points[p] - HINT_PENALTY, MIN_FINISHER_POINTS)

        for p in players:
            totals[p] += points[p]

        per_game_results[game] = {
            "parsed": parsed,
            "raw": raw_inputs,
            "ranks": ranks,
            "points": points,
            "hints": hinted,
            "is_steps": is_steps
        }

    return per_game_results, totals


def print_report(data, per_game_results, totals, weekly=None):
    players = data.get("players", [])
    games = data.get("games", [])

    for game in games:
        print(game)
        info = per_game_results.get(game, {})
        points = info.get("points", {})
        raw_map = info.get("raw", {})
        hint_map = info.get("hints", {})
        sorted_game = sorted(players, key=lambda p: points.get(p, 0), reverse=True)
        emojis = ["🥇", "🥈", "🥉"]

        def result_display(p):
            raw_val = raw_map.get(p)
            if is_dnf_value(raw_val):
                return "DNF"
            return f"{raw_val} 💡" if hint_map.get(p) else raw_val

        for i, p in enumerate(sorted_game[:3]):
            print(f"{emojis[i]} {p} ({result_display(p)}): {_fmt_points(points.get(p, 0))}")

        if len(sorted_game) > 3:
            others = ", ".join(
                f"{p} ({result_display(p)}) {_fmt_points(points.get(p, 0))}" for p in sorted_game[3:]
            )
            print(f"Others: {others}")
        print("\n")

    print("Totals")
    _print_ranking(totals)

    # determine winners (highest total)
    sorted_totals = sorted(totals.items(), key=lambda x: x[1], reverse=True)
    if sorted_totals:
        top_score = sorted_totals[0][1]
        winners = [p for p, s in sorted_totals if s == top_score]
        if len(winners) == 1:
            print(f"\nWinner: {winners[0]}")
        else:
            print(f"\nWinners (tie): {', '.join(winners)}")

    if weekly is None:
        weekly = compute_weekly(data, totals)
    print("\n<b>Weekly:</b>")
    _print_ranking(weekly)


def _fmt_points(v):
    return int(v) if float(v).is_integer() else v


def _print_ranking(scores):
    """Print a points mapping as top 3 with medals followed by an Others line."""
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    emojis = ["🥇", "🥈", "🥉"]

    for i, (p, v) in enumerate(ranked[:3]):
        print(f"{emojis[i]} {p}: {_fmt_points(v)}")

    if len(ranked) > 3:
        others = ", ".join(f"{p} {_fmt_points(v)}" for p, v in ranked[3:])
        print(f"Others: {others}")


def _to_points(val):
    """Snapshot value -> float. "-", "DNF", empty or anything unparsable counts as 0."""
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def _snapshot_date(key):
    """Snapshot key ("2026-11-06") -> date, or None for old weekday-only keys."""
    try:
        return date.fromisoformat(key)
    except (TypeError, ValueError):
        return None


def compute_weekly(data, totals, path=None, today=None):
    """Sum each player's saved daily snapshots for the current week (Monday-Sunday).

    Only snapshots dated in the same week as ``today`` count, so the first
    snapshot after a weekend (or a longer break) starts a new week. A week
    started manually with start_new_week() counts from that day instead,
    until the next Monday. Today's
    snapshot is replaced by the live ``totals`` so the weekly figure includes
    today even before it has been saved. A day where a player has no entry,
    or an entry like "-", counts as 0.
    """
    today = today or date.today()
    week_start = today - timedelta(days=today.weekday())
    manual_start = get_manual_week_start()
    if manual_start and week_start < manual_start <= today:
        week_start = manual_start
    scores = load_scores(path or SCORES_PATH)
    scores[today.isoformat()] = totals
    weekly = {p: 0.0 for p in data.get("players", [])}
    for key, snap in scores.items():
        d = _snapshot_date(key)
        if d is None or not (week_start <= d <= today):
            continue
        for p in weekly:
            weekly[p] += _to_points(snap.get(p))
    return weekly


SCORES_PATH = Path("scores.json")
SUMMARY_PATH = Path("scores_summary.json")
WEEK_PATH = Path("week.json")


def get_manual_week_start(path=WEEK_PATH):
    """Date a new week was started manually, or None."""
    try:
        return date.fromisoformat(json.loads(path.read_text())["week_start"])
    except Exception:
        return None


def start_new_week(day=None, path=WEEK_PATH):
    """Start a new weekly score from ``day`` (default today, which is included)."""
    day = day or date.today()
    path.write_text(json.dumps({"week_start": day.isoformat()}, indent=2))
    return day


def load_scores(path=SCORES_PATH):
    if path.exists() and path.stat().st_size > 0:
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def save_scores_snapshot(totals, path=SCORES_PATH, label=None, day=None):
    scores = load_scores(path)
    key = (day or date.today()).isoformat()
    # store numeric values as numbers; overwrite any existing snapshot for that day
    scores[key] = {p: (totals[p] if isinstance(totals[p], (int, float)) else totals[p]) for p in totals}
    path.write_text(json.dumps(scores, indent=2))
    return key


def delete_scores_snapshot(day, path=SCORES_PATH):
    """Remove one day's snapshot. Returns True if it existed."""
    scores = load_scores(path)
    if scores.pop(day.isoformat(), None) is None:
        return False
    path.write_text(json.dumps(scores, indent=2))
    return True


def summarize_scores(path=SCORES_PATH, out_path=SUMMARY_PATH):
    scores = load_scores(path)
    agg = {}
    # sort keys to have deterministic order (timestamps present)
    for snap_key in sorted(scores.keys()):
        snap = scores[snap_key]
        for p, v in snap.items():
            try:
                val = float(v)
            except Exception:
                # skip non-numeric
                continue
            entry = agg.setdefault(p, {"total": 0.0, "count": 0, "best": None, "worst": None, "last_snapshot": None})
            entry["total"] += val
            entry["count"] += 1
            entry["best"] = val if entry["best"] is None or val > entry["best"] else entry["best"]
            entry["worst"] = val if entry["worst"] is None or val < entry["worst"] else entry["worst"]
            entry["last_snapshot"] = snap_key
    for p, e in agg.items():
        e["average"] = e["total"] / e["count"] if e["count"] > 0 else None
    out_path.write_text(json.dumps(agg, indent=2))
    return agg


def main(save_snapshot=True):
    data, results = load_files()
    per_game_results, totals = compute_scores(data, results, load_hints())
    print_report(data, per_game_results, totals)
    if save_snapshot:
        import db
        key = db.save_day(data, results, load_hints())
        print(f"Saved scores snapshot as '{key}' and updated summary ({SUMMARY_PATH}).")


if __name__ == "__main__":
    main()
