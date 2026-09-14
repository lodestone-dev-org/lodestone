from flask import flash, redirect, render_template, request, session, url_for

from app import app, password_ok


@app.route('/')
def index():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if password_ok(request.form['password']):
            session['logged_in'] = True
            return redirect(url_for('index'))
        flash('Incorrect password')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))
