# database.py
import os
import shutil
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import upgrade
db = SQLAlchemy()


