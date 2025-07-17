import os
import flask
import random
from bfkt import app  
from bfkt.models import get_db
from flask import render_template

@app.route("/h2h_open")
def h2h_open():
    con = get_db()
    clubs = con.execute("SELECT name FROM participants ORDER BY name ASC").fetchall()
    return render_template("h2h.html", clubs=[row["name"] for row in clubs], picked=False)

@app.route("/h2h_generator", methods=["POST"])
def h2h_generator():
    con = get_db()
    team1 = flask.request.form.get("club1")
    team2 = flask.request.form.get("club2")

    if not team1 or not team2 or team1 == team2:
        return "Invalid selection", 400

    matches = con.execute("""
        SELECT * FROM matches
        WHERE (home = ? AND away = ?) OR (home = ? AND away = ?)
        ORDER BY match_id
    """, (team1, team2, team2, team1)).fetchall()

    filename_map = {
        row["name"]: row["filename"]
        for row in con.execute("SELECT name, filename FROM participants").fetchall()
    }

    results_vector = []
    t1_wins, t2_wins, draws = 0, 0, 0
    t1_goals, t2_goals = 0, 0
    t1_biggest_win = {"margin": -1}
    t2_biggest_win = {"margin": -1}

    for match in matches:
        h, a, hg, ag = match["home"], match["away"], match["home_goals"], match["away_goals"]
        gw = (match["match_id"] // 10) + 1
        results_vector.append({
            "home": h,
            "home_goals": hg,
            "away_goals": ag,
            "away": a,
            "gw": gw
        })

        if hg > ag:
            winner = h
        elif ag > hg:
            winner = a
        else:
            winner = "draw"
            draws += 1

        if winner == team1:
            t1_wins += 1
        elif winner == team2:
            t2_wins += 1

        if h == team1:
            t1_goals += hg
            t2_goals += ag
        elif a == team1:
            t1_goals += ag
            t2_goals += hg

        margin = abs(hg - ag)
        if hg != ag:
            if winner == team1 and margin > t1_biggest_win["margin"]:
                t1_biggest_win = {
                    "score": f"{hg}-{ag}" if h == team1 else f"{ag}-{hg}",
                    "gw": gw,
                    "home": h,
                    "away": a,
                    "margin": margin
                }
            elif winner == team2 and margin > t2_biggest_win["margin"]:
                t2_biggest_win = {
                    "score": f"{hg}-{ag}" if h == team2 else f"{ag}-{hg}",
                    "gw": gw,
                    "home": h,
                    "away": a,
                    "margin": margin
                }

    standings = {
        row["name"]: {
            "points": row["points"],
            "position": idx + 1
        } for idx, row in enumerate(con.execute("""
            SELECT name, points FROM standings
            ORDER BY points DESC, goal_difference DESC, goals_for DESC, name ASC
        """).fetchall())
    }

    price_row = con.execute("SELECT initial_rating FROM participants WHERE name = ?", (team1,)).fetchone()
    team1_price = round(price_row["initial_rating"] * 100, 2) if price_row else 0
    price_row = con.execute("SELECT initial_rating FROM participants WHERE name = ?", (team2,)).fetchone()
    team2_price = round(price_row["initial_rating"] * 100, 2) if price_row else 0

    def get_rating_stats(club):
        history = con.execute("""
            SELECT gameweek, rating FROM ratings_history
            WHERE club_name = ?
            ORDER BY gameweek
        """, (club,)).fetchall()

        high_val = max(history, key=lambda r: r["rating"], default={"rating": 0, "gameweek": 0})
        biggest_jump = {"jump": 0, "gameweek": 0}
        for i in range(1, len(history)):
            jump = (history[i]["rating"] - history[i - 1]["rating"]) / history[i - 1]["rating"] * 100
            if jump > biggest_jump["jump"]:
                biggest_jump = {
                    "jump": round(jump, 2),
                    "gameweek": history[i]["gameweek"]
                }
        return {
            "alltime_high": round(high_val["rating"] * 100, 2),
            "alltime_high_gw": high_val["gameweek"],
            "biggest_jump": biggest_jump
        }

    t1_stats = get_rating_stats(team1)
    t2_stats = get_rating_stats(team2)
    picked = True
    context = {
        "picked": picked,
        "team1": team1,
        "team2": team2,
        "team1_filename": filename_map[team1],
        "team2_filename": filename_map[team2],
        "results_vector": results_vector,
        "meetings": len(matches),
        "t1_wins": t1_wins,
        "t2_wins": t2_wins,
        "draws": draws,
        "t1_goals": t1_goals,
        "t2_goals": t2_goals,
        "t1_biggest_win": t1_biggest_win if t1_biggest_win["margin"] != -1 else None,
        "t2_biggest_win": t2_biggest_win if t2_biggest_win["margin"] != -1 else None,
        "t1_points": standings.get(team1, {}).get("points", 0),
        "t2_points": standings.get(team2, {}).get("points", 0),
        "t1_position": standings.get(team1, {}).get("position", "-"),
        "t2_position": standings.get(team2, {}).get("position", "-"),
        "t1_price": team1_price,
        "t2_price": team2_price,
        "t1_high": t1_stats["alltime_high"],
        "t2_high": t2_stats["alltime_high"],
        "t1_high_gw": t1_stats["alltime_high_gw"],
        "t2_high_gw": t2_stats["alltime_high_gw"],
        "t1_jump": t1_stats["biggest_jump"]["jump"],
        "t1_jump_gw": t1_stats["biggest_jump"]["gameweek"],
        "t2_jump": t2_stats["biggest_jump"]["jump"],
        "t2_jump_gw": t2_stats["biggest_jump"]["gameweek"]
    }

    return render_template("h2h.html", **context)
