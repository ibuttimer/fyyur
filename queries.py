#----------------------------------------------------------------------------#
# Imports
#----------------------------------------------------------------------------#
from datetime import datetime
from http import HTTPStatus
from flask import request, abort

from misc import get_config, print_exc_info

#----------------------------------------------------------------------------#
# Models.
#----------------------------------------------------------------------------#
_SHOWS_BY_KEYS = ['id', 'start_time', 'name', 'image_link']

if get_config("USE_ORM"):
  from sqlalchemy import and_
  from models import Venue, Artist, Show, Genre
  ORM = True

  SHOWS_BY_KEYS = {_SHOWS_BY_KEYS[p]: p for p in range(len(_SHOWS_BY_KEYS))}
else:
  from engine import execute
  from models import ARTIST_TABLE, VENUE_TABLE, SHOWS_TABLE, GENRES_TABLE
  ORM = False

  SHOWS_BY_ARTIST_KEYS = {k: f'venue_{k}' if k == 'id' else k for k in _SHOWS_BY_KEYS}
  SHOWS_BY_VENUE_KEYS = {k: f'artist_{k}' if k == 'id' else k for k in _SHOWS_BY_KEYS}

ENGINE = not ORM


CITY_STATE_SEARCH_SEPARATOR = ','
SEARCH_BASIC = 'basic'
SEARCH_ADVANCED = 'advanced'
SEARCH_ALL = 'all'

def name_city_state_search(mode, form, entity_class, show_field):
  '''
  Perform a search
  mode:         one of 'basic', 'advanced' or 'all'
  form:         form data
  entity_class: class of entity to search
  show_field:   show field linked to entity id
  '''
  if mode not in [SEARCH_BASIC, SEARCH_ADVANCED, SEARCH_ALL]:
    abort(HTTPStatus.BAD_REQUEST.value)

  # basic 'all' mode query
  if ORM:
    entities = entity_class.query\
                    .with_entities(entity_class.id, entity_class.name)
  else: # ENGINE
    entities = f'SELECT id, name FROM "{entity_class}"'

  search_terms = []
  clauses = []
  name = None
  city = None
  state = None
  
  if mode == SEARCH_ADVANCED:
    # advanced search based on name/city/state
    have_info = False
    if form.name.data is not None and len(form.name.data) > 0:
      name = form.name.data
      have_info = True

    if form.city.data is not None and len(form.city.data) > 0:
      city = form.city.data
      have_info = True

    if form.state.data != 'none':
      state = form.state.data
      have_info = True

    if not have_info:
        mode = SEARCH_BASIC # no info switch to basic mode

  if mode == SEARCH_BASIC:
    # basic name search
    search_term = request.form.get('search_term', '')

    if CITY_STATE_SEARCH_SEPARATOR in search_term:
      # 'city, state' search
      comma = search_term.find(CITY_STATE_SEARCH_SEPARATOR)
      if comma > 0:
        city = search_term[0:comma]
      comma = comma + len(CITY_STATE_SEARCH_SEPARATOR)
      state = search_term[comma:]
      if len(state) == 0:
        state = None
    else:
      name = search_term

  if name is not None:
    name = name.strip()
    if len(name) > 0:
      if ORM:
        clauses.append(entity_class.name.ilike("%"+name+"%"))
      else: # ENGINE
        clauses.append(f'"{entity_class}.name LIKE "%{name}%"')
      search_terms.append(f'name: {name}')

  if city is not None:
    city = city.strip()
    if len(city) > 0:
      if ORM:
        clauses.append(entity_class.city.ilike("%"+city+"%"))
      else: # ENGINE
        clauses.append(f'"{entity_class}.city LIKE "%{city}%"')
      search_terms.append(f'city: {city}')

  if state is not None and state != 'none':
    state = state.strip()
    if len(state) > 0:
      if ORM:
        clauses.append(entity_class.state == state.upper())
      else: # ENGINE
        clauses.append(f'"{entity_class}.state = UPPER({state})"')
      search_terms.append(f'state: {state}')

  if len(clauses) == 1:
    if ORM:
      entities = entities.filter(clauses[0])
    else: # ENGINE
      entities = entities + " WHERE " + clauses[0]
  elif len(clauses) > 1:
    if ORM:
      entities = entities.filter(and_(*clauses))
    else: # ENGINE
      entities = entities + " WHERE " + " AND ".join(clauses)

  try:
    if ORM:
      entities = entities.all()
    else: # ENGINE
      entities = execute(entities + ";")
  except:
      print_exc_info()
      abort(HTTPStatus.INTERNAL_SERVER_ERROR.value)

  data = entity_shows(entities, show_field)

  return {
    "count": len(data),
    "data": data,
    "search_term": ', '.join(search_terms),
    "mode": mode
  }

