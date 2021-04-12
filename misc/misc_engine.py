from http import HTTPStatus
from typing import Callable, Union, Any, List, AnyStr

from flask import abort
from werkzeug.datastructures import MultiDict

from .engine import execute, execute_transaction
from .common import EntityResult, print_exc_info
from models import SHOWS_TABLE, GENRES_TABLE, ARTIST_TABLE, VENUE_TABLE, Entity
from util import get_config


def get_music_entity_engine(entity_id: int, entity: Entity,
                            result_type: EntityResult = EntityResult.DICT):
    """
    Get the music entity with the given entity_id
    :param entity_id:   id of entity
    :param entity:      entity to search for
    :param result_type: type of result required
    """
    exists = False
    if result_type == EntityResult.DICT:
        data = dict()
    else:
        data = MultiDict()
    try:
        # genres is list of names
        instance = execute(f'SELECT *, ARRAY('
                           f'SELECT g.name FROM "{entity.eng_genre_link_table}" gl '
                           f'JOIN "{GENRES_TABLE}" g ON (gl.genre_id = g.id) '
                           f'WHERE gl.{entity.eng_genre_link_column} = {entity_id}) as genres'
                           f' from "{entity.eng_table}" '
                           f'WHERE {entity.fq_column("id")} = {entity_id};'
                           )
        if instance.rowcount != 0:
            exists = True

            entry = instance.fetchone()

            data = {k: v for k, v in entry.items()}     # convert to dict
            if result_type == EntityResult.MULTIDICT:
                data = MultiDict(data)

    except:
        print_exc_info()

    if not exists:
        abort(HTTPStatus.NOT_FOUND.value)

    return data


def get_show_summary_engine(entity_id: int, shows_by: Callable[[int, Any], List]) -> tuple:
    """
    Get the show summary for the given entity_id
    :param entity_id:        id of entity
    :param shows_by:         function taking of type 'shows_by(entity_id, criterion) -> list'
    """
    past_criterion = f'"{SHOWS_TABLE}".start_time < CURRENT_TIMESTAMP'
    future_criterion = f'"{SHOWS_TABLE}".start_time >= CURRENT_TIMESTAMP'

    past_shows = shows_by(entity_id, past_criterion)
    upcoming_shows = shows_by(entity_id, future_criterion)

    return past_shows, upcoming_shows


def genre_changes_engine(base: list, update: list, entity_id: int, entity: Entity) -> list:
    """
    Get the list of SQL statements to update genre setting from 'base' to 'update'
    :param base:         base list
    :param update:       updated list
    :param entity_id:    id of entity to which genre list refers
    :param entity:       entity to update
    """
    stmts = []
    genre_objs = genre_objs_engine(list(set(base + update)))

    def genre_id(gen_g): return next(item for item in genre_objs if item["name"] == gen_g)["id"]
    table = entity.eng_genre_link_table
    column = entity.eng_genre_link_column

    # to add
    for g in update:
        if g not in base:
            stmts.append(
                f'INSERT INTO "{table}"({column}, genre_id) VALUES ({entity_id}, {genre_id(g)});'
            )
    # to remove
    for g in base:
        if g not in update:
            stmts.append(
                f'DELETE FROM "{table}" WHERE {column}={entity_id} AND genre_id={genre_id(g)};'
            )

    return stmts


def exec_transaction_engine(stmts: list, identifier: str) -> (Union[bool, None], str):
    """
    Execute a transaction in ENGINE mode
    :param stmts:      statements in transaction
    :param identifier: identification
    """
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


def exists_engine(entity: AnyStr, entity_id: int):
    """
    Check if entity exists
    :param entity:      name of table to search
    :param entity_id:   id of entity to check
    """
    exists = False
    try:
        venue = execute(f'SELECT name from "{entity}" WHERE id = {entity_id};')
        exists = (venue.rowcount != 0)
    except:
        print_exc_info()
        abort(HTTPStatus.INTERNAL_SERVER_ERROR.value)

    return exists


def genre_list_engine(names: list):
    """
    Get the genres corresponding to the specified list
    :param names:   Genre names
    """
    # in the case of engine this is just the list of genre names, orm has a list of Genre
    return names


def genre_objs_engine(names: list):
    """
    Get the genres corresponding to the specified list
    :param names:   Genre names
    """
    in_list = ["'" + g + "'" for g in names]
    in_list = ", ".join(in_list)

    # genres is list of names
    genres = execute(f'SELECT * FROM "{GENRES_TABLE}" WHERE "{GENRES_TABLE}".name IN ({in_list});')
    keys = [k for k in genres.keys()]
    results = [g for g in genres]
    genre_objs = [{k: g[k] for k in keys} for g in results]

    return genre_objs


def latest_lists_engine() -> (list, list):
    num_latest = get_config("NUM_LATEST_ON_HOME")
    latest_artists = []
    latest_venues = []
    try:
        latest_artists = execute(f'SELECT id, name FROM "{ARTIST_TABLE}" ORDER BY id DESC LIMIT {num_latest};')
        latest_venues = execute(f'SELECT id, name FROM "{VENUE_TABLE}" ORDER BY id DESC LIMIT {num_latest};')
    except:
        print_exc_info()
        abort(HTTPStatus.INTERNAL_SERVER_ERROR.value)

    return latest_artists, latest_venues

