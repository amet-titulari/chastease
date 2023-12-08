# app.py
from flask import Flask, render_template
from flask_login import LoginManager
from benutzer.models import db, Benutzer
from benutzer.user import auth

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.sqlite'
app.config['SECRET_KEY'] = '5*K9kquqvXztz+i6*q'

db.init_app(app)

login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.init_app(app)

with app.app_context():
    db.create_all()

@login_manager.user_loader
def load_user(user_id):
    return Benutzer.query.get(int(user_id))

app.register_blueprint(auth, url_prefix='/')

@app.route('/')
def home():
    return render_template('index.html')

if __name__ == "__main__":
    app.run(debug=True)
