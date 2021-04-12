# ---------------------------------------------------------------------------- #
# Imports
# ---------------------------------------------------------------------------- #
from datetime import time, datetime
from http import HTTPStatus
from typing import Union

from flask import abort
from flask_wtf import FlaskForm

from misc.engine import execute, execute_transaction
from forms import (populate_model, AVAILABILITY_FROM_DATE_FMT, AVAILABILITY_TIME_FMT)
from models import (ARTIST_TABLE, AVAILABILITY_TABLE, ARTIST_GENRES_TABLE,
                    equal_dict, dict_disjoint, get_entity)
from models import is_available, get_model_property_list, SHOWS_TABLE, fq_column
from .artist_orm import IGNORE_AVAILABILITY, IGNORE_ID_DATE
from .controllers_misc import add_show_summary, model_property_list, IGNORE_ID_GENRES, IGNORE_ID, FactoryObj, \
    populate_genred_model
from misc import (get_music_entity_engine, genre_changes_engine, exec_transaction_engine, print_exc_info, EntityResult,
                  shows_by_artist)


_ARTIST_ = get_entity(ARTIST_TABLE)
_AVAILABILITY_ = get_entity(AVAILABILITY_TABLE)


def artist_factory_engine(obj_type: FactoryObj) -> Union[dict, str, None]:
    """
    Get an artist related object
    :param obj_type: object type to get
    :return:
    """
    result = None
    if obj_type == FactoryObj.OBJECT:
        result = _ARTIST_.model_dict()
    elif obj_type == FactoryObj.CLASS:
        result = _ARTIST_.eng_table
    return result


def availability_factory_engine(obj_type: FactoryObj) -> Union[dict, str, None]:
    """
    Get an availability related object
    :param obj_type: object type to get
    :return:
    """
    result = None
    if obj_type == FactoryObj.OBJECT:
        result = _AVAILABILITY_.model_dict()
    elif obj_type == FactoryObj.CLASS:
        result = _AVAILABILITY_.eng_table
    return result


def availability_by_artist_engine(artist_id: int,
                                  from_date=datetime, as_type=EntityResult.DICT) -> Union[dict, None]:
    """
    Search for an artist's latest availability
    :param artist_id:  id of artist
    :param from_date:  filtering criterion
    :param as_type:    result
    """
    availability = None
    try:
        properties = ['"' + AVAILABILITY_TABLE + '".' + p for p in get_model_property_list(AVAILABILITY_TABLE)]
        properties = ', '.join(properties)
        result = execute(f'SELECT {properties} FROM "{AVAILABILITY_TABLE}" '
                         f'INNER JOIN "{ARTIST_TABLE}" '
                         f'ON {_AVAILABILITY_.fq_column("artist_id")} = {_ARTIST_.fq_column("id")} '
                         f'WHERE {_AVAILABILITY_.fq_column("artist_id")} = {artist_id} '
                         f'AND {_AVAILABILITY_.fq_column("from_date")} < TIMESTAMP \'{from_date}\' '
                         f'ORDER BY {_AVAILABILITY_.fq_column("from_date")} DESC, '
                         f'{_AVAILABILITY_.fq_column("id")} DESC;')
        if result.rowcount == 0:
            availability = None
        else:
            entry = result.mappings().first()
            availability = {k: entry.get(k) for k in entry.keys()}
    except:
        print_exc_info()
        abort(HTTPStatus.INTERNAL_SERVER_ERROR.value)

    return availability


def get_artist_engine(artist_id: int) -> dict:
    """
    Show the artist page with the given artist_id
    :param artist_id:   id of artist
    """
    artist = get_music_entity_engine(artist_id, _ARTIST_)
    return add_show_summary(artist_id, artist, shows_by_artist)


def populate_artist_engine(artist: dict, form: FlaskForm):
    """
    Populate an artist from a form
    :param artist:  artist
    :param form:    form to populate from
    """
    property_list = model_property_list(artist, IGNORE_ID_GENRES)
    return populate_genred_model(artist, form, property_list)


def populate_availability_engine(availability: dict, form: FlaskForm):
    """
    Populate an availability from a form
    """
    property_list = model_property_list(availability, IGNORE_AVAILABILITY)
    return populate_model(availability, form, property_list)


def datetime_to_str(date_time: datetime) -> str:
    return date_time.strftime(AVAILABILITY_FROM_DATE_FMT)


def time_to_str(t_time: Union[datetime, time]) -> str:
    return t_time.strftime(AVAILABILITY_TIME_FMT)


def availability_time_to_str(available_time):
    return None if available_time is None else f"'{time_to_str(available_time)}'"


def availability_insert_sql(artist_id: int, availability: dict):
    """
    Generate availability insert SQL
    :param artist_id:       id of the artist to update
    :param availability:    artist availability
    """
    properties = model_property_list(availability, IGNORE_ID)
    value_dict = {
        'artist_id': str(artist_id),
        'from_date': "'" + datetime_to_str(availability["from_date"]) + "'"
    }
    # get non empty times
    times_to_add = [p for p in properties if p != 'artist_id' and p != 'from_date' and availability[p] is not None]
    properties_list = [p for p in value_dict.keys()] + times_to_add

    value_dict = {**value_dict, **{
        p: availability_time_to_str(availability[p]) for p in times_to_add
    }}
    values = [value_dict[p] for p in properties_list]

    values_list = ', '.join(values)
    properties_list = ', '.join(properties_list)

    return f'INSERT INTO "{AVAILABILITY_TABLE}"({properties_list}) VALUES ({values_list});'


