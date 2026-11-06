import json
import os
from pathlib import Path

# app.py and scoreboard.py use paths relative to the working directory
os.chdir(Path(__file__).parent)

import pandas as pd
import streamlit as st

import scoreboard
from app import load_data, save_data, load_results, save_results

EMOJIS = ["🥇", "🥈", "🥉"]

st.set_page_config(page_title="LinkedIn Games", page_icon="🧩", layout="wide")
st.title("🧩 LinkedIn Games Scoreboard")

data = load_data()
results = load_results()
players = data.get("players", [])
games = data.get("games", [])


def fmt(v):
    return int(v) if float(v).is_integer() else v


def is_dnf(raw):
    return raw is None or str(raw).strip().lower() in ("", "-", "-1", "dnf")


tab_board, tab_register, tab_manage, tab_history = st.tabs(
    ["🏆 Scoreboard", "✏️ Register results", "👥 Players & games", "📈 History"]
)

with tab_board:
    if not players or not games:
        st.info("Add at least one player and one game to get started.")
    else:
        per_game, totals = scoreboard.compute_scores(data, results)
        ranked = sorted(totals.items(), key=lambda x: x[1], reverse=True)

        top = ranked[0][1] if ranked else 0
        winners = [p for p, s in ranked if s == top]
        if top > 0:
            st.success(("Winner: " if len(winners) == 1 else "Winners (tie): ") + ", ".join(winners))

        cols = st.columns(min(3, len(ranked)))
        for i, (p, v) in enumerate(ranked[:3]):
            cols[i].metric(f"{EMOJIS[i]} {p}", fmt(v))

        st.subheader("Totals")
        st.bar_chart(pd.DataFrame({"Points": [v for _, v in ranked]}, index=[p for p, _ in ranked]), horizontal=True)

        st.subheader("Per game")
        game_cols = st.columns(4)
        for gi, game in enumerate(games):
            info = per_game[game]
            rows = []
            for p in sorted(players, key=lambda p: info["points"][p], reverse=True):
                rank = info["ranks"][p]
                raw = info["raw"][p]
                medal = EMOJIS[rank - 1] if rank and rank <= 3 else (str(rank) if rank else "")
                rows.append({"": medal, "Player": p, "Result": "DNF" if is_dnf(raw) else raw, "Pts": fmt(info["points"][p])})
            with game_cols[gi % 4]:
                st.markdown(f"**{game}**")
                st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

        st.divider()
        if st.button("💾 Save today's snapshot", help="Stores totals in scores.json under today's date and updates scores_summary.json"):
            key = scoreboard.save_scores_snapshot(totals)
            scoreboard.summarize_scores()
            st.toast(f"Saved snapshot '{key}'")

        weekly = scoreboard.compute_weekly(data, totals)
        manual_start = scoreboard.get_manual_week_start()
        st.subheader("Weekly")
        if manual_start:
            st.caption(f"Week started manually on {manual_start.isoformat()}")
        weekly_ranked = sorted(weekly.items(), key=lambda x: x[1], reverse=True)
        st.bar_chart(pd.DataFrame({"Points": [v for _, v in weekly_ranked]}, index=[p for p, _ in weekly_ranked]), horizontal=True)
        with st.popover("🔄 Start new week"):
            st.warning("Weekly scores restart from today. Today's results count towards the new week.")
            if st.button("Yes, start new week"):
                scoreboard.start_new_week()
                st.rerun()

with tab_register:
    if not players or not games:
        st.info("Add at least one player and one game first.")
    else:
        st.caption("Times as `m:ss`, Pinpoint as number of guesses. Use `-` or `DNF` for did not finish.")
        grid = pd.DataFrame(
            {g: [str(results.get(g, {}).get(p, "") or "") for p in players] for g in games},
            index=players,
        )
        edited = st.data_editor(grid, width="stretch", key="results_editor")
        c1, c2 = st.columns([1, 5])
        if c1.button("Save results", type="primary"):
            new_results = {g: {p: str(edited.at[p, g]).strip() for p in players} for g in games}
            save_results(new_results)
            st.toast("Results saved")
            st.rerun()
        with c2.popover("🗑️ Reset all results"):
            st.warning("This clears every result.")
            if st.button("Yes, reset"):
                save_results({})
                st.rerun()

with tab_manage:
    left, right = st.columns(2)
    for col, kind, items in ((left, "player", players), (right, "game", games)):
        with col:
            st.subheader(f"{kind.title()}s")
            with st.form(f"add_{kind}", clear_on_submit=True):
                name = st.text_input(f"New {kind}").strip()
                if st.form_submit_button(f"Add {kind}") and name:
                    if name in items:
                        st.error(f"{name} already exists.")
                    else:
                        items.append(name)
                        save_data(data)
                        if kind == "game":
                            results.setdefault(name, {})
                            save_results(results)
                        st.rerun()
            for name in list(items):
                a, b = st.columns([4, 1])
                a.write(name)
                if b.button("Remove", key=f"rm_{kind}_{name}"):
                    items.remove(name)
                    save_data(data)
                    if kind == "player":
                        for g in results.values():
                            g.pop(name, None)
                    else:
                        results.pop(name, None)
                    save_results(results)
                    st.rerun()

with tab_history:
    scores = scoreboard.load_scores()
    if not scores:
        st.info("No snapshots yet. Save one from the Scoreboard tab.")
    else:
        st.subheader("Snapshots")
        st.dataframe(pd.DataFrame(scores).fillna(0), width="stretch")
        summary = json.loads(scoreboard.SUMMARY_PATH.read_text()) if scoreboard.SUMMARY_PATH.exists() else {}
        if summary:
            st.subheader("Summary")
            st.dataframe(
                pd.DataFrame(summary).T.sort_values("total", ascending=False),
                width="stretch",
            )
