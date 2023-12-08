# benutzer/user.py
from flask import Blueprint, render_template, redirect, url_for, request, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from .models import Benutzer, db

auth = Blueprint('auth', __name__)

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = Benutzer.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('main.index'))  # Angenommen, es gibt eine 'index'-Route in Ihrer Hauptanwendung
        else:
            flash('Login fehlgeschlagen. Bitte überprüfen Sie Ihre Anmeldedaten.')

    return render_template('login.html')

@auth.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        password2 = request.form.get('password2')

        user = Benutzer.query.filter_by(username=username).first()

        if user:
            flash('Benutzername existiert bereits.')
        elif password != password2:
            flash('Passwörter stimmen nicht überein.')
        else:
            # Hier wird das Passwort gehasht
            hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
            new_user = Benutzer(username=username, password=hashed_password)
            db.session.add(new_user)
            db.session.commit()

            return redirect(url_for('auth.login'))

    return render_template('signup.html')

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.index'))  # Rückkehr zur Hauptseite
