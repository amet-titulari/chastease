# #extension/__init__.py

from flask import Blueprint

extension = Blueprint('extension', __name__)

from . import routes
