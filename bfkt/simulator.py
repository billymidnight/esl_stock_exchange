import os
import flask
import random
import numpy as np
import random
from scipy.stats import norm
import math
from bfkt import app  # Import the Flask app from the app module
from bfkt.models import get_db


def simulate_match(player_a_rating, player_b_rating, scaling_factor=3, home_advantage=1.08):
    total_rating = player_a_rating + player_b_rating
    
    a_goal_prob = player_a_rating / total_rating
    b_goal_prob = player_b_rating / total_rating
    
    a_expected_goals = a_goal_prob * scaling_factor * home_advantage
    b_expected_goals = b_goal_prob * scaling_factor
    
    a_goals = np.random.poisson(a_expected_goals)
    b_goals = np.random.poisson(b_expected_goals)
    
    if np.random.rand() < 0.1: 
        if np.random.rand() < 0.5:
            a_goals += np.random.randint(1, 3)
        else:
            b_goals += np.random.randint(1, 3) 

    if np.random.rand() < 0.05:
        b_goals = 0

    return a_goals, b_goals

def calculate_match_drifts(home_rating, away_rating, home_goals, away_goals, alpha_nodraw=0.055):
    homefav = False

    if home_rating >= away_rating:
        fav_rating = home_rating
        fav_goals = home_goals
        udog_rating = away_rating
        udog_goals = away_goals
        homefav = True
    else:
        fav_rating = away_rating
        fav_goals = away_goals
        udog_rating = home_rating
        udog_goals = home_goals
    

    gd = abs(fav_goals - udog_goals)

    if fav_goals == udog_goals:
        alpha_draw = 0.15
        base_drift = 0.0
        log_term = math.log(fav_rating / udog_rating)
        drift_udog = base_drift + alpha_draw * log_term
        drift_fav = -drift_udog
         
    elif fav_goals > udog_goals:
        base_drift = 0.065
        log_term = math.log(fav_rating / udog_rating)
        if log_term <= 1:
            exponent = 1 + 0.5 * (gd - 1)
        else:
            exponent = 1- 0.5 * (gd - 1)
        drift_fav = base_drift - alpha_nodraw * (log_term ** exponent)
        drift_udog = -drift_fav

    else:
        base_drift = 0.065
        log_term = math.log(fav_rating / udog_rating)
        exponent = 1 - 0.3 * (gd - 1)  
        drift_udog = base_drift + alpha_nodraw * (log_term ** exponent)
        drift_fav = -drift_udog

    if homefav:
        return drift_fav, drift_udog
    else:
        return drift_udog, drift_fav    

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

def update_options():
    con = get_db()

    current_gw = con.execute("SELECT gameweek FROM status").fetchone()["gameweek"]

    rows = con.execute("""
        SELECT oh.holding_id, oh.type, oh.strike, oh.expiration_gw,
               p.initial_rating, p.volatility, p.drift, p.gw_played
        FROM options_holdings oh
        JOIN participants p ON oh.underlying = p.name 
        WHERE oh.expired = FALSE
    """).fetchall()

    for row in rows:
        S = round(row["initial_rating"] * 100.0, 2)
        K = row["strike"]
        vol = row["volatility"]
        drift = row["drift"]
        gameno = con.execute("SELECT gameno FROM status").fetchone()["gameno"]
        games_left_this_week = 10 - gameno
        games_toexpiry = games_left_this_week + 10 * (row["expiration_gw"]-current_gw)
        T = (row["expiration_gw"] - current_gw) + (1 if not row["gw_played"] else 0) + (games_toexpiry / 40.0)
        T = max(0, T)

        print("checking the ", row["holding_id"], row["type"], "option now")
        print("expiration gw:", row["expiration_gw"], "| T is:", T, "| K:", K, "| vol:", vol)

        call, put = black_scholes(S, K, T, vol, r = drift * 0.2)
        curr_premium = call if row["type"] == "call" else put
        curr_premium = max(curr_premium, 0.01)

        con.execute("""
            UPDATE options_holdings
            SET curr_premium = ?
            WHERE holding_id = ?
        """, (curr_premium, row["holding_id"]))

    con.commit()
    print("✅ All options updated with new premiums.")