def entity_shows(entities, show_field):
  '''
  Perform a shows search
  entities:   list of entities whose shows to search for
  show_field: show field linked to entity id
  '''
  data = []
  for entity in entities:
    try:
      if ORM:
        shows = Show.query\
                      .filter(and_(show_field == entity.id, Show.start_time > datetime.now()))\
                      .count()
      else: # ENGINE
        shows = execute(f'SELECT COUNT(id) FROM "{SHOWS_TABLE}" WHERE {show_field} = {entity["id"]} AND start_time > CURRENT_TIMESTAMP;')
        shows = shows.scalar()
    except:
        print_exc_info()
        abort(HTTPStatus.INTERNAL_SERVER_ERROR.value)

    data.append({
      "id": entity.id,
      "name": entity.name,
      "num_upcoming_shows": shows
    })

  return data


def venues_search(mode, form):
  '''
  Perform a search on venues
  mode:   one of 'basic', 'advanced' or 'all'
  form:   form data
  '''
  if ORM:
    return name_city_state_search(mode, form, Venue, Show.venue_id)
  else: # ENGINE
    return name_city_state_search(mode, form, VENUE_TABLE, 'venue_id')


def artists_search(mode, form):
  '''
  Perform a search on artists
  mode:   one of 'basic', 'advanced' or 'all'
  form:   form data
  '''
  if ORM:
    return name_city_state_search(mode, form, Artist, Show.artist_id)
  else: # ENGINE
    return name_city_state_search(mode, form, ARTIST_TABLE, 'artist_id')


def _shows_by(entity_id, entity_class, link_field, show_field, keys, key_prefix, *criterion):
    '''
    Select shows for the specified entity
    entity_id:    id of entity whose shows to search for
    entity_class: class/table of entity
    link_field:   show field linking show and entity
    show_field:   info field in show
    keys:         keys to access result fields
    criterion:    filtering criterion
    '''
    try:
      if ORM:
        shows = Show.query.join(entity_class, show_field == entity_class.id)\
                      .with_entities(show_field, Show.start_time, entity_class.name, entity_class.image_link)\
                      .filter(and_(link_field == entity_id, *criterion))\
                      .order_by(Show.start_date)\
                      .all()
      else: # ENGINE
        shows = execute(f'SELECT {show_field}, "{SHOWS_TABLE}".start_time, '\
                        f'"{entity_class}".name, "{entity_class}".image_link FROM "{SHOWS_TABLE}" '\
                        f'INNER JOIN "{entity_class}" ON {show_field} = "{entity_class}".id '\
                        f'WHERE {link_field} = {entity_id} AND {" AND ".join(criterion)} '\
                        f'ORDER BY "{SHOWS_TABLE}".start_time;')
        shows = shows.mappings().fetchall()
    except:
        print_exc_info()
        abort(HTTPStatus.INTERNAL_SERVER_ERROR.value)

    # key is 'prefix_key' or 'start_time'
    # value is value or isoformat() for start_time
    kval = lambda k: f'{key_prefix}_{k}' if k != "start_time" else k
    vval = lambda k, v: v if k != "start_time" else v.isoformat()
    return [{kval(k): vval(k, show[v]) for k, v in keys.items()} for show in shows]

def shows_by_artist(artist_id, *criterion):
    '''
    Select shows for the specified artist
    artist_id:  id of artist 
    criterion:  filtering criterion
    '''
    if ORM:
      shows = _shows_by(artist_id, Venue, Show.artist_id, 
                        Show.venue_id, SHOWS_BY_KEYS, "venue_id", *criterion)
    else: # ENGINE
      shows = _shows_by(artist_id, VENUE_TABLE, f'"{SHOWS_TABLE}".artist_id', 
                        f'"{SHOWS_TABLE}".venue_id', SHOWS_BY_ARTIST_KEYS, "venue", *criterion)
    return shows


def shows_by_venue(venue_id, *criterion):
    '''
    Select shows for the specified venue
    venue_id:   id of venue 
    criterion:  filtering criterion
    '''
    if ORM:
      shows = _shows_by(venue_id, Artist, Show.venue_id, 
                        Show.artist_id, SHOWS_BY_KEYS, "artist_id", *criterion)
    else: # ENGINE
      shows = _shows_by(venue_id, ARTIST_TABLE, f'"{SHOWS_TABLE}".venue_id', 
                        f'"{SHOWS_TABLE}".artist_id', SHOWS_BY_VENUE_KEYS, "artist", *criterion)
    return shows



def get_genres():
    '''
    Generate a list of possible genre options
    '''
    try:
      if ORM:
        genres = Genre.query.with_entities(Genre.name).order_by(Genre.name).all()
      else: # ENGINE
        genres = execute(f'SELECT name FROM "{GENRES_TABLE}" ORDER BY name;')
    except:
        print_exc_info()
        abort(HTTPStatus.INTERNAL_SERVER_ERROR.value)

    options = [(g[0], g[0]) for g in genres if g[0] != 'Other']
    options.append(('Other', 'Other'))
    return options, [g[0] for g in options]



