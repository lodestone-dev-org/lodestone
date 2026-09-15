import os
import sqlite3

from flask import Flask, g

app = Flask(__name__)

# is persisted so sessions survive a restart rather than logging you out
KEY_FILE = 'secret_key'
if not os.path.exists(KEY_FILE):
    with open(KEY_FILE, 'wb') as f:
        f.write(os.urandom(32))
with open(KEY_FILE, 'rb') as f:
    app.secret_key = f.read()

DB_PATH = os.environ.get('LODESTONE_DB', 'lodestone.db')


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    with sqlite3.connect(DB_PATH) as db:
        db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            )
        ''')


init_db()

# this has to be last because routes.py imports app from here
import routes
