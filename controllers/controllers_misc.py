from datetime import datetime
import re
from typing import Callable, Union, Any, List
from enum import Enum
from http import HTTPStatus
from flask.helpers import flash, url_for

from sqlalchemy.sql.sqltypes import String
from sqlalchemy.inspection import inspect
from flask import abort, redirect
from flask_sqlalchemy import Model
from werkzeug.datastructures import MultiDict
from forms import AVAILABILITY_FROM_DATE_FMT, set_multiselect_field_options, get_genre_list

from queries import get_genres
from misc import get_config, print_exc_info
from models import model_property_list as models_model_property_list


if get_config("USE_ORM"):
  from models import Show
  ORM = True
else:
  from engine import execute, execute_transaction
  from models import SHOWS_TABLE, GENRES_TABLE, get_model_property_list
  ORM = False

ENGINE = not ORM


IGNORE_ID = ['id']
IGNORE_ID_GENRES = ["id", "genres"]


def set_genre_field_options(field, data):
  choices, values = get_genres()
  set_multiselect_field_options(field, choices, values, data)


def model_property_list(model, ignore=[]):
  '''
  Get the list of property names from a SQLAlchemy model
  model:  model to get property names from
  ignore: names to ignore
  '''
  # need to inspect as if model object is empty it will have no items in its dict
  if ORM:
    return models_model_property_list(model, ignore=ignore)
  else: # ENGINE
    return [key for key in get_model_property_list(model) 
                      if key not in ignore]


RE_DATETIME = re.compile(r'(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})')

def get_availability_date(query_date):
  if query_date is not None:
    match = RE_DATETIME.match(query_date)
    if match:
      query_date = datetime.strptime(match[1] + ' ' + match[2], AVAILABILITY_FROM_DATE_FMT)
    else:
      query_date = datetime.today()


class EntityResult(Enum):
  DICT = 1
  MULTIDICT = 2
  MODEL = 3


def get_music_entity(entity_id: int, entity_class: List[Union[Model, String]], shows_by: Callable[[int, Any], List], 
                      genre_link_table: str = None, genre_link_field: str = None, result_type: EntityResult = EntityResult.DICT):
  '''
  Get the music entity with the given entity_id
  entity_id:        id of entity
  entity_class:     class of entity or name of table to search
  shows_by:         function taking of type 'shows_by(entity_id, criterion) -> list'
  genre_link_table: name of entity/genre link table, only required in engine mode
  genre_link_field: name of field in entity/genre link table linking to entity id, only required in engine mode
  '''
  exists = False
  try:
    if ORM:
      entity = entity_class.query.filter(entity_class.id==entity_id).first()
      if entity != None:
        exists = True
        if result_type == EntityResult.DICT:
          data = entity.get_dict(genres='name')
        else:
          data = entity.get_multidict(genres='name')

    else: # ENGINE
      # genres is list of names
      entity = execute(f'SELECT *, ARRAY(' \
                          f'SELECT g.name FROM "{genre_link_table}" gl ' \
                            f'JOIN "{GENRES_TABLE}" g ON (gl.genre_id = g.id) '\
                            f'WHERE gl.{genre_link_field} = {entity_id}) as genres' \
                        f' from "{entity_class}" ' \
                        f'WHERE "{entity_class}".id = {entity_id};'
        )
      if entity.rowcount != 0:
        exists = True

        entry = entity.mappings().first()

        data = {k: entry.get(k) for k in entry.keys()}
        if result_type == EntityResult.MULTIDICT:
          data = MultiDict(data)

  except:
    print_exc_info()
    if result_type == EntityResult.DICT:
      data = dict()
    else:
      data = MultiDict()

  if not exists:
    abort(HTTPStatus.NOT_FOUND.value)

  return data