def settle_expirations(current_gw):
    con = get_db()

    rows = con.execute("""
        SELECT * FROM options_holdings
        WHERE expiration_gw = ? AND expired = 0
    """, (current_gw,)).fetchall()

    for row in rows:
        club = row["underlying"]
        contracts = row["contracts"]
        strike = row["strike"]
        premium_paid = row["cost"]
        option_type = row["type"]
        holding_id = row["holding_id"]

        price_row = con.execute("SELECT initial_rating FROM participants WHERE name = ?", (club,)).fetchone()
        underlying_price = round(price_row["initial_rating"] * 100.0, 2)

        if option_type == "call":
            intrinsic = max(underlying_price - strike, 0)
        else:  # put
            intrinsic = max(strike - underlying_price, 0)

        realized_return = round((intrinsic - premium_paid) * 100 * contracts, 2)

        con.execute("""
            UPDATE options_holdings
            SET expired = 1,
                curr_premium = 0,
                held_till_expiry = 1,
                expired_underlying = ?,
                itm_otm = ?
            WHERE holding_id = ?
        """, (underlying_price, "itm" if intrinsic > 0 else "otm", holding_id))

        if intrinsic > 0:
            payout = intrinsic * 100 * contracts
            con.execute("UPDATE equity SET bankroll = bankroll + ?", (payout,))



def settle_obets(current_gw):
    """
    Settle all digital Over/Under bets expiring in the given gameweek.
    For each:
      - Compute final underlying price = participants.initial_rating * 100
      - Determine win/loss based on obet_type vs. strike
      - Update options_bets.obet_result and underlying_finished
      - If won, credit options_bets.obet_potential_payout to the sports-bankroll table
    """
    con = get_db()
    rows = con.execute("""
        SELECT obet_id, obet_underlying, obet_type, obet_strike, obet_potential_payout
        FROM options_bets
        WHERE obet_expiry = ? AND result IS NULL
    """, (current_gw,)).fetchall()

    for row in rows:
        obet_id   = row["obet_id"]
        club      = row["obet_underlying"]
        bet_type  = row["obet_type"]    
        strike    = row["obet_strike"]
        payout    = row["obet_potential_payout"]

        price_row = con.execute(
            "SELECT initial_rating FROM participants WHERE name = ?",
            (club,)
        ).fetchone()
        final_price = round(price_row["initial_rating"] * 100.0, 2)

        if (bet_type == "Over"  and final_price > strike) or \
           (bet_type == "Under" and final_price < strike):
            result = "Won"
        else:
            result = "Lost"

        con.execute("""
            UPDATE options_bets
               SET result = ?,
                   underlying_finished = ?
             WHERE obet_id = ?
        """, (result, final_price, obet_id))

        if result == "Won":
            con.execute("""
                UPDATE equity
                   SET bankroll = bankroll + ?
            """, (payout,))

    con.commit()

