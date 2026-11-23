import json
import os
from datetime import date
from pathlib import Path

# app.py and scoreboard.py use paths relative to the working directory
os.chdir(Path(__file__).parent)

import altair as alt
import pandas as pd
import streamlit as st

import db
import scoreboard
from app import load_data, save_data, load_results, save_results

EMOJIS = ["🥇", "🥈", "🥉"]

st.set_page_config(page_title="LinkedIn Games", page_icon="🧩", layout="wide")
st.title("🧩 LinkedIn Games Scoreboard")

data = load_data()
results = load_results()
hints = scoreboard.load_hints()
players = data.get("players", [])
games = data.get("games", [])


def fmt(v):
    return int(v) if float(v).is_integer() else v


is_dnf = scoreboard.is_dnf_value


def results_grid(results, hints, players, games, key):
    """Results grid plus a matching hints checkbox grid. Returns both edited frames."""
    grid = pd.DataFrame(
        {g: [str(results.get(g, {}).get(p, "") or "") for p in players] for g in games},
        index=players,
    )
    edited = st.data_editor(grid, width="stretch", key=f"{key}_results")
    st.markdown("**💡 Hints used**")
    hint_grid = pd.DataFrame(
        {g: [scoreboard.used_hints(hints, g, p) for p in players] for g in games},
        index=players,
    )
    edited_hints = st.data_editor(hint_grid, width="stretch", key=f"{key}_hints")
    return edited, edited_hints


def read_grid(edited, edited_hints, players, games):
    """Edited grids -> (results, hints, errors) with every result tidied up."""
    new_results, errors = {}, []
    for g in games:
        new_results[g] = {}
        for p in players:
            norm, err = scoreboard.normalize_result(edited.at[p, g], scoreboard.is_steps_game(g))
            if err:
                errors.append(f"**{g} / {p}**: {err}")
            new_results[g][p] = norm
    new_hints = {g: {p: bool(edited_hints.at[p, g]) for p in players} for g in games}
    return new_results, new_hints, errors


def show_errors(errors):
    st.error("Nothing saved. Fix these first:\n\n" + "\n\n".join(errors))


def save_current(new_results, new_hints):
    """Save today's results. If today's snapshot is already saved, refresh it too."""
    save_results(new_results)
    scoreboard.save_hints(new_hints)
    clear_quick_entry()
    if any(d == date.today() for d, _ in db.saved_days()):
        db.save_day(data, new_results, new_hints)
        return "Results saved and today's snapshot updated"
    return "Results saved"


def flash(msg):
    """Show msg as a toast after the next rerun."""
    st.session_state["flash"] = msg


if "flash" in st.session_state:
    st.toast(st.session_state.pop("flash"))


def clear_quick_entry():
    """Drop quick-entry widget state so it reloads from the saved files."""
    for k in [k for k in st.session_state if str(k).startswith("q_") and k != "q_player"]:
        del st.session_state[k]


tab_board, tab_stats, tab_register, tab_manage, tab_history = st.tabs(
    ["🏆 Scoreboard", "📊 Weekly stats", "✏️ Register results", "👥 Players & games", "📈 History"]
)

with tab_board:
    if not players or not games:
        st.info("Add at least one player and one game to get started.")
    else:
        per_game, totals = scoreboard.compute_scores(data, results, hints)
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
                result = "DNF" if is_dnf(raw) else (f"{raw} 💡" if info["hints"][p] else raw)
                rows.append({"": medal, "Player": p, "Result": result, "Pts": fmt(info["points"][p])})
            with game_cols[gi % 4]:
                st.markdown(f"**{game}**")
                st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        st.caption(f"💡 = hints used (−{fmt(scoreboard.HINT_PENALTY)} points)")

        st.divider()
        if st.button("💾 Save today's snapshot", help="Stores today's results in games.db and totals in scores.json, and updates scores_summary.json"):
            key = db.save_day(data, results, hints)
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

# Categorical slots, assigned to players in data.json order so a player keeps
# their color whichever filters are applied.
PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
SEQUENTIAL = ["#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#104281"]


def player_color(domain):
    scale = alt.Scale(domain=domain, range=PALETTE[: len(domain)]) if len(domain) <= len(PALETTE) else alt.Scale(domain=domain)
    return alt.Color("player:N", title="Player", scale=scale, legend=alt.Legend(orient="top"))


