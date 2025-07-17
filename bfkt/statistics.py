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

from flask import render_template
from collections import defaultdict

def extract_top_streaks(streaks, target_results, name_to_filename):
    top = defaultdict(list)
    for club, seq in streaks.items():
        streak_start = None
        curr = 0
        for i, result in enumerate(seq):
            if result in target_results:
                if streak_start is None:
                    streak_start = i
                curr += 1
            else:
                if curr > 0:
                    top[curr].append({
                        "club": club,
                        "filename": name_to_filename.get(club),
                        "from_gw": streak_start + 1,
                        "to_gw": streak_start + curr
                    })
                curr = 0
                streak_start = None
        if curr > 0:
            top[curr].append({
                "club": club,
                "filename": name_to_filename.get(club),
                "from_gw": streak_start + 1,
                "to_gw": streak_start + curr
            })

    if not top:
        return []

    top_lengths = sorted(top.keys(), reverse=True)
    result = []
    added = 0
    for length in top_lengths:
        if added < 3 or len(result[-1]["clubs"]) == len(top[length]):
            result.append({"length": length, "clubs": top[length]})
            added += 1
        else:
            break
    return result

@app.route("/statistics")
def statistics():
    con = get_db()
    matches = con.execute("SELECT * FROM matches ORDER BY match_id ASC").fetchall()
    name_to_filename = {
        row["name"]: row["filename"]
        for row in con.execute("SELECT name, filename FROM participants").fetchall()
    }

    wins, draws, losses = defaultdict(int), defaultdict(int), defaultdict(int)
    clean_sheets = defaultdict(int)
    streaks = defaultdict(list)
    h2h_counts = defaultdict(int)
    biggest_wins = []
    biggest_win_margin = 0

    for match in matches:
        h, a, hg, ag = match["home"], match["away"], match["home_goals"], match["away_goals"]

        if hg > ag:
            wins[h] += 1
            losses[a] += 1
            streaks[h].append("W")
            streaks[a].append("L")
        elif hg < ag:
            wins[a] += 1
            losses[h] += 1
            streaks[a].append("W")
            streaks[h].append("L")
        else:
            draws[h] += 1
            draws[a] += 1
            streaks[h].append("D")
            streaks[a].append("D")

        if ag == 0:
            clean_sheets[h] += 1
        if hg == 0:
            clean_sheets[a] += 1

        margin = abs(hg - ag)
        if hg != ag:
            if margin > biggest_win_margin:
                biggest_win_margin = margin
                biggest_wins = [{
                    "home": h, "away": a, "score": f"{hg}-{ag}",
                    "match_id": match["match_id"],
                    "gameweek": (match["match_id"] + 9) // 10
                }]
            elif margin == biggest_win_margin:
                biggest_wins.append({
                    "home": h, "away": a, "score": f"{hg}-{ag}",
                    "match_id": match["match_id"],
                    "gameweek": (match["match_id"] + 9) // 10
                })

        key = tuple(sorted([h, a]))
        h2h_counts[key] += 1

    def top_clubs(d):
        if not d: return 0, []
        max_val = max(d.values())
        return max_val, [{"club": k, "filename": name_to_filename[k]} for k, v in d.items() if v == max_val]

    most_cs = top_clubs(clean_sheets)
    least_cs_val = min(clean_sheets.values(), default=0)
    least_cs = [c for c, v in clean_sheets.items() if v == least_cs_val]
    least_cs_data = [{"club": c, "filename": name_to_filename[c]} for c in least_cs]

    sorted_h2h = sorted(h2h_counts.items(), key=lambda x: -x[1])
    top3_meetings = []
    prev_count, rank = None, 0
    for pair, count in sorted_h2h:
        if rank < 3 or count == prev_count:
            top3_meetings.append({
                "clubs": list(pair),
                "count": count,
                "filenames": [name_to_filename[pair[0]], name_to_filename[pair[1]]]
            })
            if count != prev_count:
                rank += 1
                prev_count = count

    print(streaks["Ajax AFC"])
    context = {
        "most_wins": top_clubs(wins),
        "most_draws": top_clubs(draws),
        "most_losses": top_clubs(losses),
        "longest_win_streaks": extract_top_streaks(streaks, ["W"], name_to_filename),
        "longest_loss_streaks": extract_top_streaks(streaks, ["L"], name_to_filename),
        "longest_unbeaten_streaks": extract_top_streaks(streaks, ["W", "D"], name_to_filename),
        "longest_winless_streaks": extract_top_streaks(streaks, ["L", "D"], name_to_filename),
        "longest_draw_streaks": extract_top_streaks(streaks, ["D"], name_to_filename),
        "biggest_win_margin": biggest_win_margin,
        "biggest_wins": biggest_wins,
        "most_clean_sheets": {"count": most_cs[0], "clubs": most_cs[1]},
        "least_clean_sheets": {"count": least_cs_val, "clubs": least_cs_data},
        "top_head_to_heads": top3_meetings
    }

    return render_template("statistics.html", **context)