@app.route('/simulator/', methods=['GET', 'POST'])
def results_generator():

    con = get_db()
    operation = flask.request.form.get("operation")

    if operation == "simulate":
        id = flask.request.form.get("idoffset")
        print("id for simulation is", id)
        match_data = con.execute(
            """
            SELECT s.home, s.away, p1.initial_rating as home_rating, p2.initial_rating as away_rating
            FROM schedule s
            JOIN participants p1 ON s.home = p1.name
            JOIN participants p2 ON s.away = p2.name
            WHERE s.id = ?
            """,
            (id,)
        ).fetchone()

        if not match_data:
            return "Match not found", 404

        
        home, away, homerating, awayrating = match_data
        home = match_data["home"]
        away = match_data["away"]
        homerating = match_data["home_rating"]
        awayrating = match_data["away_rating"]
        homegoals, awaygoals = simulate_match(float(homerating), float(awayrating))

        con.execute(
            "INSERT INTO matches (home, away, home_goals, away_goals) VALUES (?, ?, ?, ?)",
            (home, away, homegoals, awaygoals)
        )
        gw = con.execute("SELECT gameweek FROM status").fetchone()["gameweek"]
        offset = con.execute("SELECT gameno FROM status").fetchone()["gameno"]
        matchid = (gw - 1) * 10 + offset + 1
        print(f"match id from simulator is {matchid}")
        print(f"match id is {matchid}")
        currbets = con.execute("SELECT * FROM ml_bets "
                               "WHERE gameid = ?",(matchid,)).fetchall()
        
        for bet in currbets:
            winlose = "lose"
            stake = bet["stake"]
            betid = bet["betid"]
            horse = bet["horse"]
            if horse == "draw":
                if homegoals == awaygoals:
                    winlose = "win"
            elif horse == "home":
                if homegoals > awaygoals:
                    winlose = "win"
            elif horse == "away":
                if homegoals < awaygoals:
                    winlose = "win" 
            payout = bet["payout"]
            if winlose == "win":
                con.execute("UPDATE bankroll "
                    "SET curr_bankroll = curr_bankroll + ?", (payout + stake,))
            con.execute("UPDATE ml_bets "
                    "SET status = ?, actualhome = ?, actualaway = ?, winlose = ? "
                    "WHERE betid = ?",
                    ("past", homegoals, awaygoals, winlose, betid)) 

        standings_data = con.execute(
            """
            SELECT name, matches_played, draws, wins, losses, goals_for, goals_against, points, goal_difference 
            FROM standings WHERE name IN (?, ?)
            """,
            (home, away)
        ).fetchall()

        standings = {row["name"]: row for row in standings_data}
        home_standing = standings[home]
        away_standing = standings[away]

        update_values = {}
        if homegoals == awaygoals:
            update_values = {
                home: {"matches_played": 1, "draws": 1, "goals_for": homegoals, "goals_against": awaygoals, "points": 1, "goal_difference": homegoals - awaygoals},
                away: {"matches_played": 1, "draws": 1, "goals_for": awaygoals, "goals_against": homegoals, "points": 1, "goal_difference": awaygoals - homegoals}
            }
        elif homegoals > awaygoals:
            update_values = {
                home: {"matches_played": 1, "wins": 1, "goals_for": homegoals, "goals_against": awaygoals, "points": 3, "goal_difference": homegoals - awaygoals},
                away: {"matches_played": 1, "losses": 1, "goals_for": awaygoals, "goals_against": homegoals, "goal_difference": awaygoals - homegoals}
            }
        else:
            update_values = {
                home: {"matches_played": 1, "losses": 1, "goals_for": homegoals, "goals_against": awaygoals, "goal_difference": homegoals - awaygoals},
                away: {"matches_played": 1, "wins": 1, "goals_for": awaygoals, "goals_against": homegoals, "points": 3, "goal_difference": awaygoals - homegoals}
            }

        for team, values in update_values.items():
            con.execute(
                """
                UPDATE standings
                SET matches_played = matches_played + ?,
                    wins = wins + ?,
                    draws = draws + ?,
                    losses = losses + ?,
                    goals_for = goals_for + ?,
                    goals_against = goals_against + ?,
                    points = points + ?,
                    goal_difference = goal_difference + ?
                WHERE name = ?
                """,
                (values["matches_played"], values.get("wins", 0), values.get("draws", 0),
                 values.get("losses", 0), values["goals_for"], values["goals_against"],
                 values.get("points", 0), values["goal_difference"], team)
            )


        for club in [home, away]:
            current_points = con.execute("SELECT points FROM standings WHERE name = ?", (club,)).fetchone()["points"]
            con.execute(
                "INSERT INTO points_history (name, gameweek, points) VALUES (?, ?, ?)",
                (club, gw, current_points)
            )

        ## Update ratings of home and away player here
        home_data = con.execute(
            "SELECT drift, volatility FROM participants WHERE name = ?", (home,)
        ).fetchone()
        away_data = con.execute(
            "SELECT drift, volatility FROM participants WHERE name = ?", (away,)
        ).fetchone()

        mu_home_char, sigma_home = home_data["drift"], home_data["volatility"]
        mu_away_char, sigma_away = away_data["drift"], away_data["volatility"]

        

        delta_t = 1.1


        mu_home, mu_away = calculate_match_drifts(
            homerating, awayrating, homegoals, awaygoals
        )
        print(f"the home mu is {mu_home} and the away my is {mu_away}")
        weight_sample = min(max(random.gauss(69, 6.8), 0), 100)
        print(f"weight sample was {weight_sample}")
        mu_home_final = mu_home if random.uniform(0, 100) <= weight_sample else mu_home_char
        print("mu_home_final was ", mu_home_final)
        mu_away_final = mu_away if random.uniform(0, 100) <= weight_sample else mu_away_char
        print("mu_away_final was ", mu_away_final)

        Z_home = random.gauss(0, math.sqrt(delta_t))
        Z_away = random.gauss(0, math.sqrt(delta_t))

        print("zhome was ", Z_home)
        print("zaway was ", Z_away)

        new_home_rating = homerating * math.exp(
            (mu_home_final - 0.5 * sigma_home**2) * delta_t + sigma_home * Z_home
        )

        new_away_rating = awayrating * math.exp(
            (mu_away_final - 0.5 * sigma_away**2) * delta_t + sigma_away * Z_away
        )

        con.execute(
            "UPDATE participants SET initial_rating = ? WHERE name = ?",
            (new_home_rating, home)
        )
        con.execute(
            "UPDATE participants SET initial_rating = ? WHERE name = ?",
            (new_away_rating, away)
        )

        con.execute("INSERT INTO ratings_history (club_name, gameweek, rating) VALUES (?, ?, ?)", (home, gw, new_home_rating))
        con.execute("INSERT INTO ratings_history (club_name, gameweek, rating) VALUES (?, ?, ?)", (away, gw, new_away_rating))


        all_clubs = con.execute("SELECT name, drift, volatility, initial_rating FROM participants").fetchall()

        delta_t_small = delta_t / 40.0 

        for row in all_clubs:
            name, mu, sigma, rating = row["name"], row["drift"], row["volatility"], row["initial_rating"]

            if name == home or name == away:
                continue

            Z = random.gauss(0, math.sqrt(delta_t_small))
            new_rating = rating * math.exp((mu - 0.5 * sigma**2) * delta_t_small + sigma * Z)

            con.execute(
                "UPDATE participants SET initial_rating = ? WHERE name = ?",
                (new_rating, name)
            )

        con.execute("""
            UPDATE participants
            SET gw_played = 1
            WHERE name IN (?, ?)
        """, (home, away))
            
        update_options()

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

        con.execute("INSERT INTO equity_history (gameweek, gameno, equity_value) VALUES (?,?,?)", (gw, offset, equity))
        


        # gmae no and gameweek officially incremented, nothing can be done after this
        con.execute("UPDATE status SET gameno = gameno + 1")
        gameno = con.execute("SELECT gameno FROM status").fetchone()["gameno"]
        gameweek = con.execute("SELECT gameweek FROM status").fetchone()["gameweek"]
        if gameno == 10:
            con.execute("UPDATE participants SET gw_played = 0")
            settle_obets(gameweek) 
            settle_expirations(gameweek)
            con.execute("UPDATE status SET gameno = 0, gameweek = gameweek + 1")
        #con.commit()
        
        # if gameweek == 178:
        #     winner = con.execute("SELECT name FROM standings "
        #                          "ORDER BY points DESC LIMIT 1").fetchone()["name"]
        #     futures_bets = con.execute("SELECT * FROM futures_bets ").fetchall()

        #     for bet in futures_bets:
        #         winlose = "lose"
        #         betid = bet["betid"]
        #         if bet["horse"] == winner:
        #             winlose = "win"
        #             curr_bankroll = con.execute("SELECT curr_bankroll FROM bankroll").fetchone()["curr_bankroll"]
        #             new_bankroll = curr_bankroll + bet["payout"] + bet["stake"]
        #             con.execute("UPDATE bankroll SET curr_bankroll = ?", (new_bankroll,))
        #         bet["actualchamp"] = winner    
        #         con.execute("UPDATE futures_bets SET winlose = ?, actualchamp = ? WHERE betid = ?", (winlose, winner, betid,))

        #         winner_img = con.execute("SELECT filename FROM participants WHERE name = ?", (winner,)).fetchone()["filename"]
        #         cur = con.execute(
        #             "SELECT * FROM standings "
        #             "ORDER BY points DESC, goal_difference DESC, goals_for DESC, name ASC"
        #         )
        #         standings = cur.fetchall()
        #         for index, row in enumerate(standings, start=1):
        #             row["position"] = index

        #         for player in standings:
        #             name = player["name"]
        #             cur = con.execute("SELECT filename FROM participants WHERE name = ?", (name,))
        #             img_name = cur.fetchone()["filename"]
        #             player["img_name"] = img_name
        #         year = con.execute("SELECT year FROM year").fetchone()["year"]
                
        #         context = {
        #             "winner": winner,
        #             "winner_img": winner_img,
        #             "year": year,
        #             "standings": standings
        #         }
        #         return flask.render_template("leagueend.html", **context)


    # Fetch matches with images
    cur = con.execute(
        """
        SELECT m.*, ph.filename as homepic, pa.filename as awaypic 
        FROM matches m
        JOIN participants ph ON m.home = ph.name
        JOIN participants pa ON m.away = pa.name
        ORDER BY m.match_id DESC
        """
    )
    matches = cur.fetchall()

    # Group matches by gameweek
    grouped_matches = []
    current_gw = None
    current_group = []

    for match in matches:
        match["gameweek"] = (match["match_id"] - 1) // 10 + 1
        if current_gw is None:
            current_gw = match["gameweek"]

        if match["gameweek"] != current_gw:
            grouped_matches.append(current_group)
            current_group = []
            current_gw = match["gameweek"]

        current_group.append(match)

    if current_group:
        grouped_matches.append(current_group)

    context = {
        "grouped_matches": grouped_matches,
        "matches": matches  
    }

    return flask.render_template("fixtures.html", **context)



