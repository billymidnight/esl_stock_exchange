import os
import flask
import math
from scipy.stats import norm
import numpy as np
import matplotlib.pyplot as plt
import random
from bfkt import app  
from bfkt.models import get_db
from flask import render_template, request, jsonify

@app.route('/obet_handler/', methods=['GET', 'POST'])
def obet_handler():
    data = request.get_json()
    club = data.get('club')
    bet_type = data.get('type')
    strike = data.get('strike')
    expiry = data.get('expiry')
    odds = data.get('odds')
    size = data.get('size')
    decimalOdds = data.get('decodds')

    print(decimalOdds, " is the decimal odds motherfrucker")


    if not all([club, bet_type, strike is not None, expiry, odds, size]):
        return jsonify({'error': 'Missing data fields'}), 400

    con = get_db()

    theclub = con.execute("SELECT 1 FROM participants WHERE name = ?", (club,)).fetchone()
    if not theclub:
        return jsonify({'error': 'Club does not exist'}), 404
    
    bankroll_row = con.execute("SELECT bankroll FROM equity").fetchone()
    if not bankroll_row:
        return jsonify({'error': 'User equity not found'}), 404
    
    bankroll = bankroll_row["bankroll"]
    if bankroll < size:
        return jsonify({'error': 'Insufficient funds'}), 403

    gw_row = con.execute("SELECT gameweek FROM status").fetchone()
    if not gw_row:
        return jsonify({'error': 'Could not fetch gameweek'}), 500
    
    current_gw = gw_row["gameweek"]

    potential_payout = round(size * decimalOdds, 2)

    print("odds for this one is ", {odds})

    con.execute("""
        INSERT INTO options_bets (
            obet_underlying,
            obet_type,
            obet_strike,
            obet_expiry,
            obet_size,
            obet_odds,
            obet_potential_payout,
            obet_gw_placed,
            obet_placed_price
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        club,
        bet_type,
        strike,
        expiry,
        size,
        odds,
        potential_payout,
        current_gw,
        size  
    ))

    new_bankroll = bankroll - size
    con.execute("UPDATE equity SET bankroll = ?", (new_bankroll,))

    con.commit()
    return jsonify({'success': True}), 200