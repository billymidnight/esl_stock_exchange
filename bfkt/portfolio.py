import os
import flask
import numpy as np
import matplotlib.pyplot as plt
from bfkt import app  
from bfkt.models import get_db, equity_calc
from flask import render_template

@app.route('/portfolio_viewer')
def portfolio_viewer():
    con = get_db()
    cur = con.cursor()

    # Get bankroll
    bankroll_row = cur.execute("SELECT bankroll FROM equity").fetchone()
    bankroll = bankroll_row["bankroll"] if bankroll_row else 0

    gw_row = cur.execute("SELECT gameweek FROM status").fetchone()
    current_gw = gw_row["gameweek"] if gw_row else 0

    all_rows = cur.execute("""
        SELECT gameweek, gameno, equity_value
        FROM equity_history
        ORDER BY gameweek, gameno
    """).fetchall()

    xy_all = []
    for row in all_rows:
        xval = row["gameweek"] + (0.1 * row["gameno"])
        xy_all.append((xval, row["equity_value"]))
    last_1 = [(x, y) for x, y in xy_all if int(x) == current_gw]

    if not last_1:
        if len(xy_all) >= 1:
            last = xy_all[-1][1]
            second_last = xy_all[-2][1] if len(xy_all) >= 2 else last
            last_1 = [(current_gw, second_last), (current_gw + 0.1, last)]
        else:
            last_1 = [(current_gw, 0)]

    def extract_by_gameweeks(data, max_gws):
        seen_gws = set()
        result = []
        for x, y in reversed(data):
            gw = int(x)
            if gw not in seen_gws:
                seen_gws.add(gw)
            if len(seen_gws) > max_gws:
                break
            result.append((x, y))
        return list(reversed(result))

    last_10 = extract_by_gameweeks(xy_all, 10)
    last_20 = extract_by_gameweeks(xy_all, 20)
    all_time = xy_all

    trends = {
        "alltime": all_time,
        "last20": last_20,
        "last10": last_10,
        "last1": last_1
    }

    graph_dir = os.path.join(os.path.dirname(__file__), "static", "images", "graphs")
    os.makedirs(graph_dir, exist_ok=True)

    trend_meta = {}

    for label, data in trends.items():
        if len(data) < 1:
            continue

        x = [d[0] for d in data]
        y = [d[1] for d in data]
        delta = y[-1] - y[0]
        pct = round((delta / y[0]) * 100, 2) if y[0] != 0 else 0
        color = "#00e676" if delta >= 0 else "#ff5252"

        fig, ax = plt.subplots(figsize=(7, 4))
        ax.plot(x, y, marker='o', linewidth=2, color=color)
        if label == "last1":
            realLabel = f"Current Gameweek ({current_gw})"
        elif label == "last10":
            realLabel = "Last 10 Gameweeks"
        elif label == "last20":
            realLabel = "Last 20 Gameweeks"
        else:
            realLabel = "All Time"
        ax.set_title(f"{realLabel}", fontsize=14, color='white')
        ax.set_xlabel("Gameweek", color='white')
        ax.set_ylabel("Equity", color='white')
        ax.grid(True, linestyle="--", alpha=0.4)
        ax.set_facecolor("#0d1117")
        fig.patch.set_facecolor("#0d1117")
        ax.tick_params(colors="white")

        fname = f"equity_{label}.png"
        fpath = os.path.join(graph_dir, fname)
        plt.tight_layout()
        plt.savefig(fpath, dpi=150, bbox_inches='tight')
        plt.close()

        trend_meta[label] = {
            "filename": fname,
            "dollar": round(delta, 2),
            "percent": pct
        }

    holding_rows = cur.execute("""
        SELECT sh.club_name, sh.volume, sh.avg_cost,
               p.initial_rating, p.filename
        FROM stock_holdings sh
        JOIN participants p ON sh.club_name = p.name
        WHERE sh.volume > 0
    """).fetchall()

    gameweek_row = cur.execute("SELECT gameweek FROM status").fetchone()
    current_gameweek = gameweek_row["gameweek"] if gameweek_row else 0
    previous_gameweek = current_gameweek - 1

    club_data = []
    pie_data = {}

    for row in holding_rows:
        club = row["club_name"]
        volume = row["volume"]
        avg_cost = row["avg_cost"]
        current_price = round(row["initial_rating"] * 100.0, 2)

        total_cost = round(volume * avg_cost, 2)
        market_value = round(volume * current_price, 2)

        return_dollar = round(market_value - total_cost, 2)
        return_pct = round((return_dollar / total_cost) * 100, 2) if total_cost > 0 else 0

        pie_data[club] = market_value

        last_week_row = cur.execute("""
            SELECT rating FROM ratings_history
            WHERE club_name = ? AND gameweek = ?
        """, (club, previous_gameweek)).fetchone()

        if last_week_row:
            last_price = round(last_week_row["rating"] * 100.0, 2)
            weekly_dollar_change = round(current_price - last_price, 2)
            weekly_percent_change = round((weekly_dollar_change / last_price) * 100, 2) if last_price else 0
        else:
            weekly_dollar_change = 0.00
            weekly_percent_change = 0.00

        gw0_row = cur.execute("""
            SELECT rating FROM ratings_history
            WHERE club_name = ? AND gameweek = 0
        """, (club,)).fetchone()

        if gw0_row:
            gw0_price = round(gw0_row["rating"] * 100.0, 2)
            returns_dollar = round(current_price - gw0_price, 2)
            returns_percent = round((returns_dollar / gw0_price) * 100, 2) if gw0_price else 0
        else:
            returns_dollar = 0.00
            returns_percent = 0.00

        # Transaction history
        txns = cur.execute("""
            SELECT gameweek, action, volume_traded, underlying_price
            FROM transactions
            WHERE club_name = ?
            ORDER BY gameweek ASC
        """, (club,)).fetchall()

        club_data.append({
            "club_name": club,
            "filename": row["filename"],
            "price": current_price,
            "volume": volume,
            "avg_cost": avg_cost,
            "total_cost": total_cost,
            "value": market_value,
            "total_return": return_dollar,
            "total_return_pct": return_pct,
            "dollar_change": weekly_dollar_change,
            "percent_change": weekly_percent_change,
            "returns_dollar": returns_dollar,
            "returns_percent": returns_percent,
            "transactions": txns
        })

    # total_holdings_value = sum(pie_data.values())
    # equity = round(bankroll + total_holdings_value, 2)
    # bankroll = round(bankroll, 2)

    bankroll, equity = equity_calc()

    # Pie chart
    fig, ax = plt.subplots(figsize=(7, 7))
    labels = list(pie_data.keys())
    sizes = list(pie_data.values())

    wedges, texts, autotexts = ax.pie(
        sizes,
        labels=labels,
        autopct='%1.1f%%',
        startangle=90,
        textprops={'fontsize': 19, 'color': 'white'}
    )

    for autotext in autotexts:
        autotext.set_fontsize(20)
        autotext.set_fontweight('bold')
    for text in texts:
        text.set_fontsize(20)
        text.set_fontweight('bold')

    ax.axis('equal')
    fig.patch.set_facecolor('#0d1117')
    ax.set_facecolor('#0d1117')

    current_dir = os.path.dirname(__file__)
    graph_dir = os.path.join(current_dir, "static", "images", "graphs")
    os.makedirs(graph_dir, exist_ok=True)
    pie_path = os.path.join(graph_dir, "portfolio_pie.png")
    plt.savefig(pie_path, bbox_inches='tight', dpi=150, transparent=False)
    plt.close()

    return render_template("portfolio.html",
                           equity_graphs=trend_meta,
                           holdings=club_data,
                           bankroll=bankroll,
                           equity=equity,
                           piechart_filename="portfolio_pie.png")

