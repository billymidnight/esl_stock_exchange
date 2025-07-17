import math
import numpy as np
from scipy.stats import norm
import random

import random

def apply_vig_and_to_american(true_prob):
    """
    - Draw a vig percentage ~ Normal(0.025, 0.008).
    - Inflate the true probability by (1 + vig_pct).
    - If p_vig >= 1.0, resample p_vig from a Normal(0.9995, 0.0003) and clamp to < 1.
    - If p_vig == 0.0, add a tiny epsilon to avoid division by zero.
    - Convert to American odds.
    """
    # 1) Add “vig” to the input probability
    vig_pct = random.gauss(0.025, 0.008)
    p_vig = true_prob * (1 + vig_pct)

    # 2) If p_vig is ≥ 1, draw a new value near 0.9995 (and force < 1.0)
    if p_vig >= 1.0:
        p_vig = random.gauss(0.9995, 0.0003)
        # Clamp into (0, 1) just in case the gaussian wandered outside [0,1]
        if p_vig >= 1.0:
            p_vig = 0.9999
        elif p_vig <= 0.0:
            p_vig = 1e-6

    # 3) If p_vig is exactly zero or negative, bump it up by a tiny epsilon
    if p_vig <= 0.0:
        p_vig = 1e-6

    # 4) Now convert to American odds:
    if p_vig < 0.5:
        # positive moneyline: (1/p − 1)*100
        return round((1.0 / p_vig - 1.0) * 100)
    else:
        # negative moneyline: −(p/(1−p))*100
        return round(- (p_vig / (1.0 - p_vig)) * 100)

    
def round_to_half(x: float) -> float:
    """
    Round x to the nearest “*.5” value.
    Examples:
      3.98 → 3.5
      4.33 → 4.5
    """
    return round(x - 0.5) + 0.5


def calculate_match_drifts(home_rating, away_rating, home_goals, away_goals, alpha_nodraw=0.045):
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
        alpha_draw = 0.11
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

    return round(call, 5), round(put, 5), norm.cdf(d2)

home_rating = 0.45
away_rating = 5.37

scaling_factor = 3
home_advantage = 1.08

total_rating = home_rating + away_rating

a_goal_prob = home_rating / total_rating
b_goal_prob = away_rating / total_rating

a_expected_goals = a_goal_prob * scaling_factor * home_advantage
b_expected_goals = b_goal_prob * scaling_factor

all_results = []
for _ in range(1000000):
    a_goals = np.random.poisson(a_expected_goals)
    b_goals = np.random.poisson(b_expected_goals)
    all_results.append((a_goals, b_goals))

home_ml_prob = sum(1 for a, b in all_results if a > b) / len(all_results)
away_ml_prob = sum(1 for a, b in all_results if a < b) / len(all_results)
draw_prob = sum(1 for a,b in all_results if a == b) / len(all_results)

goal_count_probs = []

for i in range(15):
    goal_count_probs.append(sum(1 for a,b in all_results if a + b == i) / len(all_results))

expected_goals = sum(a + b for a,b in all_results) / len(all_results)
totals_hook = round_to_half(expected_goals)

totals_overs_probs = []
totals_unders_probs = []
for i in range(13):
    hook = i + 0.5
    over_prob = sum(goal_count_probs[j] for j in range(i + 1, len(goal_count_probs)))
    under_prob = sum(goal_count_probs[j] for j in range(0, i + 1))
    totals_overs_probs.append(over_prob)
    totals_unders_probs.append(under_prob)

home_totals_overs_probs = []
home_totals_unders_probs = []
away_totals_overs_probs = []
away_totals_unders_probs = []

hooks = [0.5, 1.5, 2.5, 3.5, 4.5]
n = len(all_results)

for hook in hooks:
    home_over = sum(1 for a, _ in all_results if a > hook) / n
    home_under = sum(1 for a, _ in all_results if a <= hook) / n
    away_over = sum(1 for _, b in all_results if b > hook) / n
    away_under = sum(1 for _, b in all_results if b <= hook) / n

    home_totals_overs_probs.append(home_over)
    home_totals_unders_probs.append(home_under)
    away_totals_overs_probs.append(away_over)
    away_totals_unders_probs.append(away_under)