with tab_stats:
    db.import_scores_json()
    cols, rows = db.query("SELECT day, player, points FROM daily_totals")
    daily = pd.DataFrame(rows, columns=cols)
    if daily.empty:
        st.info("No days saved yet. Press 💾 Save today's snapshot on the Scoreboard tab.")
    else:
        daily["date"] = pd.to_datetime(daily["day"])
        daily["week"] = (daily["date"] - pd.to_timedelta(daily["date"].dt.day_of_week, unit="D")).dt.date
        weeks = sorted(daily["week"].unique(), reverse=True)
        all_players = players + sorted(set(daily["player"]) - set(players))

        def week_label(w):
            end = w + pd.Timedelta(days=6)
            return f"Week {w.isocalendar()[1]} · {w:%d %b} – {end:%d %b %Y}"

        f1, f2 = st.columns([1, 2])
        week = f1.selectbox("Week", weeks, format_func=week_label, key="stats_week")
        shown = f2.multiselect("Players", all_players, default=all_players, key="stats_players")

        wk = daily[(daily["week"] == week) & daily["player"].isin(shown)].sort_values("date")
        start, end = week.isoformat(), (week + pd.Timedelta(days=6)).isoformat()
        cols, rows = db.query("SELECT * FROM results WHERE day BETWEEN ? AND ?", (start, end))
        detail = pd.DataFrame(rows, columns=cols)
        detail = detail[detail["player"].isin(shown)]

        if wk.empty:
            st.info("Nothing saved for these players this week.")
        else:
            wk["label"] = wk["date"].dt.strftime("%a %d")
            wk["cumulative"] = wk.groupby("player")["points"].cumsum()
            week_totals = wk.groupby("player")["points"].sum().sort_values(ascending=False)

            m = st.columns(4)
            m[0].metric("🏆 Leading", week_totals.index[0], f"{fmt(week_totals.iloc[0])} pts", delta_color="off")
            m[1].metric("Days saved", wk["day"].nunique())
            best = wk.loc[wk["points"].idxmax()]
            m[2].metric("Best day", f"{fmt(best['points'])} pts", f"{best['player']}, {best['label']}", delta_color="off")
            m[3].metric("💡 Results with hints", int(detail["hints"].sum()) if not detail.empty else 0)

            color = player_color([p for p in all_players if p in shown])
            day_order = list(dict.fromkeys(wk["label"]))
            hover = alt.selection_point(fields=["label"], nearest=True, on="pointerover", empty=False)

            st.subheader("Points through the week")
            base = alt.Chart(wk).encode(
                x=alt.X("label:O", title=None, sort=day_order, axis=alt.Axis(labelAngle=0)),
                y=alt.Y("cumulative:Q", title="Points so far"),
                color=color,
            )
            tooltip = [alt.Tooltip("player:N", title="Player"), alt.Tooltip("label:O", title="Day"),
                       alt.Tooltip("points:Q", title="Points that day"), alt.Tooltip("cumulative:Q", title="Week so far")]
            lines = base.mark_line(strokeWidth=2, interpolate="monotone")
            points = base.mark_point(filled=True, size=70, stroke="white", strokeWidth=2, opacity=1).encode(tooltip=tooltip)
            rule = alt.Chart(wk).mark_rule(color="gray", opacity=0.4).encode(
                x=alt.X("label:O", sort=day_order)).transform_filter(hover)
            catcher = alt.Chart(wk).mark_rule(opacity=0, strokeWidth=30).encode(
                x=alt.X("label:O", sort=day_order)).add_params(hover)
            ends = base.transform_filter(
                alt.datum.label == day_order[-1]
            ).mark_text(align="left", dx=8, fontSize=12).encode(text="player:N", color=alt.value("gray"))
            chart = alt.layer(lines, rule, points, catcher)
            if len(shown) <= 4:
                chart = alt.layer(chart, ends)
            st.altair_chart(chart.properties(height=340), width="stretch")

            if detail.empty:
                st.caption("Per-game charts appear for days saved with 💾 Save today's snapshot from now on. "
                           "Older days only have daily totals.")
            else:
                left, right = st.columns(2)
                with left:
                    st.subheader("Points per game")
                    per_game = detail.groupby(["player", "game"], as_index=False).agg(
                        points=("points", "sum"), hints=("hints", "sum"), days=("day", "nunique"))
                    game_order = [g for g in games if g in set(per_game["game"])] + sorted(set(per_game["game"]) - set(games))
                    heat = alt.Chart(per_game).mark_rect(cornerRadius=4, stroke="white", strokeWidth=2).encode(
                        x=alt.X("game:N", title=None, sort=game_order, axis=alt.Axis(labelAngle=-30)),
                        y=alt.Y("player:N", title=None, sort=[p for p in all_players if p in shown]),
                        color=alt.Color("points:Q", title="Points", scale=alt.Scale(range=SEQUENTIAL)),
                        tooltip=[alt.Tooltip("player:N", title="Player"), alt.Tooltip("game:N", title="Game"),
                                 alt.Tooltip("points:Q", title="Points"), alt.Tooltip("days:Q", title="Days played"),
                                 alt.Tooltip("hints:Q", title="Times with hints")],
                    )
                    st.altair_chart(heat.properties(height=320), width="stretch")

                with right:
                    st.subheader("Results per day")
                    game = st.selectbox("Game", game_order, key="stats_game", label_visibility="collapsed")
                    g = detail[(detail["game"] == game) & detail["value"].notna()].copy()
                    if g.empty:
                        st.info(f"No finished {game} results this week.")
                    else:
                        g["date"] = pd.to_datetime(g["day"])
                        g["label"] = g["date"].dt.strftime("%a %d")
                        g["hint_label"] = g["hints"].map({1: "Used hints", 0: "No hints"})
                        steps = bool(g["is_steps"].iloc[0])
                        g["shown"] = g["raw"] if not steps else g["value"].astype(int).astype(str)
                        g_days = sorted(set(g["label"]), key=lambda l: g.loc[g["label"] == l, "date"].iloc[0])
                        by_day = alt.Chart(g).encode(
                            x=alt.X("label:O", title=None, sort=g_days, axis=alt.Axis(labelAngle=0)),
                            y=alt.Y("value:Q", title="Attempts" if steps else "Time",
                                    scale=alt.Scale(zero=steps),
                                    axis=alt.Axis(tickMinStep=1) if steps else alt.Axis(
                                        labelExpr="floor(datum.value / 60) + ':' + (datum.value % 60 < 10 ? '0' : '') + datum.value % 60")),
                            color=color,
                        )
                        res_chart = alt.layer(
                            by_day.mark_line(strokeWidth=2),
                            by_day.mark_point(size=80, filled=True, stroke="white", strokeWidth=2, opacity=1).encode(
                                shape=alt.Shape("hint_label:N", title=None,
                                                scale=alt.Scale(domain=["No hints", "Used hints"], range=["circle", "diamond"])),
                                tooltip=[alt.Tooltip("player:N", title="Player"), alt.Tooltip("label:O", title="Day"),
                                         alt.Tooltip("shown:N", title="Result"), alt.Tooltip("hint_label:N", title="Hints"),
                                         alt.Tooltip("points:Q", title="Points")],
                            ),
                        )
                        st.altair_chart(res_chart.properties(height=280), width="stretch")
                        st.caption("Lower is better. ◆ = hints used.")

            with st.expander("Table view"):
                table = wk.pivot_table(index="player", columns="label", values="points", aggfunc="sum")[day_order]
                table["Week"] = table.sum(axis=1)
                st.dataframe(table.sort_values("Week", ascending=False).fillna(0), width="stretch")

