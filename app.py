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
        # the container itself is the source of truth for run state, so this only
        # holds what we need to build the container back up
        db.execute('''
            CREATE TABLE IF NOT EXISTS servers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER NOT NULL REFERENCES users(id),
                name TEXT NOT NULL,
                server_type TEXT NOT NULL DEFAULT 'PAPER',
                version TEXT NOT NULL,
                memory TEXT NOT NULL DEFAULT '2G',
                port INTEGER NOT NULL UNIQUE,
                rcon_password TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        ''')


init_db()

# this has to be last because routes.py imports app from here
import routes
