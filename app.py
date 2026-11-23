import json
from pathlib import Path
import sys

DATA_PATH = Path("data.json")
RESULTS_PATH = Path("results.json")


def load_data():
    if not DATA_PATH.exists():
        DATA_PATH.write_text(json.dumps({"players": [], "games": []}, indent=2))
    return json.loads(DATA_PATH.read_text())


def save_data(data):
    DATA_PATH.write_text(json.dumps(data, indent=2))


def load_results():
    if not RESULTS_PATH.exists():
        return {}
    try:
        txt = RESULTS_PATH.read_text()
        if not txt.strip():
            return {}
        return json.loads(txt)
    except json.JSONDecodeError:
        return {}


def save_results(results):
    RESULTS_PATH.write_text(json.dumps(results, indent=2))


def add_player():
    data = load_data()
    name = input("Enter new player name: ").strip()
    if not name:
        print("Empty name, aborted.")
        return
    if name in data.get("players", []):
        print("Player already exists.")
        return
    data["players"].append(name)
    save_data(data)
    print(f"Added player {name}.")


def remove_player():
    data = load_data()
    players = data.get("players", [])
    if not players:
        print("No players to remove.")
        return
    print("Players:")
    for i, p in enumerate(players, 1):
        print(f"{i}. {p}")
    choice = input("Enter number of player to remove: ")
    try:
        idx = int(choice) - 1
        if idx < 0 or idx >= len(players):
            print("Invalid selection.")
            return
    except ValueError:
        print("Invalid input.")
        return
    name = players.pop(idx)
    save_data(data)
    # remove from results
    results = load_results()
    for game in list(results.keys()):
        if name in results[game]:
            del results[game][name]
    save_results(results)
    import scoreboard
    hints = scoreboard.load_hints()
    for game in hints.values():
        game.pop(name, None)
    scoreboard.save_hints(hints)
    print(f"Removed player {name} and cleared their results.")


def add_game():
    data = load_data()
    name = input("Enter new game name: ").strip()
    if not name:
        print("Empty name, aborted.")
        return
    if name in data.get("games", []):
        print("Game already exists.")
        return
    data["games"].append(name)
    save_data(data)
    # ensure results entry exists
    results = load_results()
    if name not in results:
        results[name] = {}
        save_results(results)
    print(f"Added game {name}.")


def remove_game():
    data = load_data()
    games = data.get("games", [])
    if not games:
        print("No games to remove.")
        return
    print("Games:")
    for i, g in enumerate(games, 1):
        print(f"{i}. {g}")
    choice = input("Enter number of game to remove: ")
    try:
        idx = int(choice) - 1
        if idx < 0 or idx >= len(games):
            print("Invalid selection.")
            return
    except ValueError:
        print("Invalid input.")
        return
    name = games.pop(idx)
    save_data(data)
    results = load_results()
    if name in results:
        del results[name]
        save_results(results)
    import scoreboard
    hints = scoreboard.load_hints()
    if hints.pop(name, None) is not None:
        scoreboard.save_hints(hints)
    print(f"Removed game {name} and its results.")


def _choose(items, what, label=str):
    """Print a numbered list and return the chosen item, or None."""
    for i, item in enumerate(items, 1):
        print(f"{i}. {label(item)}")
    choice = input(f"Enter {what} number: ").strip()
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(items):
            return items[idx]
    except ValueError:
        pass
    print("Invalid selection.")
    return None


def _edit_results(results, hints, players, targets):
    """Prompt for each player's result in the target games, editing results/hints in place.

    Enter keeps the current value, 'h' after a result marks hints, and
    unreadable input is asked for again.
    """
    import scoreboard
    print("Enter keeps the current value. Add 'h' if hints were used, e.g. 1:05h")
    for game in targets:
        is_steps = scoreboard.is_steps_game(game)
        unit = "attempts" if is_steps else "m:ss"
        print(f"\n{game} ({unit}, '-' or 'DNF' for DNF):")
        results.setdefault(game, {})
        for player in players:
            cur = results[game].get(player, "")
            if cur and scoreboard.used_hints(hints, game, player):
                cur += "h"
            prompt = f"{player} ({cur})> " if cur else f"{player}> "
            while True:
                val = input(prompt).strip()
                if val == "":
                    break  # keep existing
                hint = val.lower().endswith("h")
                norm, err = scoreboard.normalize_result(val[:-1] if hint else val, is_steps)
                if err:
                    print(f"  {err}, try again (Enter keeps the current value).")
                    continue
                results[game][player] = norm
                hints.setdefault(game, {})[player] = hint
                break


