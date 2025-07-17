import flask
from flask import render_template
from bfkt.models import get_db
from bfkt import app
from tester import round_to_half, apply_vig_and_to_american
import numpy as np

@app.route('/betzoom/', methods=['GET'])
def betzoom():
    con = get_db()

    matchday = con.execute("SELECT gameweek FROM status").fetchone()["gameweek"]
    gameno   = con.execute("SELECT gameno   FROM status").fetchone()["gameno"]

    earliest = con.execute("SELECT id FROM schedule ORDER BY id LIMIT 1").fetchone()
    fixture = None
    if earliest:
        match_id = earliest["id"] + gameno
        fixture  = con.execute(
            "SELECT home, away FROM schedule WHERE id = ?", (match_id,)
        ).fetchone()

    # prepare some placeholders properly
    ml_home_odds = ml_away_odds = ml_draw_odds = None
    btts_odds = {}
    dc_odds = {}
    featured_total = None
    featured_total_over = featured_total_under = None
    featured_spread = None
    feat_spread_home = feat_spread_away = None
    all_home_totals = {}
    all_away_totals = {}
    all_home_spreads = {}
    all_away_spreads = {}

    if fixture:
        homenext = fixture["home"]
        awaynext = fixture["away"]

        home_rating = con.execute(
            "SELECT initial_rating FROM participants WHERE name = ?", (homenext,)
        ).fetchone()["initial_rating"]
        away_rating = con.execute(
            "SELECT initial_rating FROM participants WHERE name = ?", (awaynext,)
        ).fetchone()["initial_rating"]

        home_pic = con.execute("SELECT filename FROM participants WHERE name = ?", (homenext,)).fetchone()["filename"]
        away_pic = con.execute("SELECT filename FROM participants WHERE name = ?", (awaynext,)).fetchone()["filename"]

        scaling_factor  = 3
        home_advantage  = 1.08
        total_rating    = home_rating + away_rating
        a_goal_prob     = home_rating / total_rating
        b_goal_prob     = away_rating / total_rating
        a_expected_goals = a_goal_prob * scaling_factor * home_advantage
        b_expected_goals = b_goal_prob * scaling_factor

        N = 100_000
        all_results = [
            (np.random.poisson(a_expected_goals), np.random.poisson(b_expected_goals))
            for _ in range(N)
        ]

        home_ml_prob = sum(1 for a, b in all_results if a > b) / N
        away_ml_prob = sum(1 for a, b in all_results if a < b) / N
        draw_prob    = sum(1 for a, b in all_results if a == b) / N

        ml_home_odds = apply_vig_and_to_american(home_ml_prob)
        ml_away_odds = apply_vig_and_to_american(away_ml_prob)
        ml_draw_odds = apply_vig_and_to_american(draw_prob)

        btts_yes_prob = sum(1 for a, b in all_results if a > 0 and b > 0) / N
        btts_no_prob  = 1 - btts_yes_prob
        btts_odds["yes"] = apply_vig_and_to_american(btts_yes_prob)
        btts_odds["no"]  = apply_vig_and_to_american(btts_no_prob)

        # Totals (0.5–12.5)
        goal_count_probs = [
            sum(1 for a, b in all_results if a + b == i) / N
            for i in range(15)
        ]
        for i in range(13):
            hook = i + 0.5
            over_prob  = sum(goal_count_probs[j] for j in range(i + 1, len(goal_count_probs)))
            under_prob = 1 - over_prob
            oid = apply_vig_and_to_american(over_prob)
            uid = apply_vig_and_to_american(under_prob)
            all_home_totals[hook] = {"over": oid, "under": uid}
            all_away_totals[hook] = {"over": oid, "under": uid}

        # spreads markets
        home_minus_spreads_probs = {}
        away_minus_spreads_probs = {}
        home_plus_spreads_probs  = {}
        away_plus_spreads_probs  = {}

        minus_spreads = [-1.5, -2.5, -3.5, -4.5, -5.5, -6.5]
        for s in minus_spreads:
            home_minus = sum(1 for a, b in all_results if a + s > b) / N
            away_minus = sum(1 for a, b in all_results if b + s > a) / N

            home_minus_spreads_probs[s] = home_minus
            away_minus_spreads_probs[s] = away_minus

            home_plus_spreads_probs[-s] = 1 - away_minus
            away_plus_spreads_probs[-s] = 1 - home_minus

        all_home_spreads = {}
        all_away_spreads = {}
        for s, prob in home_minus_spreads_probs.items():
            all_home_spreads[s] = apply_vig_and_to_american(prob)
        for s, prob in home_plus_spreads_probs.items():
            all_home_spreads[s] = apply_vig_and_to_american(prob)
        for s, prob in away_minus_spreads_probs.items():
            all_away_spreads[s] = apply_vig_and_to_american(prob)
        for s, prob in away_plus_spreads_probs.items():
            all_away_spreads[s] = apply_vig_and_to_american(prob)

        closest = 1000
        mean_spread = -8.5
        for spread, odds in all_home_spreads.items():
            if abs(100 - abs(odds)) < closest:
                mean_spread = spread
                closest = abs(100 - abs(odds))

        k = 2
        target_spreads = [mean_spread + i for i in range(-k, k + 1)]

        trimmed_home_spreads_odds = {
            s: all_home_spreads[s] for s in target_spreads if s in all_home_spreads
        }
        away_target = [-s for s in target_spreads][::-1]
        trimmed_away_spreads_odds = {
            s: all_away_spreads[s] for s in away_target if s in all_away_spreads
        }

        featured_spread = mean_spread
        feat_spread_home = trimmed_home_spreads_odds.get(mean_spread)
        feat_spread_away = trimmed_away_spreads_odds.get(-mean_spread)

        # double chance
        dc_home_prob = home_ml_prob + draw_prob
        dc_away_prob = away_ml_prob + draw_prob
        dc_odds["home_or_draw"] = apply_vig_and_to_american(dc_home_prob)
        dc_odds["away_or_draw"] = apply_vig_and_to_american(dc_away_prob)

        # Featured total is simply the rounded to half of expected
        expected_goals = sum(a + b for a, b in all_results) / N
        featured_total = round_to_half(expected_goals)
        over_p = sum(goal_count_probs[j] for j in range(int(featured_total + 0.5), len(goal_count_probs)))
        under_p = 1 - over_p
        featured_total_over = apply_vig_and_to_american(over_p)
        featured_total_under = apply_vig_and_to_american(under_p)

    print("The home pic is ", home_pic , " and the way pic is ", away_pic)
    context = {
        "bankroll": round(con.execute("SELECT bankroll FROM equity").fetchone()["bankroll"], 2),
        "matchday": matchday,
        "gameno": gameno,
        "fixture": fixture if fixture else {},

        "home_pic": home_pic,
        "away_pic": away_pic,

        # Moneyline
        "ml_home": ml_home_odds,
        "ml_draw": ml_draw_odds,
        "ml_away": ml_away_odds,

        # Featured Total
        "featured_total": featured_total,
        "featured_total_over": featured_total_over,
        "featured_total_under": featured_total_under,

        # Featured Spread
        "featured_spread": featured_spread,
        "feat_spread_home": feat_spread_home,
        "feat_spread_away": feat_spread_away,

        # Double Chance
        "dc_home_or_draw": dc_odds.get("home_or_draw"),
        "dc_away_or_draw": dc_odds.get("away_or_draw"),

        # BTTS
        "btts_yes": btts_odds.get("yes"),
        "btts_no": btts_odds.get("no"),

        # All totals
        "all_home_totals": all_home_totals,
        "all_away_totals": all_away_totals,

        # All (trimmed) spreads
        "all_home_spreads": trimmed_home_spreads_odds,
        "all_away_spreads": trimmed_away_spreads_odds,
    }

    return render_template("betzoom.html", **context)
