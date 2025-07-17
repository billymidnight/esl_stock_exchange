import os
import flask
from flask import render_template
from bfkt import app
from bfkt.models import get_db
import matplotlib.pyplot as plt
from matplotlib.cm import get_cmap

@app.route("/graph_generator")
def graph_generator():
    con = get_db()

    # Map team name → filename
    filename_map = {
        row["name"]: row["filename"]
        for row in con.execute("SELECT name, filename FROM participants").fetchall()
    }

    # Pull points history
    rows = con.execute(
        "SELECT name, gameweek, points FROM points_history ORDER BY gameweek"
    ).fetchall()

    # Organize points history
    data = {}
    for row in rows:
        name = row["name"]
        if name not in data:
            data[name] = []
        data[name].append((row["gameweek"], row["points"]))

    fig, ax = plt.subplots(figsize=(18, 10))
    cmap = get_cmap('tab20')  
    participants_with_colors = []

    for idx, (team, values) in enumerate(data.items()):
        gws = [v[0] for v in values]
        pts = [v[1] for v in values]
        color = cmap(idx % 20)
        ax.plot(gws, pts, linewidth=2, label=team, color=color)

        participants_with_colors.append({
            "name": team,
            "color": f"rgb({int(color[0]*255)}, {int(color[1]*255)}, {int(color[2]*255)})",
            "filename": filename_map.get(team, "")
        })

    ax.set_title("Points History for All Clubs", fontsize=20, fontweight="bold")
    ax.set_xlabel("Gameweek", fontsize=14)
    ax.set_ylabel("Points", fontsize=14)
    ax.grid(True, linestyle="--", alpha=0.3)
    ax.set_facecolor("#0d1117")
    fig.patch.set_facecolor("#0d1117")
    ax.tick_params(colors="white")
    ax.title.set_color("#58a6ff")
    ax.xaxis.label.set_color("white")
    ax.yaxis.label.set_color("white")

    # Save to correct directory
    out_path = os.path.join(os.path.dirname(__file__), "static", "images", "points_history_graph.png")
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()

    return render_template("pointshistory.html", participants=participants_with_colors)
