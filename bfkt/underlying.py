import os
import flask
import random
import numpy as np
import random
import math
from bfkt import app  
from bfkt.models import get_db



@app.route('/handle_buyorder', methods=['POST'])
def handle_buyorder():
    data = flask.request.get_json()
    club_name = data.get("club_name")
    trade_type = data.get("trade_type")  
    volume = int(data.get("volume"))
    price = float(data.get("price"))
    
    total_cost = volume * price

    con = get_db()
    cur = con.cursor()

    bankroll_row = cur.execute("SELECT bankroll FROM equity").fetchone()
    if bankroll_row is None:
        return flask.jsonify({"error": "Bankroll not initialized."}), 400

    current_bankroll = bankroll_row["bankroll"]

    if total_cost > current_bankroll:
        return flask.jsonify({"error": "Insufficient funds."}), 400

    gameweek_row = cur.execute("SELECT gameweek FROM status").fetchone()
    gameweek = gameweek_row["gameweek"] if gameweek_row else 0

    cur.execute("""
        INSERT INTO transactions (gameweek, club_name, action, volume_traded, underlying_price)
        VALUES (?, ?, 'buy', ?, ?)
    """, (gameweek, club_name, volume, price))

    existing = cur.execute("""
        SELECT volume, avg_cost FROM stock_holdings
        WHERE club_name = ?
    """, (club_name,)).fetchone()

    old_volume = existing["volume"]
    old_avg_cost = existing["avg_cost"]

    new_volume = old_volume + volume
    new_avg_cost = (
        (old_volume * old_avg_cost) + (volume * price)
    ) / new_volume if new_volume > 0 else price

    cur.execute("""
        UPDATE stock_holdings
        SET volume = ?, avg_cost = ?
        WHERE club_name = ?
    """, (new_volume, new_avg_cost, club_name))

    cur.execute("""
        UPDATE equity
        SET bankroll = bankroll - ?
    """, (total_cost,))

    con.commit()

    return flask.jsonify({"success": True, "message": f"{club_name} stock bought successfully."})

@app.route('/handle_sellorder', methods=['POST'])
def handle_sellorder():
    data = flask.request.get_json()
    club_name = data.get("club_name")
    trade_type = data.get("trade_type")  
    volume = int(data.get("volume"))
    price = float(data.get("price"))

    total_gain = volume * price

    con = get_db()
    cur = con.cursor()

    gameweek_row = cur.execute("SELECT gameweek FROM status").fetchone()
    gameweek = gameweek_row["gameweek"] if gameweek_row else 0

    holding = cur.execute("""
        SELECT volume, avg_cost FROM stock_holdings
        WHERE club_name = ?
    """, (club_name,)).fetchone()

    if holding is None or holding["volume"] < volume:
        return flask.jsonify({"error": "Insufficient shares to sell."}), 400

    old_volume = holding["volume"]
    old_avg_cost = holding["avg_cost"]

    new_volume = old_volume - volume
    new_avg_cost = 0 if new_volume == 0 else old_avg_cost  

    cur.execute("""
        UPDATE stock_holdings
        SET volume = ?, avg_cost = ?
        WHERE club_name = ?
    """, (new_volume, new_avg_cost, club_name))

    cur.execute("""
        INSERT INTO transactions (gameweek, club_name, action, volume_traded, underlying_price)
        VALUES (?, ?, 'sell', ?, ?)
    """, (gameweek, club_name, volume, price))

    cur.execute("""
        UPDATE equity
        SET bankroll = bankroll + ?
    """, (total_gain,))

    con.commit()

    return flask.jsonify({"success": True, "message": f"{club_name} stock sold successfully."})
