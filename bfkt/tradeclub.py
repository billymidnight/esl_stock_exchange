import os
import flask
import random
import numpy as np
import random
import math
import matplotlib.pyplot as plt
from bfkt import app  
from bfkt.models import get_db

import math

def pull_financials(club_name):
    con = get_db()

    high_row = con.execute("SELECT MAX(rating) AS max FROM ratings_history WHERE club_name = ?", (club_name,)).fetchone()
    low_row = con.execute("SELECT MIN(rating) AS min FROM ratings_history WHERE club_name = ?", (club_name,)).fetchone()

    alltime_high = round(high_row["max"] * 100, 2) if high_row and high_row["max"] else 0
    alltime_low = round(low_row["min"] * 100, 2) if low_row and low_row["min"] else 0

    matches = con.execute("""
        SELECT * FROM matches
        WHERE home = ? OR away = ?
        ORDER BY match_id ASC
    """, (club_name, club_name)).fetchall()

    largest_win = {"margin": -1}
    largest_loss = {"margin": -1}
    wins_against = {}
    losses_against = {}
    win_streak = {"length": 0}
    loss_streak = {"length": 0}

    current_win_streak = 0
    win_start = None
    current_loss_streak = 0
    loss_start = None

    for match in matches:
        is_home = match["home"] == club_name
        opponent = match["away"] if is_home else match["home"]
        gf = match["home_goals"] if is_home else match["away_goals"]
        ga = match["away_goals"] if is_home else match["home_goals"]
        margin = abs(gf - ga)
        match_id = match["match_id"]
        gw = math.ceil(match_id / 10)

        if gf > ga:
            if margin > largest_win["margin"] or (margin == largest_win["margin"] and gw > largest_win.get("gameweek", -1)):
                largest_win = {
                    "opponent": opponent,
                    "gf": gf,
                    "ga": ga,
                    "margin": margin,
                    "match_id": match_id,
                    "gameweek": gw
                }
            wins_against[opponent] = wins_against.get(opponent, 0) + 1

            if current_win_streak == 0:
                win_start = gw
            current_win_streak += 1
            if current_win_streak >= win_streak.get("length", 0):
                win_streak = {"length": current_win_streak, "gw_start": win_start, "gw_end": gw}
            current_loss_streak = 0

        elif gf < ga:
            if margin > largest_loss["margin"] or (margin == largest_loss["margin"] and gw > largest_loss.get("gameweek", -1)):
                largest_loss = {
                    "opponent": opponent,
                    "gf": gf,
                    "ga": ga,
                    "margin": margin,
                    "match_id": match_id,
                    "gameweek": gw
                }
            losses_against[opponent] = losses_against.get(opponent, 0) + 1

            if current_loss_streak == 0:
                loss_start = gw
            current_loss_streak += 1
            if current_loss_streak >= loss_streak.get("length", 0):
                loss_streak = {"length": current_loss_streak, "gw_start": loss_start, "gw_end": gw}
            current_win_streak = 0

        else:
            current_win_streak = 0
            current_loss_streak = 0

    max_wins = max(wins_against.values(), default=0)
    most_wins_against = [{"club": club, "count": wins_against[club]} for club in wins_against if wins_against[club] == max_wins]

    max_losses = max(losses_against.values(), default=0)
    most_losses_against = [{"club": club, "count": losses_against[club]} for club in losses_against if losses_against[club] == max_losses]

    ratings = con.execute("""
        SELECT gameweek, rating FROM ratings_history
        WHERE club_name = ?
        ORDER BY gameweek
    """, (club_name,)).fetchall()

    biggest_jump = {"jump": 0, "gameweek": 0}
    biggest_fall = {"fall": 0, "gameweek": 0}
    for i in range(1, len(ratings)):
        prev = ratings[i - 1]["rating"]
        curr = ratings[i]["rating"]
        pct_change = ((curr - prev) / prev) * 100 if prev else 0
        if pct_change > biggest_jump["jump"]:
            biggest_jump = {"jump": round(pct_change, 2), "gameweek": ratings[i]["gameweek"]}
        if pct_change < biggest_fall["fall"]:
            biggest_fall = {"fall": round(pct_change, 2), "gameweek": ratings[i]["gameweek"]}

    return {
        "alltime_high": alltime_high,
        "alltime_low": alltime_low,
        "largest_win": largest_win if largest_win["margin"] != -1 else None,
        "largest_loss": largest_loss if largest_loss["margin"] != -1 else None,
        "most_wins_against": most_wins_against,
        "most_losses_against": most_losses_against,
        "longest_win_streak": win_streak if win_streak.get("length", 0) > 0 else None,
        "longest_loss_streak": loss_streak if loss_streak.get("length", 0) > 0 else None,
        "biggest_jump": biggest_jump,
        "biggest_fall": biggest_fall
    }


