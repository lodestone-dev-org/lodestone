import hmac
import os

from flask import Flask

app = Flask(__name__)

# is persisted so sessions survive a restart rather than logging you out
KEY_FILE = 'secret_key'
if not os.path.exists(KEY_FILE):
    with open(KEY_FILE, 'wb') as f:
        f.write(os.urandom(32))
with open(KEY_FILE, 'rb') as f:
    app.secret_key = f.read()

PASSWORD = os.environ.get('LODESTONE_PASSWORD', 'lodestone')


def password_ok(attempt):
    return hmac.compare_digest(attempt.encode(), PASSWORD.encode())


# this has to be last because routes.py imports app from here
import routes
