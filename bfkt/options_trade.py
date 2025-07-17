import os
import flask
import math
from scipy.stats import norm
import numpy as np
import matplotlib.pyplot as plt
import random
from bfkt import app  
from bfkt.models import get_db
from flask import render_template

@app.route('/handle_optionsbuy', methods=['POST'])
def options_handlebuy():
    import flask
    con = get_db()
    data = flask.request.get_json()

    club = data["club"]
    option_type = data["type"]  # "call" or "put"
    strike = float(data["strike"])
    expiry = int(data["expiry_gw"])
    premium = float(data["premium"])
    contracts = int(data["contracts"])

    print("ENTERED HEREEEEEEE")

    total_cost = round(contracts * premium * 100, 2)

    bankroll_row = con.execute("SELECT bankroll FROM equity").fetchone()
    bankroll = bankroll_row["bankroll"] if bankroll_row else 0.0

    print("bankroll is ", bankroll, "and total cost is ", total_cost)
    if total_cost > bankroll:
        return flask.jsonify({"error": "Insufficient funds"}), 400

    gameweek = con.execute("SELECT gameweek FROM status").fetchone()["gameweek"]

    rating_row = con.execute("SELECT initial_rating FROM participants WHERE name = ?", (club,)).fetchone()
    if not rating_row:
        return flask.jsonify({"error": "Invalid club"}), 400
    underlying_price = round(rating_row["initial_rating"] * 100.0, 2)

    print(f"type is {option_type} strike is {strike}, underlying is {underlying_price}, contracts is {contracts}, premium is {premium}, gameweek traded is {gameweek}, gwexpiry is {expiry}")
    con.execute("""
        INSERT INTO options_history (
            type, action, underlying, strike, underlying_price, contracts,
            premium, gameweek_traded, gameweek_expiry
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        option_type, "buy", club, strike, underlying_price, contracts,
        premium, gameweek, expiry
    ))

    con.execute("""
        INSERT INTO options_holdings (
            type, underlying, strike, expiration_gw, cost, contracts, expired, curr_premium
        ) VALUES (?, ?, ?, ?, ?, ?, 0, ?)
    """, (
        option_type, club, strike, expiry, premium, contracts, premium
    ))

    con.execute("""
        UPDATE equity SET bankroll = bankroll - ?
    """, (total_cost,))

    con.commit()
    return "", 200

@app.route('/sell_option', methods=['POST'])
def sell_option():
    con = get_db()
    data = flask.request.get_json()

    holding_id = int(data["holding_id"])
    contracts_to_sell = int(data["contracts"])

    option = con.execute("""
        SELECT * FROM options_holdings WHERE holding_id = ?
    """, (holding_id,)).fetchone()

    if not option or option["contracts"] < contracts_to_sell:
        return flask.jsonify({"error": "Invalid request"}), 400

    contracts_held = option["contracts"]
    full_sale = (contracts_to_sell == contracts_held)

    premium_now = option["curr_premium"]
    market_value = premium_now * 100 * contracts_to_sell

    # Update bankroll
    con.execute("UPDATE equity SET bankroll = bankroll + ?", (market_value,))

    current_gw = con.execute("SELECT gameweek FROM status").fetchone()["gameweek"]
    underlying_price = con.execute("SELECT initial_rating FROM participants WHERE name = ?", (option["underlying"],)).fetchone()["initial_rating"] * 100.0

    # Insert into options_history
    buy_gameweek_row = con.execute("""
        SELECT gameweek_traded FROM options_history
        WHERE type = ? AND action = 'buy' AND underlying = ? AND strike = ? AND gameweek_expiry = ?
        ORDER BY gameweek_traded ASC LIMIT 1
    """, (option["type"], option["underlying"], option["strike"], option["expiration_gw"])).fetchone()

    buy_gameweek = buy_gameweek_row["gameweek_traded"] if buy_gameweek_row else None
    premium_bought = option["cost"]
    realized_pnl = round((premium_now - premium_bought) * 100 * contracts_to_sell, 2)

    con.execute("""
        INSERT INTO options_history (
            type, action, underlying, strike, underlying_price, contracts, premium,
            gameweek_traded, gameweek_expiry, buy_gameweek, premium_bought, profit_made
        ) VALUES (?, 'sell', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        option["type"], option["underlying"], option["strike"],
        underlying_price, contracts_to_sell, premium_now,
        current_gw, option["expiration_gw"], buy_gameweek, premium_bought, realized_pnl
    ))

    if full_sale:
        itm_otm = "itm" if premium_now >= premium_bought else "otm"
        con.execute("""
            UPDATE options_holdings
            SET expired = 1,
                held_till_expiry = 0,
                itm_otm = ?,
                expired_underlying = ?
            WHERE holding_id = ?
        """, (itm_otm, underlying_price, holding_id))
    else:
        con.execute("""
            UPDATE options_holdings
            SET contracts = contracts - ?
            WHERE holding_id = ?
        """, (contracts_to_sell, holding_id))

    con.commit()
    return "", 200
