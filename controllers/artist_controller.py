#----------------------------------------------------------------------------#
# Imports
#----------------------------------------------------------------------------#
from datetime import time
from engine import transaction
from flask import render_template, request, flash, url_for, jsonify, Markup, abort

from queries import *
from misc import current_datetime, get_config, print_exc_info
from .controllers_misc import *

from forms import (populate_genred_model, populate_model, ArtistForm, NCSSearchForm, 
                      AVAILABILITY_FROM_DATE_FMT, AVAILABILITY_TIME_FMT)
from models import is_available_time_key, is_available, model_items


if get_config("USE_ORM"):
  from sqlalchemy import and_, func
  from models import SQLAlchemyDB as db, Artist, Show, Availability
  ORM = True
else:
  from engine import execute, execute_transaction
  from models import (ARTIST_TABLE, AVAILABILITY_TABLE, ARTIST_GENRES_TABLE, 
                      equal_dict, dict_disjoint, new_model_dict)
  from http import HTTPStatus
  ORM = False

ENGINE = not ORM


def artists():
  '''
  List all artists
  '''
  form = NCSSearchForm()

  return render_template('pages/artists.html', 
                          results = artists_search(SEARCH_ALL, form), 
                          title = 'Fyyur | Artists',
                          form = form)

def search_artists():
  '''
  Perform search on artists.

  Request query parameters:
  mode:   search query mode; one of 'basic', 'advanced' or 'all'
  '''
  mode = request.args.get('mode', default=SEARCH_BASIC)

  form = NCSSearchForm()

  return render_template('pages/artists.html', 
                          results = artists_search(mode, form), 
                          title = 'Fyyur | Artists Search',
                          form = form)


def search_artists_advanced():
  '''
  Perform advanced search on artists
  '''
  form = NCSSearchForm()

  if request.method == 'POST':
    results = artists_search(SEARCH_ADVANCED, form)
  else:
    results = {
    "count": 0,
    "data": [],
    "search_term": "",
    "mode": 'none'
  }

  return render_template('pages/artists.html', 
                          results = results, 
                          title = 'Fyyur | Artists Search',
                          form = form)


def availability_by_artist(artist_id: int, from_date=None, as_type=EntityResult.DICT) -> Union[dict, Model, None]:
  '''
  Search for an artist's latest availability
  artist_id:  id of artist 
  from_date:  filtering criterion
  as:         result
  '''
  if from_date is None:
    from_date = datetime.today()
  try:
    if ORM:
      availability = Availability.query.join(Artist, Availability.artist_id == Artist.id)\
                          .filter(and_(Availability.artist_id == artist_id), Availability.from_date < from_date)\
                          .order_by(Availability.from_date.desc(), Availability.id.desc())\
                          .first()
      if availability is not None and as_type != EntityResult.MODEL:
        availability = availability.get_dict()
              
    else: # ENGINE
      properties = ['"'+AVAILABILITY_TABLE+'".'+p for p in get_model_property_list(AVAILABILITY_TABLE)]
      properties = ', '.join(properties)
      result = execute(f'SELECT {properties} FROM "{AVAILABILITY_TABLE}" '\
              f'INNER JOIN "{ARTIST_TABLE}" ON "{AVAILABILITY_TABLE}".artist_id = "{ARTIST_TABLE}".id '\
              f'WHERE "{AVAILABILITY_TABLE}".artist_id = {artist_id} AND "{AVAILABILITY_TABLE}".from_date < TIMESTAMP \'{from_date}\' '\
              f'ORDER BY "{AVAILABILITY_TABLE}".from_date DESC, "{AVAILABILITY_TABLE}".id DESC;')
      if result.rowcount == 0:
        availability = None
      else:
        entry = result.mappings().first()
        availability = {k: entry.get(k) for k in entry.keys()}
  except:
      print_exc_info()
      abort(HTTPStatus.INTERNAL_SERVER_ERROR.value)

  return availability


def show_artist(artist_id: int):
  '''
  Show the artist page with the given artist_id
  artist_id:   id of artist 
  '''
  if ORM:
    artist = get_music_entity_with_show_summary(artist_id, Artist, shows_by_artist)
  else: # ENGINE
    artist = get_music_entity_with_show_summary(artist_id, ARTIST_TABLE, shows_by_artist, ARTIST_GENRES_TABLE, 'artist_id')

  availability = availability_by_artist(artist_id)
  if availability is not None:
    count = 0
    for key in availability.keys():
      if (is_available_time_key(key)) and availability[key] is not None:
        availability[key] = availability[key].isoformat(timespec='minutes')
        count = count + 1
    if count == 0:
      availability = None
  else:
    availability = None
  artist["availability"] = availability

  return render_template('pages/show_artist.html', artist=artist)


