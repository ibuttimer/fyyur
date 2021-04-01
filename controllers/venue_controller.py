#----------------------------------------------------------------------------#
# Imports
#----------------------------------------------------------------------------#
from datetime import timedelta
from flask import render_template, request, Response, flash, url_for, jsonify, Markup
from sqlalchemy import and_, func

from queries import *
from .controllers_misc import *

from forms import (populate_genred_model, VenueForm, NCSSearchForm, 
                    APP_DATETIME_FMT, APP_DATE_FMT, APP_TIME_FMT)
from misc import get_config, print_exc_info

_BOOKING_BY_VENUE_KEYS = ['start_time', 'duration', 'name'] 
# keys to extract data for db results
BOOKING_BY_VENUE_KEYS = {p: p for p in _BOOKING_BY_VENUE_KEYS}

if get_config("USE_ORM"):
  from models import SQLAlchemyDB as db, Venue, Show
  ORM = True

  # # keys to extract data for db results
  # BOOKING_BY_VENUE_KEYS = {_BOOKING_BY_VENUE_KEYS[p]: p for p in range(len(_BOOKING_BY_VENUE_KEYS))}

else:
  from engine import execute, execute_transaction
  from models import (VENUE_TABLE, SHOWS_TABLE, VENUE_GENRES_TABLE, 
                      new_model_dict, dict_disjoint, equal_dict)
  from http import HTTPStatus
  ORM = False

ENGINE = not ORM


def venues():
  '''
  List all venues
  '''
  data = []

  if ORM:
    cities_states = Venue.query.with_entities(Venue.state, Venue.city).distinct().all()
    for city_state in cities_states:
      venues = Venue.query.with_entities(Venue.id, Venue.name)\
                    .filter(and_(Venue.state == city_state.state, Venue.city == city_state.city))\
                    .all()

      data.append({
        "state": city_state[0],
        "city": city_state[1],
        "venues": entity_shows(venues, Show.venue_id)
      })
  else: # ENGINE
    cities_states = execute(f'SELECT DISTINCT state, city from "{VENUE_TABLE}";')
    for city_state in cities_states:
      city = city_state["city"]
      state = city_state["state"]
      venues = execute(f'SELECT DISTINCT id, name from "{VENUE_TABLE}" WHERE state = \'{state}\' AND city = \'{city}\';')
      data.append({
        "state": state,
        "city": city,
        "venues": entity_shows(venues, 'venue_id')
      })

  return render_template('pages/venues.html', areas=data)


def search_venues():
  '''
  Perform search on venues.

  Request query parameters:
  mode:   search query mode; one of 'basic', 'advanced' or 'all'
  '''
  mode = request.args.get('mode', default=SEARCH_BASIC)

  form = NCSSearchForm()

  return render_template('pages/search_venues.html', 
                          results = venues_search(mode, form), 
                          title = 'Fyyur | Venues Search',
                          form = form)


def search_venues_advanced():
  '''
  Perform advanced search on venues
  '''
  form = NCSSearchForm()

  if request.method == 'POST':
    results = venues_search(SEARCH_ADVANCED, form)
  else:
    results = {
    "count": 0,
    "data": [],
    "search_term": "",
    "mode": 'none'
  }

  return render_template('pages/search_venues.html', 
                          results = results, 
                          title = 'Fyyur | Venues Search',
                          form = form)


def show_venue(venue_id: int):
  '''
  Show the venue page with the given venue_id
  venue_id:   id of venue 
  '''
  if ORM:
    venue = get_music_entity_with_show_summary(venue_id, Venue, shows_by_venue)
  else: # ENGINE
    venue = get_music_entity_with_show_summary(venue_id, VENUE_TABLE, shows_by_venue, VENUE_GENRES_TABLE, 'venue_id')

  return render_template('pages/show_venue.html', venue=venue)


def populate_venue(venue, form):
  '''
  Populate a venue from a form
  '''
  property_list = model_property_list(venue if ORM else VENUE_TABLE, IGNORE_ID_GENRES)
  return populate_genred_model(venue, form, property_list)


