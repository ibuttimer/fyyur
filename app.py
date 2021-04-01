#----------------------------------------------------------------------------#
# Imports
#----------------------------------------------------------------------------#
import dateutil.parser
import babel
from flask import Flask, render_template, abort
from flask_moment import Moment
from flask_migrate import Migrate, show
import logging
from logging import Formatter, FileHandler
from flask_wtf import CSRFProtect
from flask_wtf.csrf import CSRFError
from http import HTTPStatus

from misc import get_config, print_exc_info, set_config

#----------------------------------------------------------------------------#
# App Config.
#----------------------------------------------------------------------------#

app = Flask(__name__)
moment = Moment(app)
app.config.from_object('config')
set_config(app.config)

ORM = get_config("USE_ORM")

if ORM:
    from models import SQLAlchemyDB as db

    db.init_app(app)

    migrate = Migrate(app, db)
else: # ENGINE
    from engine import setup, execute

    setup()

# https://nickjanetakis.com/blog/fix-missing-csrf-token-issues-with-flask
csrf = CSRFProtect()
csrf.init_app(app)

#----------------------------------------------------------------------------#
# Route Config.
#----------------------------------------------------------------------------#

from controllers import (shows, create_show_submission, 
                      artists, search_artists, search_artists_advanced, show_artist, 
                        edit_artist, delete_artist, artist_availability, create_artist_submission,
                      venues, search_venues, search_venues_advanced, show_venue, 
                        create_venue_submission, delete_venue, edit_venue_submission, venue_bookings
                      )

app.add_url_rule('/shows/create', view_func=create_show_submission, methods=['POST', 'GET'])
app.add_url_rule('/shows', view_func=shows, methods=['GET'])

app.add_url_rule('/artists', view_func=artists, methods=['GET'])
app.add_url_rule('/artists/search', view_func=search_artists, methods=['POST'])
app.add_url_rule('/artists/advanced_search', view_func=search_artists_advanced, methods=['GET', 'POST'])
app.add_url_rule('/artists/<int:artist_id>', view_func=show_artist, methods=['GET'])
app.add_url_rule('/artists/<int:artist_id>/edit', view_func=edit_artist, methods=['POST', 'GET'])
app.add_url_rule('/artists/<int:artist_id>', view_func=delete_artist, methods=['DELETE'])
app.add_url_rule('/artists/<int:artist_id>/availability', view_func=artist_availability, methods=['GET'])
app.add_url_rule('/artists/create', view_func=create_artist_submission, methods=['POST', 'GET'])

app.add_url_rule('/venues', view_func=venues, methods=['GET'])
app.add_url_rule('/venues/search', view_func=search_venues, methods=['POST'])
app.add_url_rule('/venues/advanced_search', view_func=search_venues_advanced, methods=['GET', 'POST'])
app.add_url_rule('/venues/<int:venue_id>', view_func=show_venue, methods=['GET'])
app.add_url_rule('/venues/create', view_func=create_venue_submission, methods=['POST', 'GET'])
app.add_url_rule('/venues/<int:venue_id>', view_func=delete_venue, methods=['DELETE'])
app.add_url_rule('/venues/<int:venue_id>/edit', view_func=edit_venue_submission, methods=['POST', 'GET'])
app.add_url_rule('/venues/<int:venue_id>/bookings', view_func=venue_bookings, methods=['GET'])

#----------------------------------------------------------------------------#
# Models.
#----------------------------------------------------------------------------#
if ORM:
    from models import Venue, Artist
else: # ENGINE
    from models import ARTIST_TABLE, VENUE_TABLE

#----------------------------------------------------------------------------#
# Filters.
#----------------------------------------------------------------------------#

def format_datetime(value, format='medium'):
  date = dateutil.parser.parse(value)
  if format == 'full':
      format="EEEE MMMM, d, y 'at' h:mma"
  elif format == 'medium':
      format="EE MM, dd, y h:mma"
  return babel.dates.format_datetime(date, format)

app.jinja_env.filters['datetime'] = format_datetime

#----------------------------------------------------------------------------#
# Controllers.
#----------------------------------------------------------------------------#

@app.route('/')
def index():
    num_latest = get_config("NUM_LATEST_ON_HOME")
    try:
        if ORM:
            latest_artists = Artist.query\
                                    .with_entities(Artist.id, Artist.name)\
                                    .order_by(Artist.id.desc())\
                                    .limit(num_latest)
            latest_venues = Venue.query\
                                    .with_entities(Venue.id, Venue.name)\
                                    .order_by(Venue.id.desc())\
                                    .limit(num_latest)
        else: # ENGINE
            latest_artists = execute(f'SELECT id, name FROM "{ARTIST_TABLE}" ORDER BY id DESC LIMIT {num_latest};')
            latest_venues = execute(f'SELECT id, name FROM "{VENUE_TABLE}" ORDER BY id DESC LIMIT {num_latest};')
    except:
        print_exc_info()
        abort(HTTPStatus.INTERNAL_SERVER_ERROR.value)
       
    artists = [{'id': a.id, 'name': a.name} for a in latest_artists]
    venues = [{'id': v.id, 'name': v.name} for v in latest_venues]
    return render_template('pages/home.html', artists=artists, venues=venues)


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

#----------------------------------------------------------------------------#
# Launch.
#----------------------------------------------------------------------------#

# Default port:
if __name__ == '__main__':
    app.run()

# Or specify port manually:
'''
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
'''