def _choose_games(games):
    print("Games:")
    for i, g in enumerate(games, 1):
        print(f"{i}. {g}")
    choice = input("Enter game number (or 'all' for all games): ").strip()
    if choice.lower() == "all":
        return games
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(games):
            return [games[idx]]
    except ValueError:
        pass
    print("Invalid selection.")
    return None


def _snapshot_saved_today():
    import db
    from datetime import date
    return any(d == date.today() for d, _ in db.saved_days())


def _fmt(v):
    return int(v) if float(v).is_integer() else v


def _print_changes(before, after):
    changes = [f"{p} {_fmt(before.get(p, 0))} -> {_fmt(v)}" for p, v in after.items() if v != before.get(p, 0)]
    print("Points changed: " + ", ".join(changes) if changes else "No points changed.")


def register_results():
    import scoreboard
    data = load_data()
    players = data.get("players", [])
    games = data.get("games", [])
    if not players or not games:
        print("Need at least one player and one game to register results.")
        return
    targets = _choose_games(games)
    if not targets:
        return
    results = load_results()
    hints = scoreboard.load_hints()
    _edit_results(results, hints, players, targets)
    save_results(results)
    scoreboard.save_hints(hints)
    print(f"Saved results for {', '.join(targets)}.")
    if _snapshot_saved_today():
        import db
        db.save_day(data, results, hints)
        print("Today's snapshot was already saved, so it has been updated too.")
    else:
        print("Reminder: save today's snapshot (option 9) when everyone is done.")


def reset_results():
    confirm = input("Reset ALL results? Days already saved are kept. Type YES to confirm: ")
    if confirm == "YES":
        import scoreboard
        save_results({})
        scoreboard.save_hints({})
        print("All results and hints cleared.")
    else:
        print("Aborted.")


def show_scoreboard():
    # import scoreboard module to compute and print
    try:
        import scoreboard
        data = load_data()
        results = load_results()
        per_game, totals = scoreboard.compute_scores(data, results, scoreboard.load_hints())
        scoreboard.print_report(data, per_game, totals)
    except Exception as e:
        print("Failed to show scoreboard:", e)


def save_snapshot():
    import db
    import scoreboard
    data = load_data()
    key = db.save_day(data, load_results(), scoreboard.load_hints())
    print(f"Saved today's snapshot ({key}) to games.db and scores.json.")


def _choose_saved_day(what="day"):
    import db
    db.import_scores_json()
    days = db.saved_days()
    if not days:
        print("No saved days yet. Save today's snapshot first (option 9).")
        return None
    print("Saved days:")
    return _choose(days, what, lambda d: f"{d[0]:%a %d %b %Y}" + ("" if d[1] else "  (totals only)"))


def fix_saved_day():
    import db
    import scoreboard
    from datetime import date
    chosen = _choose_saved_day()
    if not chosen:
        return
    day, has_detail = chosen
    before = db.load_totals(day)

    if not has_detail:
        print(f"{day:%a %d %b} was imported from scores.json and only has totals. Enter keeps the current value.")
        totals = dict(before)
        for player, cur in before.items():
            while True:
                val = input(f"{player} ({_fmt(cur)})> ").strip()
                if val == "":
                    break
                try:
                    totals[player] = float(val)
                    break
                except ValueError:
                    print("  Not a number, try again.")
        db.save_totals(day, totals)
        print(f"Saved totals for {day:%a %d %b}.")
        _print_changes(before, db.load_totals(day))
        return

    d_data, d_results, d_hints = db.load_day(day, load_data())
    print(f"\nResults for {day:%a %d %b %Y}:")
    for game in d_data["games"]:
        cells = ", ".join(
            f"{p} {d_results.get(game, {}).get(p) or '-'}{' h' if scoreboard.used_hints(d_hints, game, p) else ''}"
            for p in d_data["players"]
        )
        print(f"  {game}: {cells}")
    print()
    targets = _choose_games(d_data["games"])
    if not targets:
        return
    _edit_results(d_results, d_hints, d_data["players"], targets)
    db.save_day(d_data, d_results, d_hints, day=day)
    if day == date.today():
        save_results(d_results)
        scoreboard.save_hints(d_hints)
    print(f"\nSaved {day:%a %d %b}. Points for everyone that day were recalculated.")
    _print_changes(before, db.load_totals(day))