def populate_artist(artist, form):
  '''
  Populate an artist from a form
  '''
  property_list = model_property_list(artist if ORM else ARTIST_TABLE, IGNORE_ID_GENRES)
  return populate_genred_model(artist, form, property_list)


IGNORE_AVAILABILITY = ["id", "artist_id"]

def populate_availability(availability, form):
  '''
  Populate an availability from a form
  '''
  property_list = model_property_list(availability if ORM else AVAILABILITY_TABLE, IGNORE_AVAILABILITY)
  return populate_model(availability, form, property_list)


IGNORE_ID_DATE = ['id', 'from_date']

def update_artist_orm(artist_id: int, form, availability):
  '''
  Update an artist in ORM mode
  artist_id: id of the artist to update
  '''
  commit_change = False

  artist = Artist.query.filter(Artist.id==artist_id).first_or_404()
  artist_name = artist.name

  updated_artist = populate_artist(Artist(), form)
  if not updated_artist.equal(artist, IGNORE_ID):
    # change has occured update artist
    populate_artist(artist, form)
    artist_name = artist.name
    commit_change = True

  new_availability = populate_availability(Availability(), form)
  new_availability.artist_id = artist_id

  try:
      if is_available(availability) != is_available(new_availability) or \
            not availability.equal(new_availability, IGNORE_ID_DATE):
        # availability has changed, add new setting
        db.session.add(new_availability)
        commit_change = True

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

  return success, artist_name


def datetime_to_str(date_time: datetime) -> str:
  return date_time.strftime(AVAILABILITY_FROM_DATE_FMT)


def time_to_str(t_time: Union[datetime, time]) -> str:
  return t_time.strftime(AVAILABILITY_TIME_FMT)


def availability_insert_sql(artist_id: int, availability: dict):
  ''' Generate availability insert SQL'''
  properties = model_property_list(AVAILABILITY_TABLE, IGNORE_ID)
  properties_list = ', '.join(properties)
  value_dict = {
    'artist_id': str(artist_id),
    'from_date': "'"+datetime_to_str(availability["from_date"])+"'"
  }
  value_dict = {**value_dict, **{
    p: "'"+time_to_str(availability[p])+"'" for p in properties if p != 'artist_id' and p != 'from_date'
  }}
  values = [value_dict[p] for p in properties]
  values_list = ', '.join(values)

  return f'INSERT INTO "{AVAILABILITY_TABLE}"({properties_list}) VALUES ({values_list});'


def update_artist_engine(artist: dict, form, availability):
  '''
  Update an artist in ENGINE mode
  artist: base artist
  '''
  stmts = []
  artist_id = artist["id"]

  updated_artist = populate_artist(new_model_dict(ARTIST_TABLE), form)
  if not equal_dict(artist, updated_artist, IGNORE_ID):
    # change has occured update artist
    to_set = [f'{k}=\'{v}\'' for k, v in updated_artist.items() 
                              if k in dict_disjoint(artist, updated_artist, IGNORE_ID_GENRES)]
    if len(to_set) > 0:
      to_set = ", ".join(to_set)
      stmts.append(f'UPDATE "{ARTIST_TABLE}" SET {to_set} WHERE id={artist_id};')

    # update genre link table
    if updated_artist["genres"] != artist["genres"]:
      for stmt in genre_changes_engine(artist["genres"], updated_artist["genres"], 
                                        artist_id, ARTIST_GENRES_TABLE, 'artist_id'):
        stmts.append(stmt)

  new_availability = populate_availability(new_model_dict(AVAILABILITY_TABLE), form)
  new_availability["artist_id"] = artist_id

  if is_available(availability) != is_available(new_availability) or \
        not equal_dict(availability, new_availability, IGNORE_ID_DATE):
    # availability has changed, add new setting
    stmts.append(availability_insert_sql(artist_id, new_availability))
  
  return exec_transaction_engine(stmts, updated_artist["name"])


