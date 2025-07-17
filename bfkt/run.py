import flask
from bfkt import app  # Import the app from the bfkt module

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)