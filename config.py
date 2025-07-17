"""Football League Configuration."""

import pathlib

# Root of this application, useful if it doesn't occupy an entire domain
APPLICATION_ROOT = '/'

# Secret key for encrypting cookies
SECRET_KEY = b'\xa3\xb2\xd8&\x1b\xe9\x85\x7fJ\x8b\x19\xf6\xda\xb7\xe2\xe1\x9b\xce'

# File Upload to store images/logos in var/uploads/
LEAGUE_ROOT = pathlib.Path(__file__).resolve().parent
UPLOAD_FOLDER = LEAGUE_ROOT / 'app' / 'static' / 'images'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024

# Database file is var/football_league.sqlite3
DATABASE_FILENAME = LEAGUE_ROOT / 'bfkt' / 'var' / 'football_league.sqlite3'
