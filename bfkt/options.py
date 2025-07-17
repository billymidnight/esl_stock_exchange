import os
import flask
import math
from scipy.stats import norm
import numpy as np
import matplotlib.pyplot as plt
import random
from bfkt import app  
from bfkt.models import get_db, prob_to_american, format_american_odds, prob_to_decimal
from flask import render_template



def black_scholes(S, K, T, vol, r=0.001):
    """
    K: Strike price
    T: Time to expiry (number of gameweeks)
    S: Current stock price (underlying)
    vol: Volatility (from participants table)
    r: Risk-free rate (default = 0.01)
    """

    if T <= 0:
        return 0.0, 0.0  # option has expired or is expiring immediately
    
    vol = vol * 1.55
    sigma = vol
    sqrt_T = math.sqrt(T)

    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * sqrt_T)
    d2 = d1 - sigma * sqrt_T

    call = S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
    put = K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)

    return round(call, 5), round(put, 5), norm.cdf(d2)

@app.route('/options_machine/')
def options_machine():
    con = get_db()
    club_name = flask.request.args.get("club")
    if not club_name:
        return "No club forwarded unfortunately", 400
    
    # pull everything relevant about club
    club_row = con.execute("""
        SELECT initial_rating, volatility, drift, gw_played, nation
        FROM participants
        where name = ?
        """, (club_name,)).fetchone()
    
    if not club_row:
        return "Non-existent club unfortunately", 400
    
    S = round(club_row["initial_rating"] * 100.0, 2) #pull underlying
    vol = club_row["volatility"]
    drift = club_row["drift"]
    gw_played = club_row["gw_played"]

    current_gw = con.execute("SELECT gameweek FROM status").fetchone()["gameweek"]

    standings = con.execute("""
        SELECT name FROM standings
        ORDER BY points DESC, goal_difference DESC, goals_for DESC, name ASC
    """).fetchall()
    position = [i+1 for i, row in enumerate(standings) if row["name"] == club_name]
    position = position[0] if position else "?"

    # tick increments for the strike ladder
    
    if S >= 300:
        tick = 2.5
    elif S >= 150 and S <= 300:
        tick = 2.5
    elif S >= 40:
        tick = 1.0
    else:
        tick = 0.5
    
    mid_strike = round(round(S / tick) * tick, 2)

    strikes = [round(mid_strike + tick * i, 2) for i in range(-10, 11)]

    if vol >= 0.05:
        strikes = [round(mid_strike + tick * i, 2) for i in range(-15, 16)]

    expiry_gws = [current_gw + i for i in range(1,6)]

    option_chains = {}

    for expiry in expiry_gws:
        gameno = con.execute("SELECT gameno FROM status").fetchone()["gameno"]
        games_left_this_week = 10 - gameno
        games_toexpiry = games_left_this_week + 10 * (expiry-current_gw)
        T = (expiry - current_gw) + (1 if not gw_played else 0) + (games_toexpiry / 40.0)
        print("T is ", T)
        chain = []
        
        for K in strikes:
            call_theo, put_theo, call_prob = black_scholes(S, K, T, vol, r = drift * 0.2)
            put_prob = 1 - call_prob

            
            spread_pct = max(0.001, random.gauss(1.2, 0.4) / 100.0)
            call_bid = round(call_theo * (1 - spread_pct), 2)
            call_ask = round(call_theo * (1 + spread_pct), 2)
            put_bid = round(put_theo * (1 - spread_pct), 2)
            put_ask = round(put_theo * (1 + spread_pct), 2)


            chain.append({
                "strike": K,
                "call_bid": call_bid,
                "call_ask": call_ask,
                "put_bid": put_bid,
                "put_ask": put_ask,
                "call_prob": round(call_prob, 3),
                "put_prob": round(put_prob, 3),
                "call_odds": format_american_odds(prob_to_american(call_prob)),
                "put_odds": format_american_odds(prob_to_american(put_prob)),
                "call_decimal": prob_to_decimal(call_prob),
                "put_decimal": prob_to_decimal(put_prob)
                
            })

            print(f"the over decimal odds is {prob_to_decimal(call_prob)}")
            
        option_chains[f"expiry_{expiry}"] = chain
    
    bankroll_row = con.execute("SELECT bankroll FROM equity").fetchone()
    bankroll = bankroll_row["bankroll"] if bankroll_row else 0

    holding_value = con.execute("""
        SELECT SUM(sh.volume * (p.initial_rating * 100.0)) AS total_value
        FROM stock_holdings sh
        JOIN participants p ON sh.club_name = p.name
    """).fetchone()["total_value"]

    holding_value = holding_value if holding_value else 0

    options_value = con.execute("""
        SELECT SUM(curr_premium * contracts * 100.0) AS option_value
        FROM options_holdings
        WHERE contracts > 0 AND expired = False
    """).fetchone()["option_value"]
    options_value = options_value if options_value else 0

    equity = round(bankroll + holding_value + options_value, 2)
    bankroll = round(bankroll, 2)
    gameweek = con.execute("SELECT gameweek FROM status").fetchone()["gameweek"]

    if gw_played:
        match = con.execute("""
            SELECT * FROM matches 
            WHERE (home = ? OR away = ?) 
            ORDER BY match_id DESC LIMIT 1
        """, (club_name, club_name)).fetchone()

        if match:
            is_home = match["home"] == club_name
            home_goals = match["home_goals"]
            away_goals = match["away_goals"]

            if is_home:
                result_text = f"{match['home']} {home_goals} - {away_goals} {match['away']}"
                if home_goals > away_goals:
                    result_outcome = "W"
                elif home_goals < away_goals:
                    result_outcome = "L"
                else:
                    result_outcome = "D"
            else:
                result_text = f"{match['away']} {away_goals} - {home_goals} {match['home']}"
                if away_goals > home_goals:
                    result_outcome = "W"
                elif away_goals < home_goals:
                    result_outcome = "L"
                else:
                    result_outcome = "D"
        else:
            result_text = "No past results found"
            result_outcome = ""
    else:
        scheduled = con.execute("""
            SELECT * FROM schedule 
            WHERE home = ? OR away = ?
            ORDER BY id ASC
        """, (club_name, club_name)).fetchall()

        upcoming = next((row for row in scheduled if row["home"] == club_name or row["away"] == club_name), None)

        if upcoming:
            opponent = upcoming["away"] if upcoming["home"] == club_name else upcoming["home"]
            result_text = f"Upcoming vs. {opponent}"
        else:
            result_text = f"Yet to play Gameweek {gameweek}"
        result_outcome = ""

    return render_template("options_chain.html",
                           bankroll=bankroll,
                           equity=equity,
                           gameweek=gameweek,
                           club_name=club_name,
                           position=position,
                           underlying_price=S,
                           latest_result=result_text,
                           result_outcome=result_outcome,
                           option_chains=option_chains)