def get_music_entity_with_show_summary(entity_id: int, entity_class: List[Union[Model, String]], shows_by: Callable[[int, Any], List], 
                      genre_link_table: str = None, genre_link_field: str = None):
  '''
  Show the artist page with the given entity_id
  entity_id:        id of entity
  entity_class:     class of entity or name of table to search
  shows_by:         function taking of type 'shows_by(entity_id, criterion) -> list'
  genre_link_table: name of entity/genre link table, only required in engine mode
  genre_link_field: name of field in entity/genre link table linking to entity id, only required in engine mode
  '''
  data = get_music_entity(entity_id, entity_class, shows_by, genre_link_table, genre_link_field)

  # add the shows summary info
  if ORM:
    past_criterion = Show.start_time < datetime.now()
    future_criterion = Show.start_time >= datetime.now()
  else: # ENGINE
    past_criterion = f'"{SHOWS_TABLE}".start_time < CURRENT_TIMESTAMP'
    future_criterion = f'"{SHOWS_TABLE}".start_time >= CURRENT_TIMESTAMP'

  past_shows = shows_by(entity_id, past_criterion)
  upcoming_shows = shows_by(entity_id, future_criterion)
  data["past_shows"] = past_shows
  data["upcoming_shows"] = upcoming_shows
  data["past_shows_count"] = len(past_shows)
  data["upcoming_shows_count"] = len(upcoming_shows)

  return data


def genre_changes_engine(base: list, update: list, id: int, table: str, column: str) -> list:
  '''
  Get the list of SQL statements to update genre setting from 'base' to 'update'
  base:     base list
  update:   updated list
  id:       id of entity to which genre list refers
  table:    entity/genre link table
  column:   entiry column in entity/genre link table
  '''
  if ENGINE:
    stmts = []
    _, genre_objs = get_genre_list(list(set(base + update)))

    genre_id = lambda g: next(item for item in genre_objs if item["name"] == g)["id"]

    # to add
    for g in update:
      if g not in base:
        stmts.append(
          f'INSERT INTO "{table}"({column}, genre_id) VALUES ({id}, {genre_id(g)});'
        )
    # to remove
    for g in base:
      if g not in update:
        stmts.append(
          f'DELETE FROM "{table}" WHERE {column}={id} AND genre_id={genre_id(g)};'
        )
  else:
    stmts = []

  return stmts


def exec_transaction_engine(stmts: list, identifier: str):
  '''
  Execute a transaction in ENGINE mode
  stmts:      statements in transaction
  identifier: identification
  '''
  if len(stmts) > 0:
    try:
      execute_transaction(stmts)
      success = True
    except:
      print_exc_info()
      success = False
  else:
    success = None

  return success, identifier


def __flash_result(success, name, entity_type, action):
  '''
  Falsh result
  success:      action result; boolean or None
  name:         name of entity
  entity_type:  type of entity
  action:       action 
  '''
  if success:
      flash(f'{entity_type} {name} was successfully {action}!')
  elif success is not None:
      flash(f'An error occurred. {entity_type} {name} could not be {action}.')
  # else no message necessary


def update_result(success, name, entity_type, url):
  '''
  Delete result
  success:      action result; boolean or None
  name:         name of entity
  entity_type:  type of entity
  url:          url to redirect to
  '''
  __flash_result(success, name, entity_type, 'updated')
  return redirect(url)


def create_result(success, name, entity_type):
  '''
  Create result
  success:      action result; boolean or None
  name:         name of entity
  entity_type:  type of entity
  '''
  __flash_result(success, name, entity_type, 'listed')
  return redirect(url_for('index'))


def delete_result(success, name, entity_type):
  '''
  Delete result
  success:      action result; boolean or None
  name:         name of entity
  entity_type:  type of entity
  '''
  __flash_result(success, name, entity_type, 'deleted')
  return {'success': success, 'redirect': url_for('index')}


def exists_or_404(entity, entity_id: int):
  exists = False
  try:
    if ORM:
      venue = entity.query\
                    .with_entities(entity.id)\
                    .filter(entity.id==entity_id)\
                    .first()
      exists = (venue != None)
    else: # ENGINE
      venue = execute(f'SELECT name from "{entity}" WHERE id = {entity_id};')
      exists = (venue.rowcount != 0)
  except:
      print_exc_info()
      abort(HTTPStatus.INTERNAL_SERVER_ERROR.value)

  if not exists:
      abort(HTTPStatus.NOT_FOUND.value)
