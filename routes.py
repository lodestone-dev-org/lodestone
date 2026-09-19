import functools
import re
import secrets
import sqlite3

from docker.errors import DockerException
from flask import (
    Response, abort, flash, redirect, render_template, request, session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

import docker_backend
from app import app, get_db

# 25565 is the port everyone expects, so the first server gets it and the rest
# walk up from there
PORT_RANGE = range(25565, 25665)


def login_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get('user_id'):
            return redirect(url_for('login'))
        return view(*args, **kwargs)
    return wrapped


def owned(server_id):
    return get_db().execute(
        'SELECT * FROM servers WHERE id = ? AND owner_id = ?',
        (server_id, session.get('user_id')),
    ).fetchone()


def next_port():
    taken = {row['port'] for row in get_db().execute('SELECT port FROM servers')}
    for port in PORT_RANGE:
        if port not in taken:
            return port
    raise RuntimeError('no free ports left in the panel range')


def act(server_id, action, done):
    """Run a lifecycle action on a server the current user owns."""
    if owned(server_id) is None:
        abort(404)
    try:
        action(server_id)
    except (DockerException, LookupError) as e:
        flash(str(e))
    else:
        flash(done)
    return redirect(url_for('server_console', server_id=server_id))


def run_state(running, server_id):
    if running is None:
        return {'state': 'unavailable', 'uptime': None}
    return running.get(server_id, {'state': 'missing', 'uptime': None})


@app.route('/')
@login_required
def index():
    servers = get_db().execute(
        'SELECT * FROM servers WHERE owner_id = ? ORDER BY id', (session['user_id'],)
    ).fetchall()
    running = docker_backend.statuses()
    states = {s['id']: run_state(running, s['id']) for s in servers}
    return render_template('server_browser.html', servers=servers, states=states)


@app.route('/server/<int:server_id>/console')
@login_required
def server_console(server_id):
    server = owned(server_id)
    if server is None:
        abort(404)

    running = docker_backend.statuses()
    state = run_state(running, server_id)['state']
    return render_template('server_console.html',
                           servers=[server], states={server['id']: state})


def parse_players(text):
    """Pull the count and names out of an rcon `list` reply."""
    m = re.search(r'There are (\d+) of a max of (\d+) players online:?\s*(.*)$', text)
    if not m:
        raise RuntimeError(f'unexpected response: {text!r}')
    names = [n for n in (m.group(3) or '').split(', ') if n]
    return {'count': int(m.group(1)), 'max': int(m.group(2)), 'names': names}


@app.route('/server/<int:server_id>/players')
@login_required
def server_players(server_id):
    server = owned(server_id)
    if server is None:
        abort(404)

    players = None
    error = None
    try:
        players = parse_players(docker_backend.command(server_id, 'list'))
    except (DockerException, LookupError, RuntimeError, ValueError) as e:
        error = str(e)

    return render_template('players.html', server=server, players=players, error=error)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']

        if not username or not password:
            flash('Username and password are required')
            return render_template('register.html')

        db = get_db()
        try:
            cursor = db.execute(
                'INSERT INTO users (username, password_hash) VALUES (?, ?)',
                (username, generate_password_hash(password)),
            )
            db.commit()
        except sqlite3.IntegrityError:
            flash('Username already taken')
            return render_template('register.html')

        session['user_id'] = cursor.lastrowid
        session['username'] = username
        return redirect(url_for('index'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']

        user = get_db().execute(
            'SELECT * FROM users WHERE username = ?', (username,)
        ).fetchone()

        if user and check_password_hash(user['password_hash'], password):
            session.clear()
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('index'))

        flash('Invalid username or password')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/server/create', methods=['GET', 'POST'])
@login_required
def create_server():
    if request.method == 'GET':
        return render_template('server_create.html')

    name = request.form['server_name'].strip()
    version = request.form.get('minecraft_version', '1.21')
    server_type = request.form.get('server_type', 'PAPER')
    memory = request.form.get('memory', '2G')

    if not name:
        flash('Server name is required')
        return redirect(url_for('index'))

    db = get_db()
    port = next_port()
    cursor = db.execute(
        'INSERT INTO servers (owner_id, name, server_type, version, memory, port,'
        ' rcon_password) VALUES (?, ?, ?, ?, ?, ?, ?)',
        (session['user_id'], name, server_type, version, memory, port,
         secrets.token_urlsafe(24)),
    )
    db.commit()
    server = owned(cursor.lastrowid)

    try:
        docker_backend.create(server['id'], version, port, server['rcon_password'],
                              server_type, memory)
    except (DockerException, ValueError) as e:
        # no container means no server, so don't leave the row behind claiming one
        db.execute('DELETE FROM servers WHERE id = ?', (server['id'],))
        db.commit()
        flash(f'Could not create the container: {e}')
        return redirect(url_for('index'))

    flash(f'{name} created on port {port}. First start downloads the server jar.')
    return redirect(url_for('index'))


@app.route('/server/<int:server_id>/start', methods=['POST'])
@login_required
def start_server(server_id):
    return act(server_id, docker_backend.start, 'Starting')


@app.route('/server/<int:server_id>/stop', methods=['POST'])
@login_required
def stop_server(server_id):
    return act(server_id, docker_backend.stop, 'Stopped')


@app.route('/server/<int:server_id>/restart', methods=['POST'])
@login_required
def restart_server(server_id):
    return act(server_id, docker_backend.restart, 'Restarting')


@app.route('/server/<int:server_id>/command', methods=['POST'])
@login_required
def server_command(server_id):
    if owned(server_id) is None:
        abort(404)

    line = request.form['command'].strip()
    if line:
        try:
            reply = docker_backend.command(server_id, line)
        except (DockerException, LookupError, RuntimeError) as e:
            flash(str(e))
        else:
            flash(reply or f'sent: {line}')

    return redirect(url_for('server_console', server_id=server_id))


@app.route('/server/<int:server_id>/logs')
@login_required
def server_logs(server_id):
    if owned(server_id) is None:
        abort(404)
    # polled by the console for now; this becomes the SSE stream later
    return Response(docker_backend.logs(server_id), mimetype='text/plain')


@app.route('/server/<int:server_id>/delete', methods=['POST'])
@login_required
def delete_server(server_id):
    server = owned(server_id)
    if server is None:
        abort(404)

    # the row outlives a failed remove on purpose, so a container we could not
    # reach still has something in the panel pointing at it
    try:
        docker_backend.remove(server_id)
    except DockerException as e:
        flash(f'Could not remove the container: {e}')
        return redirect(url_for('index'))

    db = get_db()
    db.execute('DELETE FROM servers WHERE id = ?', (server_id,))
    db.commit()
    flash(f"Removed {server['name']}. Its world files are still on disk.")
    return redirect(url_for('index'))


def parent(path):
    return '/' + '/'.join(path.strip('/').split('/')[:-1])


def crumbs(path):
    """Breadcrumb trail for a folder, root first."""
    trail = [('server', '/')]
    walked = ''
    for part in path.strip('/').split('/'):
        if part:
            walked += '/' + part
            trail.append((part, walked))
    return trail


def browse(server_id, path):
    return redirect(url_for('server_files', server_id=server_id, path=path))


@app.route('/server/<int:server_id>/files')
@login_required
def server_files(server_id):
    server = owned(server_id)
    if server is None:
        abort(404)

    path = request.args.get('path', '/')
    try:
        entries = docker_backend.listing(server_id, path)
    except (ValueError, OSError):
        abort(404)

    return render_template('file_browser.html', server=server, path=path,
                           crumbs=crumbs(path), entries=entries)


@app.route('/server/<int:server_id>/files/edit')
@login_required
def edit_file(server_id):
    server = owned(server_id)
    if server is None:
        abort(404)

    path = request.args.get('path', '')
    here = parent(path)
    try:
        content = docker_backend.read_text(server_id, path)
    except UnicodeDecodeError:
        flash(f'{path} is not a text file')
        return browse(server_id, here)
    except ValueError as e:
        flash(str(e))
        return browse(server_id, here)
    except OSError:
        abort(404)

    return render_template('file_browser.html', server=server, path=here,
                           crumbs=crumbs(here), editing=path, content=content)


@app.route('/server/<int:server_id>/files/save', methods=['POST'])
@login_required
def save_file(server_id):
    if owned(server_id) is None:
        abort(404)

    path = request.form['path']
    try:
        docker_backend.write_text(server_id, path, request.form['content'])
    except (ValueError, OSError) as e:
        flash(str(e))
    else:
        flash(f'Saved {path}')

    return browse(server_id, parent(path))


@app.route('/server/<int:server_id>/files/folder', methods=['POST'])
@login_required
def new_folder(server_id):
    if owned(server_id) is None:
        abort(404)

    here = request.form['path']
    name = secure_filename(request.form['name'])
    if not name:
        flash('That folder name has nothing usable in it')
        return browse(server_id, here)

    try:
        docker_backend.make_folder(server_id, f'{here}/{name}')
    except (ValueError, OSError) as e:
        flash(str(e))
    else:
        flash(f'Created {name}')

    return browse(server_id, here)


@app.route('/server/<int:server_id>/files/upload', methods=['POST'])
@login_required
def upload_file(server_id):
    if owned(server_id) is None:
        abort(404)

    here = request.form['path']
    upload = request.files['file']
    name = secure_filename(upload.filename or '')
    if not name:
        flash('That file name has nothing usable in it')
        return browse(server_id, here)

    try:
        upload.save(docker_backend.resolve(server_id, f'{here}/{name}'))
    except (ValueError, OSError) as e:
        flash(str(e))
    else:
        flash(f'Uploaded {name}')

    return browse(server_id, here)


@app.route('/server/<int:server_id>/files/delete', methods=['POST'])
@login_required
def delete_file(server_id):
    if owned(server_id) is None:
        abort(404)

    path = request.form['path']
    try:
        docker_backend.delete_path(server_id, path)
    except (ValueError, OSError) as e:
        flash(str(e))
    else:
        flash(f'Deleted {path}')

    return browse(server_id, parent(path))

@app.route('/accountsettings', methods=['GET', 'POST'])
@login_required
def accountsettings():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']

        if not username:
            flash('Username is required')
            return render_template('account_settings.html')

        db = get_db()
        try:
            db.execute('UPDATE users SET username = ? WHERE id = ?',
                       (username, session['user_id']))
            if password:
                db.execute('UPDATE users SET password_hash = ? WHERE id = ?',
                           (generate_password_hash(password), session['user_id']))
            db.commit()
        except sqlite3.IntegrityError:
            flash('Username already taken')
            return render_template('account_settings.html')

        session['username'] = username
        flash('Settings updated')
        return redirect(url_for('accountsettings'))

    return render_template('account_settings.html')