def edit_artist(artist_id: int):
  '''
  Edit an artist
  artist_id: id of the artist to edit
  '''
  if ORM:
    artist = get_music_entity(artist_id, Artist, shows_by_artist)
    as_type = EntityResult.MODEL # availability as a model
    no_availability = Availability()
  else: # ENGINE
    artist = get_music_entity(artist_id, ARTIST_TABLE, shows_by_artist, ARTIST_GENRES_TABLE, 'artist_id')
    as_type = EntityResult.DICT # availability as a dict
    no_availability = dict()
  model = MultiDict(artist)

  availability = availability_by_artist(artist_id, as_type=as_type)
  if availability is None:
    availability = no_availability

  if request.method == 'GET':
    for key, value in model_items(availability, ignore=IGNORE_AVAILABILITY):
      if key == 'from_date':
        model.add(key, datetime_to_str(current_datetime()))
      elif is_available_time_key(key) and value is not None:
        model.add(key, time_to_str(value))

    form = ArtistForm(formdata=model)
    genres = model.getlist("genres")

  else:
    form = ArtistForm()
    genres = form.genres.data

  # set choices & validators based on possible options
  set_genre_field_options(form.genres, genres)

  if request.method == 'POST' and form.validate_on_submit():

    if ORM:
      success, artist_name = update_artist_orm(artist_id, form, availability)
    else: # ENGINE
      success, artist_name = update_artist_engine(artist, form, availability)

    return update_result(success, artist_name, 'Artist', url_for('show_artist', artist_id=artist_id))

  return render_template('forms/edit_artist.html', 
                  form=form, 
                  artist_name=model["name"],
                  title= 'Edit Artist',
                  submit_action=url_for('edit_artist', artist_id=artist_id),
                  cancel_url=url_for('show_artist', artist_id=artist_id),
                  submit_text='Update',
                  submit_title='Update artist'
    )


def delete_artist_orm(artist_id: int):
  '''
  Delete an artist in ORM mode
  artist_id: id of the artist to delete
  '''
  artist = Artist.query.filter(Artist.id==artist_id).first_or_404()
  artist_name = artist.name
  try:
      # when an artist is deleted, need to delete availability & shows as well to keep the db consistent
      availability = Availability.query.filter(Availability.artist_id==artist_id).all()
      shows = Show.query.filter(Show.artist_id==artist_id).all()

      for available in availability:
        db.session.delete(available)
      for show in shows:
        db.session.delete(show)
      db.session.delete(artist)
      db.session.commit()
      success = True
  except:
      db.session.rollback()
      print_exc_info()
      success = False
  finally:
      db.session.close()

  return success, artist_name


def delete_artist_engine(artist_id: int):
  '''
  Delete an artist in ENGINE mode
  artist_id: id of the artist to delete
  '''
  artist_name = None
  exists = False
  try:
    artist = execute(f'SELECT name from "{ARTIST_TABLE}" WHERE id = {artist_id};')
    if artist.rowcount != 0:
      exists = True
      artist_name = artist.mappings().first().get('name')

      # when an artist is deleted, need to delete availability, genres & shows as well to keep the db consistent
      execute_transaction([
        f'DELETE FROM "{AVAILABILITY_TABLE}" WHERE artist_id = {artist_id};',
        f'DELETE FROM "{SHOWS_TABLE}" WHERE artist_id = {artist_id};',
        f'DELETE FROM "{ARTIST_GENRES_TABLE}" WHERE artist_id = {artist_id};',
        f'DELETE FROM "{ARTIST_TABLE}" WHERE id = {artist_id};'
      ])
      success = True
  except:
    print_exc_info()
    success = False

  if not exists:
    abort(HTTPStatus.NOT_FOUND.value)

  return success, artist_name


def delete_artist(artist_id: int):
  '''
  Delete an artist
  artist_id: id of the artist to delete
  '''
  if ORM:
    success, artist_name = delete_artist_orm(artist_id)
  else: # ENGINE
    success, artist_name = delete_artist_engine(artist_id)

  return delete_result(success, artist_name, 'Artist')


def create_artist_orm(artist, availability):
  '''
  Create an artist in ORM mode
  artist:   artist to create
  '''
  artist_name = artist.name
  try:
      db.session.add(artist)
      db.session.commit()

      if availability.is_available():
        availability.artist_id = artist.id
        db.session.add(availability)
        db.session.commit()

      success = True
  except:
      db.session.rollback()
      print_exc_info()
      success = False
  finally:
      db.session.close()

  return success, artist_name


def artist_insert_sql(artist: dict):
  ''' Generate artist insert SQL'''
  properties = model_property_list(ARTIST_TABLE, IGNORE_ID)
  properties_list = ', '.join(properties)
  value_dict = {p: "'"+artist[p]+"'" for p in properties if p != 'seeking_venue'}
  value_dict['seeking_venue'] = 'TRUE' if artist['seeking_venue'] else 'FALSE'
  values = [value_dict[p] for p in properties]
  values_list = ', '.join(values)

  return f'INSERT INTO "{ARTIST_TABLE}"({properties_list}) VALUES ({values_list});'


