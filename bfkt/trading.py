import os
import flask
import random
import numpy as np
import random
import math
from scipy.stats import norm
from bfkt import app  # Import the Flask app from the app module
from bfkt.models import get_db

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

    return round(call, 5), round(put, 5)

def equity_calc():
    con = get_db()
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

    return bankroll, equity

@app.route('/traderopener/', methods=['GET'])
def traderopener():
    con = get_db()

    cur = con.execute(
        "SELECT p.name, p.filename, s.points, s.goal_difference, "
        "s.wins, s.draws, s.losses, s.goals_for, s.goals_against, "
        "(p.initial_rating * 100.0) AS price "
        "FROM participants p "
        "JOIN standings s ON p.name = s.name "
        "ORDER BY p.name ASC"
    )

    clubs = cur.fetchall()

    sorted_by_performance = sorted(clubs, key=lambda row: (-row["points"], -row["goal_difference"], -row["goals_for"], row["name"]))
    name_to_position = {club["name"]: i + 1 for i, club in enumerate(sorted_by_performance)}

    club_data = []
    ticker_data = []

    for club in clubs:
        name = club["name"]
        price = round(club["price"], 2)

        prev_rating_row = con.execute("""
            SELECT rating FROM ratings_history
            WHERE club_name = ? AND gameweek = (
                SELECT MAX(gameweek) - 1 FROM ratings_history
            )
        """, (name,)).fetchone()
        gw_played = con.execute("SELECT gw_played FROM participants WHERE name = ?"
                                ,(name,)).fetchone()["gw_played"]
        
        change_str = "Yet to play"

        if gw_played:
            if prev_rating_row and prev_rating_row["rating"]:
                prev_price = round(prev_rating_row["rating"] * 100.0, 2)
                change = round(price - prev_price, 2)
                change_pct = round((change / prev_price) * 100, 2) if prev_price else 0
                if change == 0:
                    change_str = "Yet to play"
                else:
                    change_str = f"{'+' if change >= 0 else ''}${change} ({change_pct}%)"

        ticker_data.append({
            "club": name,
            "price": price,
            "change": change_str
        })

        club_data.append({
            "name": name,
            "filename": club["filename"],
            "price": price,
            "position": name_to_position[name]
        })

    random.shuffle(ticker_data)
    
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

    holdings_rows = con.execute("""
        SELECT sh.club_name, sh.volume, (sh.volume * (p.initial_rating * 100.0)) AS value,
               rh.rating AS prev_rating, p.initial_rating AS current_rating
        FROM stock_holdings sh
        JOIN participants p ON sh.club_name = p.name AND sh.volume >= 1 
        LEFT JOIN ratings_history rh ON rh.club_name = sh.club_name AND rh.gameweek = (
            SELECT MAX(gameweek) - 1 FROM ratings_history
        )
    """).fetchall()

    holdings = []
    for row in holdings_rows:
        dollar_change = None
        percent_change = None

        if row["prev_rating"]:
            prev_price = row["prev_rating"] * 100.0
            curr_price = row["current_rating"] * 100.0
            dollar_change = round(curr_price - prev_price, 2)
            percent_change = round((dollar_change / prev_price) * 100, 2)

        holdings.append({
            "club_name": row["club_name"],
            "volume": row["volume"],
            "value": round(row["value"], 2),
            "dollar_change": dollar_change,
            "percent_change": percent_change
        })
        
    current_gw = con.execute("SELECT gameweek FROM status").fetchone()["gameweek"]
    options_rows = con.execute("""
        SELECT oh.holding_id, oh.type, oh.underlying, oh.strike, oh.expiration_gw,
               oh.cost, oh.contracts, oh.curr_premium
        FROM options_holdings oh
        WHERE oh.contracts > 0 and oh.expired = 0
    """).fetchall()

    options_holdings = []
    for row in options_rows:
        curr = row["curr_premium"]
        cost = row["cost"]
        change = round(curr - cost, 2)
        pct_change = round((change / cost) * 100, 2) if cost > 0 else 0.0
        market_value = round(curr * row["contracts"] * 100, 2)
        expiring = row["expiration_gw"] == current_gw
        total_cost = cost * 100 * row["contracts"]
        p_and_l = market_value - total_cost
        options_holdings.append({
            "club": row["underlying"],
            "strike": row["strike"],
            "type": row["type"],
            "expiry": row["expiration_gw"],
            "cost": cost,
            "curr": round(curr, 3),
            "dollar_change": change,
            "percent_change": pct_change,
            "contracts": row["contracts"],
            "market_value": market_value,
            "p&l": p_and_l,
            "expiring_this_week": expiring
        })



    context = {
        "clubs": club_data,
        "equity": equity,
        "bankroll": bankroll,
        "holdings": holdings,
        "options_holdings": options_holdings,
        "ticker_data": ticker_data
    }

    return flask.render_template("tickerscreen.html", **context)