def update_venue_orm(venue_id: int, form):
  '''
  Update a venue in ORM mode
  venue_id: id of the venue to update
  '''
  commit_change = False

  venue = Venue.query.filter(Venue.id==venue_id).first_or_404()
  venue_name = venue.name

  updated_venue = populate_venue(Venue(), form)
  if not updated_venue.equal(venue, IGNORE_ID):
    # change has occured update venue
    populate_venue(venue, form)
    commit_change = True

  try:
      if commit_change:
        db.session.commit()
        success = True
      else:
        success = None
  except:
      db.session.rollback()
      print_exc_info()
      success = False
  finally:
      db.session.close()

  return success, venue_name


def update_venue_engine(venue: dict, form):
  '''
  Update an venue in ENGINE mode
  venue:  base venue
  '''
  stmts = []
  venue_id = venue["id"]

  updated_venue = populate_venue(new_model_dict(VENUE_TABLE), form)
  if not equal_dict(venue, updated_venue, IGNORE_ID):
    # change has occured update venue
    to_set = [f'{k}=\'{v}\'' for k, v in updated_venue.items() 
                              if k in dict_disjoint(venue, updated_venue, IGNORE_ID_GENRES)]
    if len(to_set) > 0:
      to_set = ", ".join(to_set)
      stmts.append(f'UPDATE "{VENUE_TABLE}" SET {to_set} WHERE id={venue_id};')

    # update genre link table
    if updated_venue["genres"] != venue["genres"]:
      for stmt in genre_changes_engine(venue["genres"], updated_venue["genres"], 
                                        venue_id, VENUE_GENRES_TABLE, 'venue_id'):
        stmts.append(stmt)

  return exec_transaction_engine(stmts, updated_venue["name"])


def edit_venue_submission(venue_id: int):
  '''
  Edit a venue
  venue_id: id of the venue to edit
  '''
  if ORM:
    venue = get_music_entity(venue_id, Venue, shows_by_venue)
  else: # ENGINE
    venue = get_music_entity(venue_id, VENUE_TABLE, shows_by_venue, VENUE_GENRES_TABLE, 'venue_id')
  model = MultiDict(venue)

  if request.method == 'GET':
    form = VenueForm(formdata=model)
    genres = model.getlist("genres")
  else: # ENGINE
    form = VenueForm()
    genres = form.genres.data

  # set choices & validators based on possible options
  set_genre_field_options(form.genres, genres)

  if request.method == 'POST' and form.validate_on_submit():

    if ORM:
      success, venue_name = update_venue_orm(venue_id, form)
    else: # ENGINE
      success, venue_name = update_venue_engine(venue, form)

    return update_result(success, venue_name, 'Venue', url_for('show_venue', venue_id=venue_id))

  return render_template('forms/edit_venue.html', 
                  form=form, 
                  venue_name=model["name"],
                  title= 'Edit Venue',
                  submit_action=url_for('edit_venue_submission', venue_id=venue_id),
                  cancel_url=url_for('show_venue', venue_id=venue_id),
                  submit_text='Update',
                  submit_title='Update venue'
    )
 

def delete_venue_orm(venue_id: int):
  '''
  Delete an venue in ORM mode
  venue_id: id of the venue to delete
  '''
  venue = Venue.query.filter(Venue.id==venue_id).first_or_404()
  venue_name = venue.name
  try:
      # when an venue is deleted, need to delete shows as well to keep the db consistent
      shows = Show.query.filter(Show.venue_id==venue_id).all()

      for show in shows:
        db.session.delete(show)
      db.session.delete(venue)
      db.session.commit()
      success = True
  except:
      db.session.rollback()
      print_exc_info()
      success = False
  finally:
      db.session.close()

  return success, venue_name


