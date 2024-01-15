# #ca_extgension/__init__.py

from flask import Blueprint

ca_extension = Blueprint('ca_extension', __name__)

from . import routes
