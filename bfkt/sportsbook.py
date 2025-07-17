import flask
from flask import render_template
from bfkt.models import get_db
from bfkt import app
import math

def round_to_2_sig_figs(num):
    if num == 0:
        return 0
    else:
        from math import log10, floor
        return round(num, -int(floor(log10(abs(num))) - 1))


@app.route('/sportsbook/', methods=['GET'])
def sportsbook_handler():
    con = get_db()

    participants = con.execute("""
        SELECT participants.name AS name, 
               filename AS filename, 
               CAST(initial_rating AS REAL) AS initial_rating, 
               CAST(drift AS REAL) AS drift,
               points AS points
        FROM participants
        JOIN standings ON participants.name = standings.name                     
    """).fetchall()

    print("Participants fetched from DB:", participants)

    scores = {}
    invalid_entries = []

    curr_gw = con.execute("SELECT gameweek FROM status").fetchone()["gameweek"]
    # Calculate scores
    for row in participants:
        try:
            name = row["name"]
            filename = row["filename"]
            initial_rating = float(row["initial_rating"])
            points = int(row["points"])
            drift = float(row["drift"])
            
            print("club is ", name)
            
            # Calculate score
            score = (initial_rating**3 + (255 - curr_gw) * (initial_rating * drift))**1.5
            score = points**1.75 + 2*score * (255 - curr_gw)
            score = score ** ((curr_gw)/4)
            print(score)
            scores[name] = {"score": score, "filename": filename}
        except (ValueError, TypeError, KeyError) as e:
            print(f"Invalid entry for participant {row}: {e}")  # Debug invalid data
            invalid_entries.append(row)
            continue

    if invalid_entries:
        print("Invalid entries detected:", invalid_entries)

    total_score = sum(item["score"] for item in scores.values())
    if total_score == 0:
        print("Error: Total score is zero. Scores:", scores)
        return "Error: Unable to calculate odds due to zero total score", 500

    odds_data = []
    for name, data in scores.items():
        score = data["score"]
        filename = data["filename"]
        probability = score / total_score
        probability = probability * 1.05
        american_odds = round(((1 / probability - 1) * 100)) if probability < 0.5 else round(-((probability / (1 - probability)) * 100))
        
        american_odds = round_to_2_sig_figs(american_odds)
        
        if american_odds > 10000000000000:
            continue
        odds_data.append({"name": name, "filename": filename, "odds": abs(american_odds)})

    odds_data.sort(key=lambda x: x["odds"])


    return render_template('sportsbook.html', odds=odds_data)



@app.route('/bet_handler/', methods=['POST'])
def bet_handler():

    type = flask.request.form.get("type")
    stake = flask.request.form.get("stake")
    odds = flask.request.form.get("odds")
    stake = float(stake)
    odds = int(odds)

    if type == "futures":
        participant = flask.request.form.get("participant")
        ppayout = stake * (odds/100)

        con = get_db()
        con.execute("INSERT INTO futures_bets" 
                    "(horse, stake, odds, payout, status) VALUES "
                    "(?,?,?,?,?)", (participant, stake, odds, ppayout, "live",))
        con.execute("UPDATE bankroll SET curr_bankroll = curr_bankroll - ? WHERE curr_bankroll >= ?", (stake, stake,))
        return flask.redirect('/sportsbook/')
    
    else:
        horse = flask.request.form.get("horse")
        matchid = flask.request.form.get("idmatch")
        home = flask.request.form.get("home")
        away = flask.request.form.get("away")
        if odds > 0:
            ppayout =  stake * (odds/100)
        else:
            ppayout = stake * -(100/odds)

        con = get_db()
        con.execute("INSERT INTO ml_bets" 
                    "(gameid, home, away, horse, stake, odds, payout, status) VALUES "
                    "(?,?,?,?,?,?,?,?)", (matchid, home, away, horse, stake, odds, ppayout, "live",))
        con.execute("UPDATE bankroll SET curr_bankroll = curr_bankroll - ? WHERE curr_bankroll >= ?", (stake, stake,))

        return flask.redirect('/')

@app.route('/mybets_viewer/', methods=['GET'])
def mybets_viewer():
    con = get_db()
    cur = con.execute(
        "SELECT horse, stake, odds, payout "
        "FROM futures_bets WHERE status = ? ORDER BY betid DESC", ("live",))
    livebets = cur.fetchall()
    cur = con.execute(
        "SELECT horse, stake, odds, payout "
        "FROM futures_bets WHERE status = ? ORDER BY betid DESC", ("past",))
    pastbets = cur.fetchall()
    cur = con.execute(
        "SELECT horse, home, away, stake, odds, payout "
        "FROM ml_bets WHERE status = ? ORDER BY betid DESC", ("live",))
    livemlbets = cur.fetchall()
    cur = con.execute(
        "SELECT winlose, horse, home, away, actualhome, actualaway, stake, odds, payout "
        "FROM ml_bets WHERE status = ? ORDER BY betid DESC", ("past",))
    pastmlbets = cur.fetchall()

    context = {
        "livebets": livebets,
        "pastbets": pastbets,
        "livemlbets": livemlbets,
        "pastmlbets": pastmlbets
    }
    

    return flask.render_template("mybets.html", **context)
    