def delete_venue_engine(venue_id: int):
  '''
  Delete a venue in ENGINE mode
  venue_id: id of the venue to delete
  '''
  venue_name = None
  exists = False;
  try:
    venue = execute(f'SELECT name from "{VENUE_TABLE}" WHERE id = {venue_id};')
    if venue.rowcount != 0:
      exists = True
      venue_name = venue.mappings().first().get('name')

      # when an venue is deleted, need to delete genres & shows as well to keep the db consistent
      execute_transaction([
        f'DELETE FROM "{SHOWS_TABLE}" WHERE venue_id = {venue_id};',
        f'DELETE FROM "{VENUE_GENRES_TABLE}" WHERE venue_id = {venue_id};',
        f'DELETE FROM "{VENUE_TABLE}" WHERE id = {venue_id};'
      ])
      success = True
  except:
    print_exc_info()
    success = False

  if not exists:
    abort(HTTPStatus.NOT_FOUND.value)

  return success, venue_name


def delete_venue(venue_id: int):
  '''
  Delete a venue
  venue_id: id of the venue to delete
  '''
  if ORM:
    success, venue_name = delete_venue_orm(venue_id)
  else: # ENGINE
    success, venue_name = delete_venue_engine(venue_id)

  return delete_result(success, venue_name, 'Venue')


def create_venue_orm(venue: Model):
  '''
  Create an venue in ORM mode
  venue:  venue to create
  '''
  venue_name = venue.name
  try:
      db.session.add(venue)
      db.session.commit()
      success = True
  except:
      db.session.rollback()
      print_exc_info()
      success = False
  finally:
      db.session.close()

  return success, venue_name


def venue_insert_sql(venue: dict):
  ''' Generate venue insert SQL'''
  properties = model_property_list(VENUE_TABLE, IGNORE_ID)
  properties_list = ', '.join(properties)
  value_dict = {p: "'"+venue[p]+"'" for p in properties if p != 'seeking_talent'}
  value_dict['seeking_talent'] = 'TRUE' if venue['seeking_talent'] else 'FALSE'
  values = [value_dict[p] for p in properties]
  values_list = ', '.join(values)

  return f'INSERT INTO "{VENUE_TABLE}"({properties_list}) VALUES ({values_list});'


def id_name_by_unique_properties_sql(name, address, city, state):
    return f'SELECT id, name from "{VENUE_TABLE}" WHERE LOWER(name) = LOWER(\'{name}\') ' \
                        f'AND LOWER(address) = LOWER(\'{address}\') ' \
                        f'AND LOWER(city) = LOWER(\'{city}\') AND state = \'{state}\';'


def create_venue_engine(venue: dict):
  '''
  Create an venue in ENGINE mode
  venue: venue to create
  '''
  success = False
  venue_name = venue["name"]
  try:
    new_venue = execute(venue_insert_sql(venue))
    if new_venue.rowcount > 0:
      # using raw sql so need to query to get new id
      new_venue = execute(
        id_name_by_unique_properties_sql(venue["name"], venue["address"], venue["city"], venue["state"])
      )
      if new_venue.rowcount > 0:
        new_venue = new_venue.fetchone()
        venue_id = new_venue["id"]

        stmts = []
        # add genres
        for stmt in genre_changes_engine([], venue["genres"], 
                                    venue_id, VENUE_GENRES_TABLE, 'venue_id'):
          stmts.append(stmt)

        execute_transaction(stmts)
        success = True
  except:
    print_exc_info()

  return success, venue_name


