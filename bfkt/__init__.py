# __init__.py
import flask

# Create the Flask app
app = flask.Flask(__name__)

# Load configuration settings from config.py
app.config.from_object('config')

# Import the views and models after app creation
import bfkt.views  # noqa: E402
import bfkt.scheduler
import bfkt.simulator
import bfkt.sportsbook
import bfkt.champions
import bfkt.seasonend
import bfkt.trading
import bfkt.tradeclub
import bfkt.models  # noqa: E402
import bfkt.underlying
import bfkt.portfolio
import bfkt.options
import bfkt.options_trade
import bfkt.statistics
import bfkt.h2h
import bfkt.pointshistory
import bfkt.obet
import bfkt.betzoom