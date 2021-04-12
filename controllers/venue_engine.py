# ---------------------------------------------------------------------------- #
# Imports
# ---------------------------------------------------------------------------- #
from datetime import datetime
from http import HTTPStatus
from typing import Union

from flask import abort
from flask_wtf import FlaskForm

from forms import (APP_DATETIME_FMT, APP_DATE_FMT, APP_TIME_FMT)
from misc import EntityResult, print_exc_info
from misc import get_music_entity_engine, genre_changes_engine, exec_transaction_engine
from misc.engine import execute, execute_transaction
from misc.queries import entity_shows_count, shows_by_venue
from models import (VENUE_TABLE, SHOWS_TABLE, VENUE_GENRES_TABLE,
                    dict_disjoint, equal_dict, ARTIST_TABLE, get_entity)
from .controllers_misc import add_show_summary, model_property_list, IGNORE_ID_GENRES, IGNORE_ID, FactoryObj, \
    populate_genred_model
from .venue_orm import BOOKING_BY_VENUE_KEYS

# keys to extract data for db results
BOOKING_BY_VENUE_DICT = {p: p for p in BOOKING_BY_VENUE_KEYS}

_VENUE_ = get_entity(VENUE_TABLE)


def venue_factory_engine(obj_type: FactoryObj) -> Union[dict, str, None]:
    """
    Get a venue related object
    :param obj_type: object type to get
    :return:
    """
    result = None
    if obj_type == FactoryObj.OBJECT:
        result = _VENUE_.model_dict()
    elif obj_type == FactoryObj.CLASS:
        result = _VENUE_.eng_table
    return result


def venues_engine():
    """
    List all venues
    """
    venues = []
    try:
        cities_states = execute(f'SELECT DISTINCT state, city from "{VENUE_TABLE}";')
        for city_state in cities_states:
            city = city_state["city"]
            state = city_state["state"]
            venue_list = execute(
                f'SELECT DISTINCT id, name from "{VENUE_TABLE}" WHERE state = \'{state}\' AND city = \'{city}\';')
            venues.append({
                "state": state,
                "city": city,
                "venues": entity_shows_count(venue_list, _VENUE_)
            })
    except:
        print_exc_info()
        abort(HTTPStatus.INTERNAL_SERVER_ERROR.value)

    return venues


def get_venue_engine(venue_id: int):
    """
    Get a venue
    :param venue_id:   id of venue
    """
    venue = get_music_entity_engine(venue_id, _VENUE_)
    return add_show_summary(venue_id, venue, shows_by_venue)


def populate_venue_engine(venue: dict, form: FlaskForm):
    """
    Populate a venue from a form
    :param venue:   venue
    :param form:    form to populate from
    """
    property_list = model_property_list(venue, IGNORE_ID_GENRES)
    return populate_genred_model(venue, form, property_list)


def update_venue_engine(venue: dict, form: FlaskForm) -> (Union[bool, None], str):
    """
    Update an venue in ENGINE mode
    :param venue:   base venue
    :param form:    form to update from
    """
    stmts = []
    venue_id = venue["id"]

    updated_venue = populate_venue_engine(_VENUE_.model_dict(), form)
    if not equal_dict(venue, updated_venue, IGNORE_ID):
        # change has occurred update venue
        to_set = [f'{k}=\'{v}\'' for k, v in updated_venue.items()
                  if k in dict_disjoint(venue, updated_venue, IGNORE_ID_GENRES)]
        if len(to_set) > 0:
            to_set = ", ".join(to_set)
            stmts.append(f'UPDATE "{VENUE_TABLE}" SET {to_set} WHERE id={venue_id};')

        # update genre link table
        if updated_venue["genres"] != venue["genres"]:
            for stmt in genre_changes_engine(venue["genres"], updated_venue["genres"], venue_id, _VENUE_):
                stmts.append(stmt)

    return exec_transaction_engine(stmts, updated_venue["name"])


def venue_to_edit_engine(venue_id: int):
    """
    Edit a venue
    :param venue_id: id of the venue to edit
    """
    venue = get_music_entity_engine(venue_id, _VENUE_)
    as_type = EntityResult.DICT  # availability as a dict
    return venue, as_type


def delete_venue_engine(venue_id: int) -> (bool, str):
    """
    Delete a venue in ENGINE mode
    :param venue_id: id of the venue to delete
    """
    success = False
    venue_name = None
    exists = False
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

    if not exists:
        abort(HTTPStatus.NOT_FOUND.value)

    return success, venue_name


def extract_unique_properties_engine(venue: dict) -> tuple:
    """
    Extract the properties to uniquely find a venue
    Note: order matches that of existing_venue_engine() arguments
    :param venue:   venue to extract from
    :return: properties as a tuple
    """
    return venue["name"], venue["address"], venue["city"], venue["state"]