def create_venue_submission():
  '''
  Create a venue
  '''
  form = VenueForm()
  if request.method == 'POST':
    genres = form.genres.data
  else:
    genres = list()

  # set choices & validators based on possible options
  set_genre_field_options(form.genres, genres)

  if request.method == 'POST' and form.validate_on_submit():

    venue = populate_venue(Venue() if ORM else new_model_dict(VENUE_TABLE), form)

    # check for existing artist
    venue_id = None
    if ORM:
      existing = Venue.query\
                  .with_entities(Venue.id, Venue.name)\
                  .filter(and_(func.lower(Venue.name) == func.lower(venue.name), 
                                  func.lower(Venue.city) == func.lower(venue.city), 
                                  func.lower(Venue.address) == func.lower(venue.address), 
                                  Venue.state == venue.state))\
                  .first()
      if existing is not None:
        venue_id = existing.id
        venue_name = existing.name
    else: # ENGINE
      existing = execute(
        id_name_by_unique_properties_sql(venue["name"], venue["address"], venue["city"], venue["state"])
      )
      if existing.rowcount > 0:
        hit = existing.mappings().first()
        venue_id = hit.get('id')
        venue_name = hit.get('name')

    if venue_id is not None:
      url = url_for('show_venue', venue_id=venue_id)
      flash(Markup(f'A listing for {venue_name} already exists! '\
                    f'Please see <a href="{url}">{venue_name}</a>.'))
    else:
      # add venue
      if ORM:
        success, venue_name = create_venue_orm(venue)
      else: # ENGINE
        success, venue_name = create_venue_engine(venue)

      return create_result(success, venue_name, 'Venue')

  return render_template('forms/edit_venue.html', 
                  form=form, 
                  title= 'Create Venue',
                  submit_action=url_for('create_venue_submission'),
                  cancel_url=url_for('index'),
                  submit_text='Create',
                  submit_title='Create venue'
    )


def datetime_to_str(date_time: datetime) -> str:
  return date_time.strftime(APP_DATETIME_FMT)


def date_to_str(date_time: datetime) -> str:
  return date_time.strftime(APP_DATE_FMT)


def time_to_str(date_time: datetime) -> str:
  return date_time.strftime(APP_TIME_FMT)


def bookings_by_venue(venue_id, query_date):
  '''
  Search for a venues's bookings
  venue_id:   id of venue
  criterion:  filtering criterion
  '''
  try:
    if ORM:
      query = Show.query.join(Venue, Show.venue_id == Venue.id)\
                      .join(Artist, Show.artist_id == Artist.id)\
                      .with_entities(Show.start_time, Show.duration, Artist.name)
      if query_date is not None:
        query = query.filter(and_(Show.venue_id == venue_id, Show.start_date == query_date))
      else:
        query = query.filter(Show.venue_id == venue_id)\
                      .order_by(Show.start_date)
      bookings = query.all()

    else: # ENGINE
      sql = f'SELECT "{SHOWS_TABLE}".start_time, "{SHOWS_TABLE}".duration, "{ARTIST_TABLE}".name '\
            f'FROM (("{SHOWS_TABLE}" '\
            f'INNER JOIN "{VENUE_TABLE}" ON "{SHOWS_TABLE}".venue_id = "{VENUE_TABLE}".id) '\
            f'INNER JOIN "{ARTIST_TABLE}" ON "{SHOWS_TABLE}".artist_id = "{ARTIST_TABLE}".id) '\
            f'WHERE "{SHOWS_TABLE}".venue_id = {venue_id}'
      if query_date is not None:
        sql = f'{sql} AND DATE("{SHOWS_TABLE}".start_time) = \'{date_to_str(query_date)}\''
      else:
        sql = f'{sql} ORDER BY "{SHOWS_TABLE}".start_time'
      sql = sql + ';'

      bookings = execute(sql).mappings().fetchall()

  except:
      print_exc_info()
      abort(HTTPStatus.INTERNAL_SERVER_ERROR.value)

  # [{'start_time': ?, 'duration' ?, ...}, {}, ...] }
  return [{k: show[BOOKING_BY_VENUE_KEYS[v]] for k, v in BOOKING_BY_VENUE_KEYS.items()} for show in bookings]


def venue_bookings(venue_id: int):
  '''
  Get a venue's bookings
  venue_id: id of the venue

  Request query parameters:
  query_date:   search query date in form 'YYYY-MM-DD HH:MM)'
  '''
  # venue exists check
  query_date = get_availability_date(
                  request.args.get('query_date', default=None))

  exists_or_404(Venue if ORM else VENUE_TABLE, venue_id)

  bookings = bookings_by_venue(venue_id, query_date)

  bookings_list = []
  if bookings is not None:
    bookings_list = [f'{b["name"]} {time_to_str(b["start_time"])}-'\
                      f'{time_to_str(b["start_time"]+timedelta(minutes=b["duration"]))}' for b in bookings]

  return jsonify({
    'bookings': bookings_list
  })