@app.route('/options_portfolio_viewer')
def options_portfolio():
    con = get_db()

    bankroll = con.execute("SELECT bankroll FROM equity").fetchone()["bankroll"]

    holding_value = con.execute("""
        SELECT SUM(sh.volume * (p.initial_rating * 100.0)) AS total_value
        FROM stock_holdings sh
        JOIN participants p ON sh.club_name = p.name
    """).fetchone()["total_value"] or 0

    options_value = con.execute("""
        SELECT SUM(curr_premium * contracts * 100.0) as sum
        FROM options_holdings
        WHERE expired = 0 AND contracts > 0
    """).fetchone()["sum"] or 0

    equity = round(bankroll + holding_value + options_value, 2)
    bankroll = round(bankroll, 2)
    options_equity = round(options_value, 2)

    current_gw = con.execute("SELECT gameweek FROM status").fetchone()["gameweek"]

    # Active Options
    active_rows = con.execute("""
        SELECT oh.*, p.initial_rating, p.name,
               rh.rating AS prev_rating
        FROM options_holdings oh
        JOIN participants p ON oh.underlying = p.name
        LEFT JOIN ratings_history rh ON rh.club_name = p.name
            AND rh.gameweek = ?
        WHERE oh.expired = 0 AND oh.contracts > 0
        ORDER BY holding_id DESC
    """, (current_gw - 1,)).fetchall()

    active_options = []
    total_unrealized_pnl = 0

    for row in active_rows:
        curr = row["curr_premium"]
        cost = row["cost"]
        contracts = row["contracts"]
        change = round(curr - cost, 2)
        pct_change = round((change / cost) * 100, 2) if cost > 0 else 0
        total_cost = round(cost * contracts * 100, 2)
        market_value = round(curr * contracts * 100, 2)
        unrealized_pnl = market_value - total_cost
        total_unrealized_pnl += unrealized_pnl
        underlying_price = round(row["initial_rating"] * 100.0, 2)

        dollar_change = None
        percent_change = None
        if row["prev_rating"]:
            prev_price = row["prev_rating"] * 100.0
            dollar_change = round(underlying_price - prev_price, 2)
            percent_change = round((dollar_change / prev_price) * 100, 2)

        active_options.append({
            "id": row["holding_id"],
            "club": row["underlying"],
            "strike": row["strike"],
            "type": row["type"],
            "expiry": row["expiration_gw"],
            "contracts": contracts,
            "cost": cost,
            "curr": curr,
            "change": change,
            "pct_change": pct_change,
            "total_cost": round(total_cost, 2), 
            "market_value": round(market_value, 2), 
            "unrealized_pnl": round(unrealized_pnl, 2),
            "underlying_price": underlying_price,
            "underlying_change": dollar_change,
            "underlying_pct_change": percent_change
        })

    # Expired Options
    expired_rows = con.execute("""
        SELECT * FROM options_holdings
        WHERE expired = 1 OR contracts = 0
        ORDER BY holding_id DESC
    """).fetchall()

    expired_options = []
    total_realized_pnl = 0

    for row in expired_rows:
        contracts = row["contracts"]
        cost = row["cost"]
        final_val = row["curr_premium"]
        total_cost = cost * 100 * contracts
        proceeds = final_val * 100 * contracts
        realized = proceeds - total_cost
        itm_otm = row["itm_otm"]
        if itm_otm == "itm" and row["held_till_expiry"] == True:
            realized = (row["expired_underlying"] - row["strike"]) * 100
            if row["type"] == "put":
                realized = -realized
            realized -= total_cost
            proceeds = total_cost + realized
        total_realized_pnl += realized

        realized_pct = round((realized / total_cost) * 100, 2) if total_cost > 0 else 0

        expired_options.append({
            "id": row["holding_id"],
            "club": row["underlying"],
            "strike": row["strike"],
            "type": row["type"],
            "expiry": row["expiration_gw"],
            "contracts": contracts,
            "cost": cost,
            "final_val": final_val,
            "total_cost": round(total_cost, 2),
            "proceeds": round(proceeds, 2),
            "realized_pnl": round(realized, 2),
            "realized_pct": realized_pct,
            "held_to_expiry": bool(row["held_till_expiry"]),
            "expired_nature": row["itm_otm"] if row["held_till_expiry"] else "N/A"
        })
    
    net_pnl = round(total_realized_pnl + total_unrealized_pnl, 2)

    #obet part

    active_obets = con.execute("SELECT * from options_bets WHERE result is NULL ORDER BY obet_expiry ASC, obet_id DESC").fetchall()
    net_downside = con.execute("SELECT SUM(obet_size) as downside from options_bets WHERE result is NULL").fetchone()["downside"]
    net_upside = con.execute("SELECT SUM(obet_potential_payout-obet_size) as upside from options_bets WHERE result is NULL").fetchone()["upside"]

    finished_obets = con.execute("SELECT * from options_bets WHERE result is NOT NULL ORDER BY obet_expiry DESC, obet_id DESC").fetchall()

    netlosses = con.execute("SELECT SUM(obet_size) as Losses from options_bets WHERE result = 'Lost'").fetchone()["Losses"]
    netprofits = con.execute("SELECT SUM(obet_potential_payout - obet_size) as Wins from options_bets WHERE result = 'Won'").fetchone()["Wins"]
    netpandl = netprofits - netlosses

    return flask.render_template("options_portfolio_full.html", 
        bankroll=bankroll,
        equity=equity,
        gameweek=current_gw,
        options_equity=options_equity,
        active_options=active_options,
        expired_options=expired_options,
        total_realized_pnl=round(total_realized_pnl, 2),
        total_unrealized_pnl=round(total_unrealized_pnl, 2),
        net_pnl = net_pnl,
        active_obets=active_obets,
        net_downside=net_downside,
        net_upside=net_upside,
        finished_obets=finished_obets,
        netlosses=netlosses,
        netprofits=netprofits,
        netpandl=netpandl
    )
