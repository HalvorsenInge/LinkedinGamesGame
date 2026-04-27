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
    print(f"Removed game {name} and its results.")


def register_results():
    data = load_data()
    players = data.get("players", [])
    games = data.get("games", [])
    if not players or not games:
        print("Need at least one player and one game to register results.")
        return
    print("Games:")
    for i, g in enumerate(games, 1):
        print(f"{i}. {g}")
    choice = input("Enter game number to register (or 'all' for all games): ").strip()
    if choice.lower() == "all":
        targets = games
    else:
        try:
            idx = int(choice) - 1
            targets = [games[idx]]
        except Exception:
            print("Invalid selection.")
            return
    results = load_results()
    for game in targets:
        print(f"Registering results for {game} (enter '-' or 'DNF' for DNF):")
        if game not in results:
            results[game] = {}
        for player in players:
            cur = results[game].get(player, "")
            prompt = f"{player} ({cur})> " if cur else f"{player}> "
            val = input(prompt).strip()
            if val == "":
                # keep existing
                continue
            results[game][player] = val
        save_results(results)
        print(f"Saved results for {game}.")


def reset_results():
    confirm = input("Reset ALL results? Type YES to confirm: ")
    if confirm == "YES":
        save_results({})
        print("All results cleared.")
    else:
        print("Aborted.")


def show_scoreboard():
    # import scoreboard module to compute and print
    try:
        import scoreboard
        data = load_data()
        results = load_results()
        per_game, totals = scoreboard.compute_scores(data, results)
        scoreboard.print_report(data, per_game, totals)
    except Exception as e:
        print("Failed to show scoreboard:", e)


def menu():
    while True:
        print("\nLinkedIn Game Manager")
        print("1. Register results")
        print("2. Add player")
        print("3. Remove player")
        print("4. Add game")
        print("5. Remove game")
        print("6. Show scoreboard")
        print("7. Reset results")
        print("8. Exit")
        choice = input("Choose: ").strip()
        if choice == "1":
            register_results()
        elif choice == "2":
            add_player()
        elif choice == "3":
            remove_player()
        elif choice == "4":
            add_game()
        elif choice == "5":
            remove_game()
        elif choice == "6":
            show_scoreboard()
        elif choice == "7":
            reset_results()
        elif choice == "8":
            print("Goodbye")
            sys.exit(0)
        else:
            print("Invalid choice")


if __name__ == "__main__":
    menu()