def id_name_by_unique_properties_sql(name: str, address: str, city: str, state: str):
    """
    Generate select SQL from properties to uniquely find a venue
    :param name:    venue name
    :param address: venue address
    :param city:    venue city
    :param state:   venue state
    """
    return f'SELECT id, name from "{VENUE_TABLE}" WHERE LOWER(name) = LOWER(\'{name}\') ' \
           f'AND LOWER(address) = LOWER(\'{address}\') ' \
           f'AND LOWER(city) = LOWER(\'{city}\') AND state = \'{state}\';'


def existing_venue_engine(name: str, address: str, city: str, state: str):
    """
    Check for existing venue
    :param name:    venue name
    :param address: venue address
    :param city:    venue city
    :param state:   venue state
    :return: existing venue id and name, or None
    """
    venue_id = None
    venue_name = None
    try:
        existing = execute(
            id_name_by_unique_properties_sql(name, address, city, state)
        )
        if existing.rowcount > 0:
            hit = existing.mappings().first()
            venue_id = hit.get('id')
            venue_name = hit.get('name')

    except:
        print_exc_info()

    return venue_id, venue_name


def venue_insert_sql(venue: dict):
    """
    Generate venue insert SQL
    :param venue: venue to create
    """
    properties = model_property_list(venue, IGNORE_ID_GENRES)
    properties_list = ', '.join(properties)
    value_dict = {p: "'" + venue[p] + "'" for p in properties if p != 'seeking_talent'}
    value_dict['seeking_talent'] = 'TRUE' if venue['seeking_talent'] else 'FALSE'
    values = [value_dict[p] for p in properties]
    values_list = ', '.join(values)

    return f'INSERT INTO "{VENUE_TABLE}"({properties_list}) VALUES ({values_list});'


def create_venue_engine(venue: dict):
    """
    Create an venue in ENGINE mode
    :param venue: venue to create
    """
    success = False
    venue_name = venue["name"]
    try:
        new_venue = execute(venue_insert_sql(venue))
        if new_venue.rowcount > 0:
            # using raw sql so need to query to get new id
            new_venue = execute(
                id_name_by_unique_properties_sql(*extract_unique_properties_engine(venue))
            )
            if new_venue.rowcount > 0:
                new_venue = new_venue.fetchone()
                venue_id = new_venue["id"]

                stmts = []
                # add genres
                for stmt in genre_changes_engine([], venue["genres"], venue_id, _VENUE_):
                    stmts.append(stmt)

                execute_transaction(stmts)
                success = True
    except:
        print_exc_info()

    return success, venue_name


def datetime_to_str(date_time: datetime) -> str:
    return date_time.strftime(APP_DATETIME_FMT)


def str_to_datetime(date_time: datetime) -> datetime:
    return datetime.strptime(date_time, APP_DATETIME_FMT)


def date_to_str(date_time: datetime) -> str:
    return date_time.strftime(APP_DATE_FMT)


def time_to_str(date_time: datetime) -> str:
    return date_time.strftime(APP_TIME_FMT)


def bookings_by_venue_engine(venue_id: int, query_date: datetime):
    """
    Search for a venue's bookings
    :param venue_id:   id of venue
    :param query_date: date filtering criterion
    """
    bookings = []
    try:
        sql = f'SELECT "{SHOWS_TABLE}".start_time, "{SHOWS_TABLE}".duration, "{ARTIST_TABLE}".name ' \
              f'FROM (("{SHOWS_TABLE}" ' \
              f'INNER JOIN "{VENUE_TABLE}" ON "{SHOWS_TABLE}".venue_id = "{VENUE_TABLE}".id) ' \
              f'INNER JOIN "{ARTIST_TABLE}" ON "{SHOWS_TABLE}".artist_id = "{ARTIST_TABLE}".id) ' \
              f'WHERE "{SHOWS_TABLE}".venue_id = {venue_id}'
        if query_date is not None:
            sql = f'{sql} AND DATE("{SHOWS_TABLE}".start_time) = \'{date_to_str(query_date)}\''
        else:
            sql = f'{sql} ORDER BY "{SHOWS_TABLE}".start_time'
        sql = sql + ';'

        bookings = execute(sql).fetchall()

    except:
        print_exc_info()
        abort(HTTPStatus.INTERNAL_SERVER_ERROR.value)

    # [{'start_time': ?, 'duration' ?, ...}, {}, ...] }
    return [{k: show[BOOKING_BY_VENUE_DICT[k]] for k, v in BOOKING_BY_VENUE_DICT.items()} for show in bookings]