@app.route('/oneclub/', methods=['GET'])
def oneclub():
    con = get_db()
    club_name = flask.request.args.get("clubname")

    club_data = con.execute("""
        SELECT p.filename, p.initial_rating, s.goals_for, s.goals_against, s.goal_difference, s.points
        FROM participants p
        JOIN standings s ON p.name = s.name
        WHERE p.name = ?
    """, (club_name,)).fetchone()

    if not club_data:
        return "Club not found", 404

    filename = club_data["filename"]
    stock_price = round(club_data["initial_rating"] * 100, 2)
    goals_for = club_data["goals_for"]
    goals_against = club_data["goals_against"]
    goal_diff = club_data["goal_difference"]
    points = club_data["points"]

    record = con.execute("""
        SELECT wins, draws, losses FROM standings WHERE name = ?
    """, (club_name,)).fetchone()
    wins = record["wins"]
    draws = record["draws"]
    losses = record["losses"]

    full_table = con.execute("""
        SELECT name FROM standings
        ORDER BY points DESC, goal_difference DESC, goals_for DESC, name ASC
    """).fetchall()
    position = [i for i, row in enumerate(full_table, 1) if row["name"] == club_name][0]

    matches = con.execute("""
        SELECT * FROM matches
        WHERE home = ? OR away = ?
        ORDER BY match_id DESC
        LIMIT 5
    """, (club_name, club_name)).fetchall()

    last_results = []
    for match in matches:
        is_home = match["home"] == club_name
        opponent = match["away"] if is_home else match["home"]
        goals_for_ = match["home_goals"] if is_home else match["away_goals"]
        goals_against_ = match["away_goals"] if is_home else match["home_goals"]
        result = "W" if goals_for_ > goals_against_ else "L" if goals_for_ < goals_against_ else "D"

        last_results.append({
            "home": match["home"],
            "away": match["away"],
            "home_goals": match["home_goals"],
            "away_goals": match["away_goals"],
            "result": result
        })

    holding = con.execute("""
        SELECT volume, avg_cost FROM stock_holdings WHERE club_name = ?
    """, (club_name,)).fetchone()

    volume = holding["volume"] if holding else 0
    avg_cost = holding["avg_cost"] if holding else 0
    total_cost = volume * avg_cost
    current_value = volume * stock_price
    dollar_return = round(current_value - total_cost, 2) if volume > 0 else 0
    percent_return = round((dollar_return / total_cost), 4) if total_cost > 0 else 0


    ratings = con.execute("""
        SELECT gameweek, rating FROM ratings_history
        WHERE club_name = ?
        ORDER BY gameweek
    """, (club_name,)).fetchall()

    ratings_data = [{"gameweek": r["gameweek"], "rating": r["rating"]} for r in ratings]

    last_2 = ratings_data[-2:] if len(ratings_data) >= 2 else []
    weekly_change = 0
    dollar_change = 0
    if len(last_2) == 2:
        prev = last_2[0]["rating"] * 100
        curr = last_2[1]["rating"] * 100
        dollar_change = round(curr - prev, 2)
        weekly_change = round((curr - prev) / prev, 4) if prev > 0 else 0
    
    if len(ratings_data) > 1:
        x = [r["gameweek"] for r in ratings_data if r["gameweek"] > 0]
        y = [r["rating"] * 100 for r in ratings_data if r["gameweek"] > 0]
        color = "#00FF00" if y[-1] >= y[0] else "#FF4C4C"
        plt.figure(figsize=(10, 5))
        plt.plot(x, y, marker="o", color=color, linewidth=2)
        plt.title(f"{club_name} Stock History", fontsize=14, color="white")
        plt.xlabel("Gameweek", color="white")
        plt.ylabel("Share Price ($)", color="white")
        plt.grid(True, linestyle="--", alpha=0.3)
        plt.xticks(color='white')
        plt.yticks(color='white')
        plt.gca().set_facecolor('#0d1117')
        plt.gcf().patch.set_facecolor('#0d1117')
        plt.tight_layout()
        safe_filename = club_name.lower().replace(" ", "_").replace(".", "").replace(",", "") + ".png"
        graph_path = os.path.join(os.path.dirname(__file__), "static", "images", "graphs", safe_filename)
        os.makedirs(os.path.dirname(graph_path), exist_ok=True)
        plt.savefig(graph_path, dpi=150, bbox_inches='tight', transparent=False)
        plt.show()
        plt.close()
    else:
        safe_filename = None

    # Description
    description = con.execute("""
        SELECT description FROM clubs_descs WHERE club_name = ?
    """, (club_name,)).fetchone()
    description = description["description"] if description else "No description available."


    financials = pull_financials(club_name)

    bankroll = con.execute("SELECT bankroll FROM equity").fetchone()["bankroll"]

    filename2 = filename.rsplit('.', 1)
    filename2 = filename2[0] + "2." + filename2[1]

    context = {
        "bankroll": bankroll,
        "club_name": club_name,
        "filename": filename,
        "filename2": filename2,
        "stock_price": stock_price,
        "position": position,
        "goals_for": goals_for,
        "goals_against": goals_against,
        "goal_diff": goal_diff,
        "points": points,
        "last_results": last_results,
        "dollar_change": dollar_change,
        "ratings_data": ratings_data,
        "weekly_change": weekly_change * 100,
        "description": description,
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "graph_filename": safe_filename,
        "holding": {
            "volume": volume,
            "avg_cost": round(avg_cost, 4),
            "value": round(current_value, 4),
            "total_cost": round(total_cost, 4),
            "return": dollar_return,
            "return_pct": percent_return * 100
        },
        "financials": financials
    }

    return flask.render_template("oneclub.html", **context)
