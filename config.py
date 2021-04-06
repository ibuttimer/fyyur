import os

#
# NOTE: Database configuration
#       Create a copy of /secrets-sample.py, update it with the database details, and save it as `secrets.py`. 
#

SECRET_KEY = os.urandom(32)
# Grabs the folder where the script runs.
basedir = os.path.abspath(os.path.dirname(__file__))

# Enable debug mode.
DEBUG = True

# Connect to the database
from secrets import SERVER
from secrets import PORT
from secrets import DATABASE
from secrets import USERNAME
from secrets import PASSWORD

SQLALCHEMY_DATABASE_URI = f'postgresql://{USERNAME}:{PASSWORD}@{SERVER}:{PORT}/{DATABASE}'

SQLALCHEMY_TRACK_MODIFICATIONS = False    # disable FSADeprecationWarning

# general 
SHOWS_PER_PAGE = 6

# default region for phone number validation
DEFAULT_REGION = "US"

# default locale
DEFAULT_LOCALE = 'en_US'

# max number of latest listings on home page
NUM_LATEST_ON_HOME = 10

# app mode
ORM_CONNECTION = 'orm'
ENGINE_CONNECTION = 'engine'
# CONNECTION_MODE = ENGINE_CONNECTION
CONNECTION_MODE = ORM_CONNECTION

USE_ORM = CONNECTION_MODE == ORM_CONNECTION
USE_ENGINE = CONNECTION_MODE == ENGINE_CONNECTION

# print sql statements (only valid in engine mode)
PRINT_SQL = True

