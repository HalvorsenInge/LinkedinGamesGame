import json
import sys
from pathlib import Path
from datetime import datetime

DATA_PATH = Path("data.json")
RESULTS_PATH = Path("results.json")


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


def compute_scores(data, results):
    players = data.get("players", [])
    games = data.get("games", [])

    totals = {p: 0.0 for p in players}
    per_game_results = {}

    for game in games:
        game_results = results.get(game, {})
        parsed = {}
        raw_inputs = {}
        # special-case: Pinpoint is counted in steps where lower is better and values are numeric
        is_steps = str(game).strip().lower() == "pinpoint"
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
        # - Single winner (position 1 alone): 5 points
        # - Joint winners (tie including position 1 with >1 players): 4 points each
        # - 2nd place: 3 points
        # - 3rd place: 2 points
        # - All other non-DNF placings: 1 point
        # - DNF: -1 point
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
            if min_pos == 1:
                if group_size == 1:
                    grp_pts = 5.0
                else:
                    # joint winners
                    grp_pts = 4.0
            elif min_pos == 2:
                grp_pts = 3.0
            elif min_pos == 3:
                grp_pts = 2.0
            else:
                grp_pts = 1.0

            for gp in same_time_group:
                points[gp] = grp_pts
                ranks[gp] = min_pos
            i = j

        # DNF players keep rank as None and get -1 points (punished)
        for p in players:
            if parsed[p] is None:
                ranks[p] = None
                points[p] = -1.0

        for p in players:
            totals[p] += points[p]

        per_game_results[game] = {
            "parsed": parsed,
            "raw": raw_inputs,
            "ranks": ranks,
            "points": points,
            "is_steps": is_steps
        }

    return per_game_results, totals


def print_report(data, per_game_results, totals):
    players = data.get("players", [])
    games = data.get("games", [])

    for game in games:
        print(game)
        info = per_game_results.get(game, {})
        parsed = info.get("parsed", {})
        raw_map = info.get("raw", {})
        is_steps = info.get("is_steps", False)
        # print players in order (DNF last). Lower value is always better.
        order = sorted(players, key=lambda x: (parsed.get(x) is None, parsed.get(x) if parsed.get(x) is not None else float('inf')))
        for p in order:
            raw_val = raw_map.get(p)
            disp = raw_val if raw_val is not None else "-"
            print(f"{p} {disp}")
        print("\n")

    print("Totals")
    # sort totals descending
    sorted_totals = sorted(totals.items(), key=lambda x: x[1], reverse=True)
    for p, v in sorted_totals:
        # show whole numbers without .0
        if v.is_integer():
            vdisp = int(v)
        else:
            vdisp = v
        print(f"{p} {vdisp}")

    # determine winners (highest total)
    if sorted_totals:
        top_score = sorted_totals[0][1]
        winners = [p for p, s in sorted_totals if s == top_score]
        if len(winners) == 1:
            print(f"\nWinner: {winners[0]}")
        else:
            print(f"\nWinners (tie): {', '.join(winners)}")


SCORES_PATH = Path("scores.json")
SUMMARY_PATH = Path("scores_summary.json")


def load_scores(path=SCORES_PATH):
    if path.exists() and path.stat().st_size > 0:
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def save_scores_snapshot(totals, path=SCORES_PATH, label=None):
    scores = load_scores(path)
    weekday = datetime.utcnow().strftime("%A")
    key = weekday
    # store numeric values as numbers; overwrite any existing snapshot for this weekday
    scores[key] = {p: (totals[p] if isinstance(totals[p], (int, float)) else totals[p]) for p in totals}
    path.write_text(json.dumps(scores, indent=2))
    return key


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
    per_game_results, totals = compute_scores(data, results)
    print_report(data, per_game_results, totals)
    if save_snapshot:
        key = save_scores_snapshot(totals)
        summarize_scores()
        print(f"Saved scores snapshot as '{key}' and updated summary ({SUMMARY_PATH}).")


if __name__ == "__main__":
    main()