btts_prob =  sum(1 for a, b in all_results if a > 0 and b > 0) / len(all_results)
no_btts_prob = 1 - btts_prob

home_minus_spreads_probs = {}
home_plus_spreads_probs = {}
away_minus_spreads_probs = {}
away_plus_spreads_probs = {}

minus_spreads = [-1.5, -2.5, -3.5, -4.5, -5.5, -6.5]
plus_spreads = [1.5, 2.5, 3.5, 4.5, 5.5, 6.5]
for spread in minus_spreads:
    home_minus = sum(1 for a, b in all_results if a + spread > b) / n
    away_minus = sum(1 for a, b in all_results if b + spread > a) / n

    home_minus_spreads_probs[spread] = home_minus
    away_minus_spreads_probs[spread] = away_minus
    away_plus_spreads_probs[-spread] = 1 - home_minus
    home_plus_spreads_probs[-spread] = 1 - away_minus

# for spread in plus_spreads:
#     home_plus = sum(1 for a, b in all_results if a + spread > b) / n
#     away_plus = sum(1 for a, b in all_results if b + spread > a) / n

#     home_plus_spreads_probs[spread] = home_plus
#     away_plus_spreads_probs[spread] = away_plus
    
dc_home_prob = home_ml_prob + draw_prob
dc_away_prob = away_ml_prob + draw_prob

# 1) Moneyline (home/away/draw)
home_ml_odds = apply_vig_and_to_american(home_ml_prob)
away_ml_odds = apply_vig_and_to_american(away_ml_prob)
draw_odds    = apply_vig_and_to_american(draw_prob)

# 2) BTTS (“both teams to score”)
btts_yes_odds   = apply_vig_and_to_american(btts_prob)
btts_no_odds    = apply_vig_and_to_american(no_btts_prob)

# 3) Totals (overall over/under lists)
home_totals_overs_odds  = [apply_vig_and_to_american(p) for p in home_totals_overs_probs]
home_totals_unders_odds = [apply_vig_and_to_american(p) for p in home_totals_unders_probs]
away_totals_overs_odds  = [apply_vig_and_to_american(p) for p in away_totals_overs_probs]
away_totals_unders_odds = [apply_vig_and_to_american(p) for p in away_totals_unders_probs]

# 4) Spread markets (dicts)
home_minus_spreads_odds = {
    spread: apply_vig_and_to_american(prob)
    for spread, prob in home_minus_spreads_probs.items()
}
away_minus_spreads_odds = {
    spread: apply_vig_and_to_american(prob)
    for spread, prob in away_minus_spreads_probs.items()
}
home_plus_spreads_odds = {
    spread: apply_vig_and_to_american(prob)
    for spread, prob in home_plus_spreads_probs.items()
}
away_plus_spreads_odds = {
    spread: apply_vig_and_to_american(prob)
    for spread, prob in away_plus_spreads_probs.items()
}

home_spreads_odds = {}
home_spreads_odds.update(home_plus_spreads_odds)
home_spreads_odds.update(home_minus_spreads_odds)

home_spreads_odds = dict(
    sorted(home_spreads_odds.items(), key=lambda kv: kv[0], reverse=True)
)

away_spreads_odds = {}
away_spreads_odds.update(away_plus_spreads_odds)
away_spreads_odds.update(away_minus_spreads_odds)

away_spreads_odds = dict(
    sorted(away_spreads_odds.items(), key=lambda kv: kv[0], reverse=True)
)



dc_home_odds = apply_vig_and_to_american(dc_home_prob)
dc_away_odds = apply_vig_and_to_american(dc_away_prob)

closest = 1000
mean_spread = -8.5
for spread, odds in home_spreads_odds.items():
    if abs(100 - abs(odds)) < closest:
        mean_spread = spread
        closest = abs(100 - abs(odds))

print(f"Mean spread is {mean_spread}")

k = 2
target_spreads = [mean_spread + i for i in range(-k, k + 1)]

mean_spread_home = mean_spread
mean_spread_away = -mean_spread_home

trimmed_home_spreads_odds = {
    s: home_spreads_odds[s]
    for s in target_spreads
    if s in home_spreads_odds
}

away_target = [-s for s in target_spreads][::-1]

trimmed_away_spreads_odds = {
    s: away_spreads_odds[s]
    for s in away_target
    if s in away_spreads_odds
}