# ---------------------------------------------------------------------------- #
# Imports
# ---------------------------------------------------------------------------- #
import dateutil.parser
from babel.dates import format_datetime as babel_format_datetime
from flask import Flask, render_template, abort
from flask_moment import Moment
from flask_migrate import Migrate
import logging
from logging import Formatter, FileHandler
from flask_wtf import CSRFProtect
from flask_wtf.csrf import CSRFError
from http import HTTPStatus

from util import set_config, get_config
from misc import print_exc_info

# ---------------------------------------------------------------------------- #
# App Config.
# ---------------------------------------------------------------------------- #
from config import USE_ORM

ORM = USE_ORM
ENGINE = not ORM

app = Flask(__name__)
moment = Moment(app)
app.config.from_object('config')
set_config(app.config)

LOCALE = get_config("DEFAULT_LOCALE")

if ORM:
    from models import SQLAlchemyDB as db
    from misc import latest_lists_orm as latest_lists

    db.init_app(app)

    migrate = Migrate(app, db)
else:  # ENGINE
    from misc.engine import setup
    from misc import latest_lists_engine as latest_lists

    setup()

# https://nickjanetakis.com/blog/fix-missing-csrf-token-issues-with-flask
csrf = CSRFProtect()
csrf.init_app(app)

# ---------------------------------------------------------------------------- #
# Route Config.
# ---------------------------------------------------------------------------- #

from controllers import (
    shows, create_show, search_shows, search_shows_advanced,
    artists, search_artists, search_artists_advanced, display_artist,
    edit_artist, delete_artist, artist_availability, create_artist,
    venues, search_venues, search_venues_advanced, display_venue,
    create_venue, delete_venue, edit_venue, venue_bookings, venue_search_performer
)

app.add_url_rule('/shows', view_func=shows, methods=['GET'])
app.add_url_rule('/shows/search', view_func=search_shows, methods=['POST'])
app.add_url_rule('/shows/advanced_search', view_func=search_shows_advanced, methods=['GET', 'POST'])
app.add_url_rule('/shows/create', view_func=create_show, methods=['POST', 'GET'])

app.add_url_rule('/artists', view_func=artists, methods=['GET'])
app.add_url_rule('/artists/search', view_func=search_artists, methods=['POST'])
app.add_url_rule('/artists/advanced_search', view_func=search_artists_advanced, methods=['GET', 'POST'])
app.add_url_rule('/artists/create', view_func=create_artist, methods=['POST', 'GET'])
app.add_url_rule('/artists/<int:artist_id>', view_func=display_artist, methods=['GET'])
app.add_url_rule('/artists/<int:artist_id>', view_func=delete_artist, methods=['DELETE'])
app.add_url_rule('/artists/<int:artist_id>/edit', view_func=edit_artist, methods=['POST', 'GET'])
app.add_url_rule('/artists/<int:artist_id>/availability', view_func=artist_availability, methods=['GET'])

app.add_url_rule('/venues', view_func=venues, methods=['GET'])
app.add_url_rule('/venues/search', view_func=search_venues, methods=['POST'])
app.add_url_rule('/venues/advanced_search', view_func=search_venues_advanced, methods=['GET', 'POST'])
app.add_url_rule('/venues/create', view_func=create_venue, methods=['POST', 'GET'])
app.add_url_rule('/venues/<int:venue_id>', view_func=display_venue, methods=['GET'])
app.add_url_rule('/venues/<int:venue_id>', view_func=delete_venue, methods=['DELETE'])
app.add_url_rule('/venues/<int:venue_id>/edit', view_func=edit_venue, methods=['POST', 'GET'])
app.add_url_rule('/venues/<int:venue_id>/bookings', view_func=venue_bookings, methods=['GET'])
app.add_url_rule('/venues/<int:venue_id>/search/artist', view_func=venue_search_performer, methods=['POST'])

# ---------------------------------------------------------------------------- #
# Filters.
# ---------------------------------------------------------------------------- #


def format_datetime(date_value, date_format='medium'):
    date = dateutil.parser.parse(date_value)
    if date_format == 'full':
        date_format = "EEEE MMMM, d, y 'at' h:mma"
    elif date_format == 'medium':
        date_format = "EE MM, dd, y h:mma"
    return babel_format_datetime(date, format=date_format, locale=LOCALE)


app.jinja_env.filters['datetime'] = format_datetime


@app.context_processor
def inject_user():
    return dict(search_info={
        'venue': {
            'url': "/venues/search?mode=basic",
            'text': "Find a venue"
        },
        'artist': {
            'url': "/artists/search?mode=basic",
            'text': "Find an artist"
        },
        'show': {
            'url': "/shows/search?mode=basic",
            'text': "Find a show"
        }
    })

# ---------------------------------------------------------------------------- #
# Controllers.
# ---------------------------------------------------------------------------- #

@app.route('/')
def index():
    latest_artists = []
    latest_venues = []
    try:
        latest_artists, latest_venues = latest_lists()
    except:
        print_exc_info()
        abort(HTTPStatus.INTERNAL_SERVER_ERROR.value)
       
    artist_list = [{'id': a.id, 'name': a.name} for a in latest_artists]
    venue_list = [{'id': v.id, 'name': v.name} for v in latest_venues]
    return render_template('pages/home.html', artists=artist_list, venues=venue_list)


@app.errorhandler(CSRFError)
def handle_csrf_error(error):
    return render_template('errors/400.html', reason=error.description), HTTPStatus.BAD_REQUEST.value


@app.errorhandler(HTTPStatus.NOT_FOUND.value)
def not_found_error(error):
    return render_template('errors/404.html'), HTTPStatus.NOT_FOUND.value


@app.errorhandler(HTTPStatus.INTERNAL_SERVER_ERROR.value)
def server_error(error):
    return render_template('errors/500.html'), HTTPStatus.INTERNAL_SERVER_ERROR.value


@app.errorhandler(HTTPStatus.SERVICE_UNAVAILABLE.value)
def server_error(error):
    return render_template('errors/503.html'), HTTPStatus.SERVICE_UNAVAILABLE.value


if not app.debug:
    file_handler = FileHandler('error.log')
    file_handler.setFormatter(
        Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]')
    )
    app.logger.setLevel(logging.INFO)
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.info('errors')

# ---------------------------------------------------------------------------- #
# Launch.
# ---------------------------------------------------------------------------- #

# Default port:
if __name__ == '__main__':
    app.run()

# Or specify port manually:
"""
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
"""