def delete_saved_day():
    import db
    chosen = _choose_saved_day("day to delete")
    if not chosen:
        return
    day = chosen[0]
    confirm = input(f"Delete everything saved for {day:%a %d %b %Y}, including its weekly points? (y/N): ")
    if confirm.strip().lower() == "y":
        db.delete_day(day)
        print(f"Deleted {day:%a %d %b}.")
    else:
        print("Aborted.")


def weekly_stats():
    """Current week (Monday-Sunday) from games.db: points per day, total and hints used."""
    import db
    from datetime import date, timedelta
    db.import_scores_json()
    today = date.today()
    start = today - timedelta(days=today.weekday())
    end = start + timedelta(days=6)
    _, rows = db.query("SELECT day, player, points FROM daily_totals WHERE day BETWEEN ? AND ?",
                       (start.isoformat(), end.isoformat()))
    if not rows:
        print("Nothing saved this week yet. Save today's snapshot (option 9).")
        return
    _, hint_rows = db.query("SELECT player, COUNT(*) FROM results WHERE hints = 1 AND day BETWEEN ? AND ? GROUP BY player",
                            (start.isoformat(), end.isoformat()))
    hint_count = dict(hint_rows)
    days = sorted({d for d, _, _ in rows})
    per = {}
    for d, p, pts in rows:
        per.setdefault(p, {})[d] = pts
    totals = {p: sum(v.values()) for p, v in per.items()}
    ranked = sorted(totals, key=totals.get, reverse=True)

    print(f"\nWeek {start.isocalendar()[1]} ({start:%d %b} - {end:%d %b})")
    width = max(len(p) for p in ranked)
    labels = [date.fromisoformat(d).strftime("%a") for d in days]
    print(" " * (width + 4) + "".join(f"{l:>5}" for l in labels) + "  Total  Hints")
    top = max(totals.values()) or 1
    medals = ["🥇", "🥈", "🥉"]
    for i, p in enumerate(ranked):
        medal = medals[i] if i < 3 else "  "
        cells = "".join(f"{_fmt(per[p].get(d, 0)):>5}" for d in days)
        bar = "█" * round(20 * totals[p] / top)
        print(f"{medal} {p:<{width}} {cells}  {_fmt(totals[p]):>5}  {hint_count.get(p, 0):>5}  {bar}")
    if len(days) and date.fromisoformat(days[-1]) != today:
        print("\nToday is not saved yet, so it is not included above.")


def start_new_week():
    import scoreboard
    confirm = input("Start a new week from today? Weekly scores restart at 0 (today's results count). (y/N): ").strip().lower()
    if confirm == "y":
        day = scoreboard.start_new_week()
        print(f"New week started {day.isoformat()}.")
    else:
        print("Aborted.")


def _status_line():
    from datetime import date
    try:
        saved = _snapshot_saved_today()
    except Exception:
        saved = False
    state = "saved ✅" if saved else "NOT saved yet ⚠️  (option 9)"
    return f"Today {date.today():%a %d %b}: snapshot {state}"


def menu():
    actions = {
        "1": register_results,
        "2": add_player,
        "3": remove_player,
        "4": add_game,
        "5": remove_game,
        "6": show_scoreboard,
        "7": reset_results,
        "8": start_new_week,
        "9": save_snapshot,
        "10": fix_saved_day,
        "11": delete_saved_day,
        "12": weekly_stats,
    }
    while True:
        print("\nLinkedIn Game Manager")
        print(_status_line())
        print("Tips: add 'h' after a result for hints (e.g. 1:05h, costs 3 points). Typed something wrong? 10 fixes any saved day.")
        print("1. Register results")
        print("2. Add player")
        print("3. Remove player")
        print("4. Add game")
        print("5. Remove game")
        print("6. Show scoreboard")
        print("7. Reset results")
        print("8. Start new week")
        print("9. Save today's snapshot")
        print("10. Fix a saved day")
        print("11. Delete a saved day")
        print("12. Weekly stats")
        print("0. Exit")
        choice = input("Choose: ").strip().lower()
        if choice in ("0", "q", "exit"):
            print("Goodbye")
            sys.exit(0)
        elif choice in actions:
            actions[choice]()
        else:
            print("Invalid choice")


if __name__ == "__main__":
    menu()
