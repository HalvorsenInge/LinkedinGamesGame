"""Weekly rollup tool
Generates a weekly rollup from scores.json and writes weekly_rollup.json.

Usage:
  python scripts/weekly_rollup.py               # run for current week (Monday..Sunday, UTC)
  python scripts/weekly_rollup.py --week-start 2026-04-06
  python scripts/weekly_rollup.py --scores scores.json --out weekly_rollup.json
"""
from datetime import datetime, timedelta
from pathlib import Path
import json
import argparse

WEEKDAYS = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]


def load_scores(path: Path):
    if not path.exists() or path.stat().st_size == 0:
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}


def parse_key_date(key: str, week_start: datetime.date):
    # Try formats produced by scoreboard:
    # - "Monday" (weekday-only) -> map to week_start + offset
    # - "Monday 2026-04-13T12:34:56" -> parse iso timestamp
    parts = key.split()
    if len(parts) == 1 and parts[0] in WEEKDAYS:
        offset = WEEKDAYS.index(parts[0])
        return week_start + timedelta(days=offset)
    if parts[0] in WEEKDAYS:
        rest = " ".join(parts[1:])
        try:
            dt = datetime.fromisoformat(rest)
            return dt.date()
        except Exception:
            # fallthrough
            pass
    # try to find an ISO-like token in the key
    for token in parts[::-1]:
        try:
            dt = datetime.fromisoformat(token)
            return dt.date()
        except Exception:
            continue
    return None


def to_number(v):
    try:
        return float(v)
    except Exception:
        return None


def find_latest_before(scores_map, cutoff_date):
    # scores_map: dict key->(date, mapping)
    candidates = [(d,k,m) for k,(d,m) in scores_map.items() if d is not None and d < cutoff_date]
    if not candidates:
        return None, None
    # pick latest date
    d,k,m = max(candidates, key=lambda x: x[0])
    return d, m


def find_latest_on_or_before(scores_map, cutoff_date):
    candidates = [(d,k,m) for k,(d,m) in scores_map.items() if d is not None and d <= cutoff_date]
    if not candidates:
        return None, None
    d,k,m = max(candidates, key=lambda x: x[0])
    return d, m


def build_scores_map(scores, week_start_date):
    # returns dict key -> (date, mapping)
    out = {}
    for k,v in scores.items():
        d = parse_key_date(k, week_start_date)
        out[k] = (d, v)
    return out


def weekly_rollup(scores_path: Path, out_path: Path, week_start_str: str = None):
    today = datetime.utcnow().date()
    if week_start_str:
        week_start = datetime.fromisoformat(week_start_str).date()
    else:
        # compute Monday of current week (UTC)
        week_start = today - timedelta(days=(today.weekday()))
    week_end = week_start + timedelta(days=6)

    scores = load_scores(scores_path)
    scores_map = build_scores_map(scores, week_start)

    # Collect snapshots that fall within the week
    snapshots = []  # list of (date, mapping, key)
    for k, (d, m) in scores_map.items():
        if d is None:
            continue
        if week_start <= d <= week_end:
            snapshots.append((d, m, k))
    # also include weekday-only keys mapped (they'll have dates within week)

    # Determine start and end totals per player
    # start_total: latest snapshot before week_start (if none, 0)
    b_date, b_map = find_latest_before(scores_map, week_start)
    e_date, e_map = find_latest_on_or_before(scores_map, week_end)

    players = set()
    for _, m, _ in snapshots:
        players.update(m.keys())
    if b_map:
        players.update(b_map.keys())
    if e_map:
        players.update(e_map.keys())

    result = {
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "generated_at": datetime.utcnow().isoformat(),
        "players": {}
    }

    for p in sorted(players):
        start_val = None
        end_val = None
        if b_map and p in b_map:
            start_val = to_number(b_map.get(p))
        if e_map and p in e_map:
            end_val = to_number(e_map.get(p))
        # fallback to 0 if missing
        if start_val is None:
            start_val = 0.0
        if end_val is None:
            # try best snapshot inside week for this player
            candidate_vals = [to_number(m.get(p)) for d,m,k in snapshots if m.get(p) is not None]
            candidate_vals = [v for v in candidate_vals if v is not None]
            end_val = candidate_vals[-1] if candidate_vals else start_val
        delta = None
        try:
            delta = end_val - start_val
        except Exception:
            delta = None

        # collect per-day values (if available)
        per_day = {}
        for d,m,k in sorted(snapshots, key=lambda x: x[0]):
            val = to_number(m.get(p))
            if val is not None:
                per_day[d.isoformat()] = val
        result["players"][p] = {
            "start_total": start_val,
            "end_total": end_val,
            "delta": delta,
            "snapshots": per_day
        }

    # winners by delta and by end_total
    winners = {"by_delta": [], "by_end_total": []}
    deltas = [(p, (d.get("delta") if isinstance(d:=result["players"][p], dict) else None)) for p in result["players"]]
    # compute best delta
    valid_deltas = [(p, result["players"][p]["delta"]) for p in result["players"] if result["players"][p]["delta"] is not None]
    if valid_deltas:
        max_delta = max(v for _,v in valid_deltas)
        winners["by_delta"] = [p for p,v in valid_deltas if v == max_delta]
    # by end total
    end_totals = [(p, result["players"][p]["end_total"]) for p in result["players"] if result["players"][p]["end_total"] is not None]
    if end_totals:
        max_end = max(v for _,v in end_totals)
        winners["by_end_total"] = [p for p,v in end_totals if v == max_end]

    result["winners"] = winners

    out_path.write_text(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Weekly rollup of scores.json")
    parser.add_argument("--week-start", help="ISO date for week start (Monday) e.g. 2026-04-06", default=None)
    parser.add_argument("--scores", help="Path to scores.json", default="scores.json")
    parser.add_argument("--out", help="Path to output rollup JSON", default="weekly_rollup.json")
    args = parser.parse_args()
    res = weekly_rollup(Path(args.scores), Path(args.out), args.week_start)
    print(f"Wrote weekly rollup to {args.out} for week {res['week_start']}..{res['week_end']}")