def id_name_by_unique_properties_sql(name, city, state):
    return f'SELECT id, name from "{ARTIST_TABLE}" WHERE LOWER(name) = LOWER(\'{name}\') ' \
                        f'AND LOWER(city) = LOWER(\'{city}\') AND state = \'{state}\';'


def create_artist_engine(artist: dict, availability: dict):
  '''
  Create an artist in ENGINE mode
  artist: artist to create
  '''
  success = False
  artist_name = artist["name"]
  try:
    new_artist = execute(artist_insert_sql(artist))
    if new_artist.rowcount > 0:
      # using raw sql so need to query to get new id
      new_artist = execute(
        id_name_by_unique_properties_sql(artist["name"], artist["city"], artist["state"])
      )
      if new_artist.rowcount > 0:
        new_artist = new_artist.fetchone()
        artist_id = new_artist["id"]

        stmts = []
        # add genres
        for stmt in genre_changes_engine([], artist["genres"], 
                                    artist_id, ARTIST_GENRES_TABLE, 'artist_id'):
          stmts.append(stmt)

        if is_available(availability):
          stmts.append(availability_insert_sql(artist_id, availability))

        execute_transaction(stmts)
        success = True
  except:
    print_exc_info()

  return success, artist_name


def create_artist_submission():
  '''
  Create an artist
  '''
  form = ArtistForm()
  if request.method == 'POST':
    genres = form.genres.data
  else:
    genres = list()

  # set choices & validators based on possible options
  set_genre_field_options(form.genres, genres)

  if request.method == 'POST' and form.validate_on_submit():
    if ORM:
      blank_artist = Artist()
      blank_availability = Availability()
    else: # ENGINE
      blank_artist = new_model_dict(ARTIST_TABLE)
      blank_availability = new_model_dict(AVAILABILITY_TABLE)

    artist = populate_artist(blank_artist, form)
    availability = populate_availability(blank_availability, form)

    # check for existing artist
    artist_id = None
    if ORM:
      existing = Artist.query\
                  .with_entities(Artist.id, Artist.name)\
                  .filter(and_(func.lower(Artist.name) == func.lower(artist.name), 
                                  func.lower(Artist.city) == func.lower(artist.city), 
                                  Artist.state == artist.state))\
                  .first()
      if existing is not None:
        artist_id = existing.id
        artist_name = existing.name
    else: # ENGINE
      existing = execute(
        id_name_by_unique_properties_sql(artist["name"], artist["city"], artist["state"])
      )
      if existing.rowcount > 0:
        hit = existing.mappings().first()
        artist_id = hit.get('id')
        artist_name = hit.get('name')
        
    if artist_id is not None:
      url = url_for('show_artist', artist_id=artist_id)
      flash(Markup(f'A listing for {artist_name} already exists! '\
                    f'Please see <a href="{url}">{artist_name}</a>.'))
    else:
      # add artist
      if ORM:
        success, artist_name = create_artist_orm(artist, availability)
      else: # ENGINE
        success, artist_name = create_artist_engine(artist, availability)

      return create_result(success, artist_name, 'Artist')

  return render_template('forms/edit_artist.html', 
                  form=form, 
                  title= 'Create Artist',
                  submit_action=url_for('create_artist_submission'),
                  cancel_url=url_for('index'),
                  submit_text='Create',
                  submit_title='Create artist'
    )


def artist_availability(artist_id: int):
  '''
  Get an artist's availability
  artist_id: id of the artist

  Request query parameters:
  query_date:   search query date in form 'YYYY-MM-DD HH:MM)'
  '''
  # artist exists check
  exists_or_404(Artist if ORM else ARTIST_TABLE, artist_id)

  query_date = get_availability_date(
                  request.args.get('query_date', default=None))

  availability = availability_by_artist(artist_id, query_date)

  available_times = []
  if availability is not None:
    for from_time, to_time, day in [
                          (availability["mon_from"], availability["mon_to"], 'Monday'),
                          (availability["tue_from"], availability["tue_to"], 'Tuesday'),
                          (availability["wed_from"], availability["wed_to"], 'Wednesday'),
                          (availability["thu_from"], availability["thu_to"], 'Thursday'),
                          (availability["fri_from"], availability["fri_to"], 'Friday'),
                          (availability["sat_from"], availability["sat_to"], 'Saturday'),
                          (availability["sun_from"], availability["sun_to"], 'Sunday')]:
      if from_time is not None and to_time is not None:
        available_times.append(f'{day} '\
            f'{time_to_str(from_time)}-{time_to_str(to_time)}')

  return jsonify({
    'availability': available_times
  })

