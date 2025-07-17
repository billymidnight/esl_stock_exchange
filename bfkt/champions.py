import os
import flask
import random
import numpy as np
import random
import math
from bfkt import app 
from bfkt.models import get_db

@app.route('/champions/', methods=["GET"])
def pastwinners():
    con = get_db()
    cur = con.execute(
        """
        SELECT champions.year, champions.winner, participants.filename
        FROM champions
        JOIN participants ON champions.winner = participants.name
        ORDER BY champions.year DESC
        """
    )
    winners = cur.fetchall()

    context = {
        "winners": winners
    }
    return flask.render_template("winners.html", **context)