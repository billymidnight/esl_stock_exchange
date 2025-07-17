import os
import flask
import numpy as np
from bfkt import app  
from bfkt.models import get_db

from scipy.stats import poisson

@app.route('/', methods=['GET'])
def show_standings():
    con = get_db()
    cur = con.execute(
        "SELECT * FROM standings "
        "ORDER BY points DESC, goal_difference DESC, goals_for DESC, name ASC"
    )
    standings = cur.fetchall()

    for index, row in enumerate(standings, start=1):
        row["position"] = index

    for player in standings:
        name = player["name"]
        cur = con.execute("SELECT filename FROM participants WHERE name = ?", (name,))
        img_name = cur.fetchone()["filename"]
        player["img_name"] = img_name

    matchday = con.execute("SELECT gameweek FROM status").fetchone()["gameweek"]
    gameno = con.execute("SELECT gameno FROM status").fetchone()["gameno"]

    earliest = con.execute(
        "SELECT id FROM schedule ORDER BY id LIMIT 1"
    ).fetchone()

    fixture = None  
    actualid = 1
    homeodds, awayodds, drawodds = None, None, None

    if earliest:
        actualid = earliest["id"] + gameno
        earliestmatch = earliest["id"]
        fixture = con.execute("SELECT home, away FROM schedule WHERE id = ?", (earliestmatch + gameno, )).fetchone()

    if fixture:
        homenext = fixture["home"]
        awaynext = fixture["away"]
        homepic = con.execute("SELECT filename FROM participants WHERE name = ?", (homenext,)).fetchone()["filename"]
        awaypic = con.execute("SELECT filename FROM participants WHERE name = ?", (awaynext,)).fetchone()["filename"]

        home_rating = con.execute("SELECT initial_rating FROM participants WHERE name = ?", (homenext,)).fetchone()["initial_rating"]
        away_rating = con.execute("SELECT initial_rating FROM participants WHERE name = ?", (awaynext,)).fetchone()["initial_rating"]

        scaling_factor = 3
        home_advantage = 1.08

        total_rating = home_rating + away_rating
    
        a_goal_prob = home_rating / total_rating
        b_goal_prob = away_rating / total_rating
        
        a_expected_goals = a_goal_prob * scaling_factor * home_advantage
        b_expected_goals = b_goal_prob * scaling_factor
        homewins = 0
        awaywins = 0
        draws = 0
        for _ in range(10000):

            a_goals = np.random.poisson(a_expected_goals)
            b_goals = np.random.poisson(b_expected_goals)
            if a_goals > b_goals:
                homewins += 1
            elif b_goals > a_goals:
                awaywins += 1
            else:
                draws += 1
        home_win_prob = homewins / 10000
        away_win_prob = awaywins / 10000
        draw_prob = draws / 10000

        print(f"home win prob is {home_win_prob} and away win prob is {away_win_prob} and draw prob is {draw_prob}")

        # Normalize probabilities (apply 3% vig to each)
        total_prob = home_win_prob + away_win_prob + draw_prob
        home_win_prob = (home_win_prob / total_prob) * 1.09
        away_win_prob = (away_win_prob / total_prob) * 1.09
        draw_prob = (draw_prob / total_prob) * 1.09

        print("home odds is ", home_win_prob, " away odds is ", away_win_prob, " and draw odds is ", draw_prob)
        

        homeodds = round(-100 * home_win_prob / (1 - home_win_prob)) if home_win_prob > 0.5 else round(100 * ((1 - home_win_prob) / home_win_prob))
        awayodds = round(-100 * away_win_prob / (1 - away_win_prob)) if away_win_prob > 0.5 else round(100 * ((1 - away_win_prob) / away_win_prob))
        drawodds = round(-100 * draw_prob / (1 - draw_prob)) if draw_prob > 0.5 else round(100 * ((1 - draw_prob) / draw_prob))


        print("home odds is ", homeodds, " away odds is ", awayodds, " and draw odds is ", drawodds)
        

        fixture_data = {
            "homename": homenext,
            "awayname": awaynext,
            "homepic": homepic,
            "awaypic": awaypic,
        }
    else:
        fixture_data = {
            "homename": "No Match",
            "awayname": "Scheduled",
            "homepic": "placeholder.jpg",
            "awaypic": "placeholder.jpg",
        }

    matchday2 = con.execute("SELECT gameweek FROM status").fetchone()["gameweek"]
    gameno2 = con.execute("SELECT gameno FROM status").fetchone()["gameno"]

    matchid = (matchday2 - 1) * 10 + gameno2 + 1
    print(f"MATCH ID BEING SENT IS NONE OTHER THAN {matchid}")
    
    notanyodds = con.execute("SELECT noodds from noodds").fetchone()["noodds"]

    if notanyodds == 1:
        noodds = True
    else:
        noodds = False
    bankroll = con.execute("SELECT curr_bankroll FROM bankroll").fetchone()["curr_bankroll"]
    context = {
        "gamenohere": gameno2,
        "standings": standings,
        "matchday": matchday,
        "gameno": actualid,
        "matchid": matchid,
        "noodds": noodds,
        "fixture": fixture_data,
        "bankroll": round(bankroll,2),
        "homeodds": homeodds,
        "awayodds": awayodds,
        "drawodds": drawodds,
    }

    return flask.render_template("league.html", **context)


