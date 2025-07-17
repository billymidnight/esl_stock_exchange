# models.py
import sqlite3
import flask
from bfkt import app  # Import the app instance

def dict_factory(cursor, row):
    """Convert database row objects to a dictionary keyed on column name."""
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}

def get_db():
    """Open a new database connection."""
    if 'sqlite_db' not in flask.g:
        db_filename = app.config['DATABASE_FILENAME']  # Access config directly
        flask.g.sqlite_db = sqlite3.connect(str(db_filename))
        flask.g.sqlite_db.row_factory = dict_factory
        flask.g.sqlite_db.execute("PRAGMA foreign_keys = ON")  # Enable foreign key support

    return flask.g.sqlite_db

@app.teardown_appcontext
def close_db(error):
    """Close the database at the end of a request."""
    sqlite_db = flask.g.pop('sqlite_db', None)
    if sqlite_db is not None:
        sqlite_db.commit()
        sqlite_db.close()

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

def prob_to_american(prob):
    if prob <= 0 or prob >= 1:
        return None
    if prob > 0.5:
        return int(round(-100 * prob / (1 - prob)))  
    else:
        return int(round(100 * (1 - prob) / prob))  

def format_american_odds(odds):
    abs_odds = abs(odds)
    sign = 1 if odds >= 0 else -1

    if abs_odds >= 1200000:
        # 2 significant digits
        from math import log10, floor
        digits = 2
        power = floor(log10(abs_odds))
        rounded = round(abs_odds, -power + digits - 1)
        return sign * int(rounded)

    elif abs_odds >= 12000:
        return sign * ((abs_odds // 1000) * 1000)
    elif abs_odds >= 1200:
        return sign * ((abs_odds // 100) * 100)
    elif abs_odds >= 400:
        return sign * ((abs_odds // 10) * 10)
    else:
        return odds

def prob_to_decimal(prob):
    """
    Converts an implied probability (0 < prob <= 1) to decimal odds.
    Returns float rounded to 2 decimal places.
    """
    if prob <= 0 or prob > 1:
        raise ValueError("Probability must be between 0 and 1 (exclusive of 0).")

    return round(1 / prob, 2)