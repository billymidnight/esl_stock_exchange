import os
import flask
import random
from bfkt import app  
from bfkt.models import get_db

@app.route('/scheduler/', methods=['GET'])
def schedule():

    con = get_db()
    x = 0
    con.execute("UPDATE noodds SET noodds = ?", (x,))
    gameweek = con.execute("SELECT gameweek FROM status").fetchone()["gameweek"]

    cur = con.execute("SELECT name FROM participants")
    players = [row["name"] for row in cur.fetchall()]

    random.shuffle(players)
    matches = [{"home": players[i], "away": players[i + 1]} for i in range(0, len(players), 2)]

    con.execute("DELETE FROM schedule")

    for match in matches:
        homename = match["home"]
        awayname = match["away"]

        homepic = con.execute("SELECT filename FROM participants WHERE name = ?", (homename,)).fetchone()["filename"]
        awaypic = con.execute("SELECT filename FROM participants WHERE name = ?", (awayname,)).fetchone()["filename"]
        match["homepic"] = homepic
        match["awaypic"] = awaypic

        con.execute(
            "INSERT INTO schedule (home, away) VALUES (?, ?)",
            (homename, awayname)
        )

    con.commit()

    context = {"matches": matches, "gameweek": gameweek}
    return flask.render_template("schedule.html", **context)

@app.route('/schedule/view', methods=['GET'])
def view_schedule():
    con = get_db()

    gameweek = con.execute("SELECT gameweek FROM status").fetchone()["gameweek"]

    schedule = con.execute("SELECT home, away FROM schedule").fetchall()
    matches = []

    for match in schedule:
        home = match["home"]
        away = match["away"]

        homepic = con.execute(
            "SELECT filename FROM participants WHERE name = ?", (home,)
        ).fetchone()["filename"]
        
        awaypic = con.execute(
            "SELECT filename FROM participants WHERE name = ?", (away,)
        ).fetchone()["filename"]

        matches.append({
            "home": home,
            "away": away,
            "homepic": homepic,
            "awaypic": awaypic
        })

    context = {
        "gameweek": gameweek,
        "matches": matches
    }
    
    return flask.render_template("schedule.html", **context)