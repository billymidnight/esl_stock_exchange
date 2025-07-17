import os
import flask
import random
import numpy as np
import random
import math
from bfkt import app  # Import the Flask app from the app module
from bfkt.models import get_db

@app.route('/seasonend/', methods=["POST"])
def seasonend():
    con = get_db()
    winner = con.execute("SELECT name FROM standings "
                                "ORDER BY points DESC LIMIT 1").fetchone()["name"]
    
    year = con.execute("SELECT year FROM year").fetchone()["year"]
    year = int(year)
    con.execute("INSERT INTO champions VALUES (?,?)", (year, winner))

    matches = con.execute(
        "SELECT home, away, home_goals, away_goals FROM matches"
    ).fetchall()

    matches_with_year = [
        (year, match["home"], match["away"], match["home_goals"], match["away_goals"])
        for match in matches
    ]

    con.executemany(
        "INSERT INTO centralunit (year, home, away, home_goals, away_goals) VALUES (?, ?, ?, ?, ?)",
        matches_with_year
    )

    con.execute("DELETE FROM matches")

    # Reset gameweek and gameno in status table
    con.execute("UPDATE status SET gameweek = 1, gameno = 0")

    # Delete all rows from schedule table
    con.execute("DELETE FROM schedule")

    con.execute("DELETE FROM standings")

    con.execute("insert into standings (name) " 
                "select name from participants")
    
    
    year += 1
    con.execute("update year set year = ?", (year,))

    return flask.redirect('/')
    

     