@app.route('/gameweek_sim/', methods=['GET', 'POST'])
def gameweek_sim():

    con = get_db()
    operation = flask.request.form.get("operation")
    id = int(flask.request.form.get("idoffset"))

    while True:
        
        print("id for simulation is", id)
        match_data = con.execute(
            """
            SELECT s.home, s.away, p1.initial_rating as home_rating, p2.initial_rating as away_rating
            FROM schedule s
            JOIN participants p1 ON s.home = p1.name
            JOIN participants p2 ON s.away = p2.name
            WHERE s.id = ?
            """,
            (id,)
        ).fetchone()

        if not match_data:
            return "Match not found", 404

        
        home, away, homerating, awayrating = match_data
        home = match_data["home"]
        away = match_data["away"]
        homerating = match_data["home_rating"]
        awayrating = match_data["away_rating"]
        homegoals, awaygoals = simulate_match(float(homerating), float(awayrating))

        con.execute(
            "INSERT INTO matches (home, away, home_goals, away_goals) VALUES (?, ?, ?, ?)",
            (home, away, homegoals, awaygoals)
        )
        gw = con.execute("SELECT gameweek FROM status").fetchone()["gameweek"]
        offset = con.execute("SELECT gameno FROM status").fetchone()["gameno"]
        matchid = (gw - 1) * 10 + offset + 1
        print(f"match id from simulator is {matchid}")
        print(f"match id is {matchid}")
        currbets = con.execute("SELECT * FROM ml_bets "
                               "WHERE gameid = ?",(matchid,)).fetchall()
        
        for bet in currbets:
            winlose = "lose"
            stake = bet["stake"]
            betid = bet["betid"]
            horse = bet["horse"]
            if horse == "draw":
                if homegoals == awaygoals:
                    winlose = "win"
            elif horse == "home":
                if homegoals > awaygoals:
                    winlose = "win"
            elif horse == "away":
                if homegoals < awaygoals:
                    winlose = "win" 
            payout = bet["payout"]
            if winlose == "win":
                con.execute("UPDATE bankroll "
                    "SET curr_bankroll = curr_bankroll + ?", (payout + stake,))
            con.execute("UPDATE ml_bets "
                    "SET status = ?, actualhome = ?, actualaway = ?, winlose = ? "
                    "WHERE betid = ?",
                    ("past", homegoals, awaygoals, winlose, betid)) 

        standings_data = con.execute(
            """
            SELECT name, matches_played, draws, wins, losses, goals_for, goals_against, points, goal_difference 
            FROM standings WHERE name IN (?, ?)
            """,
            (home, away)
        ).fetchall()

        standings = {row["name"]: row for row in standings_data}
        home_standing = standings[home]
        away_standing = standings[away]

        update_values = {}
        if homegoals == awaygoals:
            update_values = {
                home: {"matches_played": 1, "draws": 1, "goals_for": homegoals, "goals_against": awaygoals, "points": 1, "goal_difference": homegoals - awaygoals},
                away: {"matches_played": 1, "draws": 1, "goals_for": awaygoals, "goals_against": homegoals, "points": 1, "goal_difference": awaygoals - homegoals}
            }
        elif homegoals > awaygoals:
            update_values = {
                home: {"matches_played": 1, "wins": 1, "goals_for": homegoals, "goals_against": awaygoals, "points": 3, "goal_difference": homegoals - awaygoals},
                away: {"matches_played": 1, "losses": 1, "goals_for": awaygoals, "goals_against": homegoals, "goal_difference": awaygoals - homegoals}
            }
        else:
            update_values = {
                home: {"matches_played": 1, "losses": 1, "goals_for": homegoals, "goals_against": awaygoals, "goal_difference": homegoals - awaygoals},
                away: {"matches_played": 1, "wins": 1, "goals_for": awaygoals, "goals_against": homegoals, "points": 3, "goal_difference": awaygoals - homegoals}
            }

        for team, values in update_values.items():
            con.execute(
                """
                UPDATE standings
                SET matches_played = matches_played + ?,
                    wins = wins + ?,
                    draws = draws + ?,
                    losses = losses + ?,
                    goals_for = goals_for + ?,
                    goals_against = goals_against + ?,
                    points = points + ?,
                    goal_difference = goal_difference + ?
                WHERE name = ?
                """,
                (values["matches_played"], values.get("wins", 0), values.get("draws", 0),
                 values.get("losses", 0), values["goals_for"], values["goals_against"],
                 values.get("points", 0), values["goal_difference"], team)
            )


        for club in [home, away]:
            current_points = con.execute("SELECT points FROM standings WHERE name = ?", (club,)).fetchone()["points"]
            con.execute(
                "INSERT INTO points_history (name, gameweek, points) VALUES (?, ?, ?)",
                (club, gw, current_points)
            )

        home_data = con.execute(
            "SELECT drift, volatility FROM participants WHERE name = ?", (home,)
        ).fetchone()
        away_data = con.execute(
            "SELECT drift, volatility FROM participants WHERE name = ?", (away,)
        ).fetchone()

        mu_home_char, sigma_home = home_data["drift"], home_data["volatility"]
        mu_away_char, sigma_away = away_data["drift"], away_data["volatility"]

        

        delta_t = 1.1


        mu_home, mu_away = calculate_match_drifts(
            homerating, awayrating, homegoals, awaygoals
        )
        print(f"the home mu is {mu_home} and the away my is {mu_away}")
        weight_sample = min(max(random.gauss(69, 6.8), 0), 100)
        print(f"weight sample was {weight_sample}")
        mu_home_final = mu_home if random.uniform(0, 100) <= weight_sample else mu_home_char
        print("mu_home_final was ", mu_home_final)
        mu_away_final = mu_away if random.uniform(0, 100) <= weight_sample else mu_away_char
        print("mu_away_final was ", mu_away_final)

        Z_home = random.gauss(0, math.sqrt(delta_t))
        Z_away = random.gauss(0, math.sqrt(delta_t))

        print("zhome was ", Z_home)
        print("zaway was ", Z_away)

        new_home_rating = homerating * math.exp(
            (mu_home_final - 0.5 * sigma_home**2) * delta_t + sigma_home * Z_home
        )

        new_away_rating = awayrating * math.exp(
            (mu_away_final - 0.5 * sigma_away**2) * delta_t + sigma_away * Z_away
        )

        con.execute(
            "UPDATE participants SET initial_rating = ? WHERE name = ?",
            (new_home_rating, home)
        )
        con.execute(
            "UPDATE participants SET initial_rating = ? WHERE name = ?",
            (new_away_rating, away)
        )

        con.execute("INSERT INTO ratings_history (club_name, gameweek, rating) VALUES (?, ?, ?)", (home, gw, new_home_rating))
        con.execute("INSERT INTO ratings_history (club_name, gameweek, rating) VALUES (?, ?, ?)", (away, gw, new_away_rating))


        all_clubs = con.execute("SELECT name, drift, volatility, initial_rating FROM participants").fetchall()

        delta_t_small = delta_t / 40.0 

        for row in all_clubs:
            name, mu, sigma, rating = row["name"], row["drift"], row["volatility"], row["initial_rating"]

            if name == home or name == away:
                continue

            Z = random.gauss(0, math.sqrt(delta_t_small))
            new_rating = rating * math.exp((mu - 0.5 * sigma**2) * delta_t_small + sigma * Z)

            con.execute(
                "UPDATE participants SET initial_rating = ? WHERE name = ?",
                (new_rating, name)
            )

        con.execute("""
            UPDATE participants
            SET gw_played = 1
            WHERE name IN (?, ?)
        """, (home, away))
            
        update_options()

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

        con.execute("INSERT INTO equity_history (gameweek, gameno, equity_value) VALUES (?,?,?)", (gw, offset, equity))
        


        # gmae no and gameweek officially incremented, nothing can be done after this
        con.execute("UPDATE status SET gameno = gameno + 1")
        gameno = con.execute("SELECT gameno FROM status").fetchone()["gameno"]
        gameweek = con.execute("SELECT gameweek FROM status").fetchone()["gameweek"]
        if gameno == 10:
            con.execute("UPDATE participants SET gw_played = 0")
            settle_expirations(gameweek)
            settle_obets(gameweek) 
            con.execute("UPDATE status SET gameno = 0, gameweek = gameweek + 1")
        #con.commit()

        newgameno = con.execute("SELECT gameno FROM status").fetchone()["gameno"]
        if newgameno == 0:
            break
        else:
            id += 1
        

    # Fetch matches with images
    cur = con.execute(
        """
        SELECT m.*, ph.filename as homepic, pa.filename as awaypic 
        FROM matches m
        JOIN participants ph ON m.home = ph.name
        JOIN participants pa ON m.away = pa.name
        ORDER BY m.match_id DESC
        """
    )
    matches = cur.fetchall()

    # Group matches by gameweek
    grouped_matches = []
    current_gw = None
    current_group = []

    for match in matches:
        match["gameweek"] = (match["match_id"] - 1) // 10 + 1
        if current_gw is None:
            current_gw = match["gameweek"]

        if match["gameweek"] != current_gw:
            grouped_matches.append(current_group)
            current_group = []
            current_gw = match["gameweek"]

        current_group.append(match)

    if current_group:
        grouped_matches.append(current_group)

    context = {
        "grouped_matches": grouped_matches,
        "matches": matches  # <— THIS RIGHT HERE
    }

    return flask.render_template("fixtures.html", **context)