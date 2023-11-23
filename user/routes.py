from flask import render_template, redirect, url_for, flash
from flask_login import login_user, current_user, logout_user
from . import user_bp
from .forms import LoginForm, RegistrationForm
from .models import User, db

@user_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('user.test'))  # Oder eine andere passende Route

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            return redirect(url_for('user.test'))  # Oder wohin auch immer der Benutzer nach dem Login geleitet werden soll
        else:
            flash('Login fehlgeschlagen. Bitte überprüfen Sie Benutzername und Passwort.')

    return render_template('user/login.html', form=form)


@user_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('user.test'))

    form = RegistrationForm()
    if form.validate_on_submit():
        new_user = User(username=form.username.data, email=form.email.data)
        new_user.set_password(form.password.data)
        db.session.add(new_user)
        db.session.commit()
        flash('Erfolgreich registriert!')
        return redirect(url_for('user.login'))

    return render_template('user/register.html', form=form)


@user_bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('user.login'))

@user_bp.route('/test')
def test():
    return "Usermodul funktioniert!"