with tab_register:
    if not players or not games:
        st.info("Add at least one player and one game first.")
    else:
        st.caption(
            "Times as `m:ss` (`65`, `1.05` and `1,05` also work), Pinpoint as number of attempts. "
            f"Leave empty or use `-`/`DNF` for did not finish. Turn on 💡 if hints were used "
            f"(−{fmt(scoreboard.HINT_PENALTY)} points)."
        )
        quick_tab, grid_tab, fix_tab = st.tabs(["⚡ Quick entry", "📋 All results", "🛠️ Fix a saved day"])

        with quick_tab:
            player = st.selectbox("Player", players, key="q_player")
            with st.form(f"q_form_{player}"):
                entries = {}
                for game in games:
                    is_steps = scoreboard.is_steps_game(game)
                    cur = str(results.get(game, {}).get(player, "") or "")
                    c1, c2 = st.columns([4, 1], vertical_alignment="bottom")
                    if is_steps:
                        cur_n, _ = scoreboard.normalize_result(cur, is_steps=True)
                        val = c1.number_input(
                            f"{game} – attempts",
                            min_value=1,
                            step=1,
                            value=int(cur_n) if cur_n and cur_n.isdigit() else None,
                            placeholder="attempts",
                            key=f"q_{player}_{game}",
                        )
                    else:
                        val = c1.text_input(
                            f"{game} – time",
                            value=cur,
                            placeholder="m:ss",
                            key=f"q_{player}_{game}",
                        )
                    hint = c2.toggle(
                        "💡 Hints",
                        value=scoreboard.used_hints(hints, game, player),
                        key=f"q_{player}_{game}_hint",
                    )
                    entries[game] = (val, hint)

                if st.form_submit_button(f"Save {player}'s results", type="primary"):
                    errors = []
                    for game, (val, hint) in entries.items():
                        norm, err = scoreboard.normalize_result(val, scoreboard.is_steps_game(game))
                        if err:
                            errors.append(f"**{game}**: {err}")
                            continue
                        results.setdefault(game, {})[player] = norm
                        hints.setdefault(game, {})[player] = hint
                    if errors:
                        show_errors(errors)
                    else:
                        flash(save_current(results, hints).replace("Results", f"{player}'s results"))
                        st.rerun()

        with grid_tab:
            edited, edited_hints = results_grid(results, hints, players, games, key="today")
            c1, c2 = st.columns([1, 5])
            if c1.button("Save results", type="primary"):
                new_results, new_hints, errors = read_grid(edited, edited_hints, players, games)
                if errors:
                    show_errors(errors)
                else:
                    flash(save_current(new_results, new_hints))
                    st.rerun()
            with c2.popover("🗑️ Reset all results"):
                st.warning("This clears every result and hint. Days already saved are kept.")
                if st.button("Yes, reset"):
                    save_results({})
                    scoreboard.save_hints({})
                    clear_quick_entry()
                    st.rerun()

        with fix_tab:
            db.import_scores_json()
            days = dict(db.saved_days())
            if not days:
                st.info("No saved days yet. Days appear here after 💾 Save today's snapshot.")
            else:
                day = st.selectbox(
                    "Day",
                    list(days),
                    format_func=lambda d: f"{d:%A %d %b %Y}" + ("" if days[d] else "  ·  totals only"),
                    key="fix_day",
                )
                if days[day]:
                    st.caption("Correct any result or hint and press Save. Points for everyone that day "
                               "are recalculated, since one changed time can move others up or down.")
                    d_data, d_results, d_hints = db.load_day(day, data)
                    before = db.load_totals(day)
                    edited, edited_hints = results_grid(d_results, d_hints, d_data["players"], d_data["games"],
                                                        key=f"fix_{day}")
                    save_clicked = st.button(f"Save {day:%d %b}", type="primary", key="fix_save")
                    if save_clicked:
                        new_results, new_hints, errors = read_grid(edited, edited_hints, d_data["players"], d_data["games"])
                        if errors:
                            show_errors(errors)
                        else:
                            db.save_day(d_data, new_results, new_hints, day=day)
                            if day == date.today():
                                save_results(new_results)
                                scoreboard.save_hints(new_hints)
                                clear_quick_entry()
                            after = db.load_totals(day)
                            changes = [f"{p} {fmt(before.get(p, 0))} → {fmt(v)}" for p, v in after.items()
                                       if v != before.get(p, 0)]
                            flash(f"Saved {day:%d %b}. " + (", ".join(changes) if changes else "No points changed."))
                            st.rerun()
                else:
                    st.caption("This day was imported from scores.json and only has each player's total. "
                               "Correct the totals and press Save.")
                    totals_df = pd.DataFrame({"Points": pd.Series(db.load_totals(day), dtype=float)})
                    edited_totals = st.data_editor(
                        totals_df, key=f"fix_totals_{day}",
                        column_config={"Points": st.column_config.NumberColumn(min_value=0, step=1)},
                    )
                    if st.button(f"Save {day:%d %b}", type="primary", key="fix_save"):
                        db.save_totals(day, edited_totals["Points"].fillna(0).to_dict())
                        flash(f"Saved totals for {day:%d %b}")
                        st.rerun()

                with st.popover(f"🗑️ Delete {day:%d %b}"):
                    st.warning(f"Removes everything saved for {day:%A %d %b %Y}, including its points in the Weekly score.")
                    if st.button("Yes, delete this day", key="fix_delete"):
                        db.delete_day(day)
                        flash(f"Deleted {day:%d %b}")
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
                        for store in (results, hints):
                            for g in store.values():
                                g.pop(name, None)
                    else:
                        results.pop(name, None)
                        hints.pop(name, None)
                    save_results(results)
                    scoreboard.save_hints(hints)
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
