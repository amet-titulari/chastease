# benutzer/__init__.py

from flask import Blueprint

benutzer = Blueprint('benutzer', __name__)

from . import routes