def update_artist_engine(artist_id: int, form: FlaskForm, availability: dict) -> (Union[bool, None], str):
    """
    Update an artist in ENGINE mode
    :param artist_id:       id of the artist to update
    :param form:            form to populate from
    :param availability:    artist availability
    """
    stmts = []
    artist = get_music_entity_engine(artist_id, _ARTIST_)

    updated_artist = populate_artist_engine(_ARTIST_.model_dict(), form)
    if not equal_dict(artist, updated_artist, IGNORE_ID):
        # change has occurred update artist
        to_set = [f'{k}=\'{v}\'' for k, v in updated_artist.items()
                  if k in dict_disjoint(artist, updated_artist, IGNORE_ID_GENRES)]
        if len(to_set) > 0:
            to_set = ", ".join(to_set)
            stmts.append(f'UPDATE "{ARTIST_TABLE}" SET {to_set} WHERE id={artist_id};')

        # update genre link table
        if updated_artist["genres"] != artist["genres"]:
            for stmt in genre_changes_engine(artist["genres"], updated_artist["genres"], artist_id, _ARTIST_):
                stmts.append(stmt)

    new_availability = populate_availability_engine(_AVAILABILITY_.model_dict(), form)
    new_availability["artist_id"] = artist_id

    if is_available(availability) != is_available(new_availability) or \
            not equal_dict(availability, new_availability, IGNORE_ID_DATE):
        # availability has changed, add new setting
        stmts.append(availability_insert_sql(artist_id, new_availability))

    return exec_transaction_engine(stmts, updated_artist["name"])


def artist_to_edit_engine(artist_id: int) -> (dict, EntityResult, dict):
    """
    Edit an artist
    :param artist_id: id of the artist to edit
    """
    artist = get_music_entity_engine(artist_id, _ARTIST_)
    as_type = EntityResult.DICT  # availability as a dict
    no_availability = dict()
    return artist, as_type, no_availability


def delete_artist_engine(artist_id: int) -> (bool, str):
    """
    Delete an artist in ENGINE mode
    :param artist_id: id of the artist to delete
    """
    success = False
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

    if not exists:
        abort(HTTPStatus.NOT_FOUND.value)

    return success, artist_name


def extract_unique_properties_engine(artist: dict) -> tuple:
    """
    Extract the properties to uniquely find a artist
    Note: order matches that of existing_artist_engine() arguments
    :param artist:   artist to extract from
    :return: properties as a tuple
    """
    return artist["name"], artist["city"], artist["state"]


def id_name_by_unique_properties_sql(name: str, city: str, state: str):
    """
    Generate select SQL from properties to uniquely find an artist
    :param name:    artist name
    :param city:    artist city
    :param state:   artist state
    """
    return f'SELECT id, name from "{ARTIST_TABLE}" WHERE LOWER(name) = LOWER(\'{name}\') ' \
           f'AND LOWER(city) = LOWER(\'{city}\') AND state = \'{state}\';'


def existing_artist_engine(name: str, city: str, state: str):
    """
    Check for existing artist
    :param name:    artist name
    :param city:    artist city
    :param state:   artist state
    :return: existing artist id and name, or None
    """
    artist_id = None
    artist_name = None
    try:
        existing = execute(
            id_name_by_unique_properties_sql(name, city, state)
        )
        if existing.rowcount > 0:
            hit = existing.mappings().first()
            artist_id = hit.get('id')
            artist_name = hit.get('name')

    except:
        print_exc_info()

    return artist_id, artist_name


def artist_insert_sql(artist: dict):
    """
    Generate artist insert SQL
    :param artist:          artist to create
    """
    properties = model_property_list(artist, IGNORE_ID_GENRES)
    properties_list = ', '.join(properties)
    value_dict = {p: "'" + artist[p] + "'" for p in properties if p != 'seeking_venue'}
    value_dict['seeking_venue'] = 'TRUE' if artist['seeking_venue'] else 'FALSE'
    values = [value_dict[p] for p in properties]
    values_list = ', '.join(values)

    return f'INSERT INTO "{ARTIST_TABLE}"({properties_list}) VALUES ({values_list});'


def create_artist_engine(artist: dict, availability: dict):
    """
    Create an artist in ENGINE mode
    :param artist:          artist to create
    :param availability:    artist availability
    """
    success = False
    artist_name = artist["name"]
    try:
        new_artist = execute(artist_insert_sql(artist))
        if new_artist.rowcount > 0:
            # using raw sql so need to query to get new id
            new_artist = execute(
                id_name_by_unique_properties_sql(*extract_unique_properties_engine(artist))
            )
            if new_artist.rowcount > 0:
                new_artist = new_artist.fetchone()
                artist_id = new_artist["id"]

                stmts = []
                # add genres
                for stmt in genre_changes_engine([], artist["genres"], artist_id, _ARTIST_):
                    stmts.append(stmt)

                if is_available(availability):
                    stmts.append(availability_insert_sql(artist_id, availability))

                execute_transaction(stmts)
                success = True
    except:
        print_exc_info()

    return success, artist_name