@app.route('/update_standings/', methods=['POST'])
def update_standings():
    con = get_db()
    
    home = flask.request.form["home"]
    away = flask.request.form["away"]
    homegoals = int(flask.request.form["homegoals"])
    awaygoals = int(flask.request.form["awaygoals"])

    homename = con.execute("SELECT name FROM participants WHERE name = ?", (home,)).fetchone()
    if homename is None:
        flask.abort(404, description="Home participant not available in BFKT")
    awayname = con.execute("SELECT name FROM participants WHERE name = ?", (away,)).fetchone()
    if awayname is None:
        flask.abort(404, description="Away participant not available in BFKT")
    
    con.execute(
        "INSERT INTO matches (home, away, home_goals, away_goals) VALUES (?, ?, ?, ?)",
        (home, away, homegoals, awaygoals)
    )
    
    home_standings = con.execute("SELECT * FROM standings WHERE name = ?", (home,)).fetchone()
    away_standings = con.execute("SELECT * FROM standings WHERE name = ?", (away,)).fetchone()
    
    if homegoals == awaygoals:
        con.execute(
            "UPDATE standings SET matches_played = ?, draws = ?, goals_for = ?, goals_against = ?, points = ? WHERE name = ?",
            (home_standings["matches_played"] + 1, home_standings["draws"] + 1, home_standings["goals_for"] + homegoals,
             home_standings["goals_against"] + awaygoals, home_standings["points"] + 1, home)
        )
        con.execute(
            "UPDATE standings SET matches_played = ?, draws = ?, goals_for = ?, goals_against = ?, points = ? WHERE name = ?",
            (away_standings["matches_played"] + 1, away_standings["draws"] + 1, away_standings["goals_for"] + awaygoals,
             away_standings["goals_against"] + homegoals, away_standings["points"] + 1, away)
        )
    elif homegoals > awaygoals:
        con.execute(
            "UPDATE standings SET matches_played = ?, wins = ?, goals_for = ?, goals_against = ?, points = ? WHERE name = ?",
            (home_standings["matches_played"] + 1, home_standings["wins"] + 1, home_standings["goals_for"] + homegoals,
             home_standings["goals_against"] + awaygoals, home_standings["points"] + 3, home)
        )
        con.execute(
            "UPDATE standings SET matches_played = ?, losses = ?, goals_for = ?, goals_against = ? WHERE name = ?",
            (away_standings["matches_played"] + 1, away_standings["losses"] + 1, away_standings["goals_for"] + awaygoals,
             away_standings["goals_against"] + homegoals, away)
        )
    else:
        con.execute(
            "UPDATE standings SET matches_played = ?, losses = ?, goals_for = ?, goals_against = ? WHERE name = ?",
            (home_standings["matches_played"] + 1, home_standings["losses"] + 1, home_standings["goals_for"] + homegoals,
             home_standings["goals_against"] + awaygoals, home)
        )
        con.execute(
            "UPDATE standings SET matches_played = ?, wins = ?, goals_for = ?, goals_against = ?, points = ? WHERE name = ?",
            (away_standings["matches_played"] + 1, away_standings["wins"] + 1, away_standings["goals_for"] + awaygoals,
             away_standings["goals_against"] + homegoals, away_standings["points"] + 3, away)
        )
    
    con.execute(
        "UPDATE standings SET goal_difference = ? WHERE name = ?",
        (home_standings["goal_difference"] + (homegoals - awaygoals), home)
    )
    con.execute(
        "UPDATE standings SET goal_difference = ? WHERE name = ?",
        (away_standings["goal_difference"] + (awaygoals - homegoals), away)
    )
    con.commit() 
    return flask.redirect('/')


        


