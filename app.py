from flask import Flask, render_template
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

from database import db
from user import user_bp
from user.models import User

app = Flask(__name__)

# Konfiguration der App
app.config['SECRET_KEY'] = '6K2x*Ssi96Dx9io#C%'  # Ihr geheimer Schlüssel
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.sqlite'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialisieren von db mit der App
db.init_app(app)
migrate = Migrate(app, db)

# Initialisieren des Login-Managers
login_manager = LoginManager()
login_manager.login_view = "user.login"  # Setzen Sie die Login-View für Flask-Login
login_manager.init_app(app)

# Benutzer-Lade-Funktion für Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Registrieren des user-Blueprints
app.register_blueprint(user_bp, url_prefix='/user')

@app.route('/')
def hello_world():
    titel = "Willkommen zu meiner Flask-Anwendung"
    content = "Dies ist der Inhalt meiner Seite."
    return render_template('index.html', titel=titel, content=content)

if __name__ == '__main__':
    # Fügen Sie die Migrationserweiterung hinzu und erstellen Sie das Migrationsverzeichnis
    migrate = Migrate(app, db)
    app.run(debug=True)
