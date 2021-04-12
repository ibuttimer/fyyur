# ---------------------------------------------------------------------------- #
# Imports
# ---------------------------------------------------------------------------- #
from datetime import timedelta, datetime
from http import HTTPStatus
from typing import Union

from flask import abort
from flask_sqlalchemy import Pagination
from flask_wtf import FlaskForm

from misc import (print_exc_info, EntityResult, ncsg_search_clauses, entity_search_clauses,
                  OR_CONJUNC, AND_CONJUNC, SearchParams, entity_search_expression, SP_GENRES
                  )
from util import get_config
from misc.engine import execute
from misc.queries_engine import join_engine
from models import ARTIST_TABLE, VENUE_TABLE, SHOWS_TABLE, get_entity, fq_column, GENRES_TABLE
from .artist_engine import datetime_to_str
from .controllers_misc import IGNORE_ID, model_property_list, FactoryObj, FILTER_PREVIOUS, FILTER_UPCOMING
from .show_orm import SHOWS_KEYS, AvailabilitySlot

# keys to extract data for db results
SHOWS_DICT = {p: p for p in SHOWS_KEYS}

SHOWS_PER_PAGE = get_config("SHOWS_PER_PAGE")

_ARTIST_ = get_entity(ARTIST_TABLE)
_VENUE_ = get_entity(VENUE_TABLE)
_SHOWS_ = get_entity(SHOWS_TABLE)


def show_factory_engine(obj_type: FactoryObj) -> Union[dict, str, None]:
    """
    Get a show related object
    :param obj_type: object type to get
    :return:
    """
    result = None
    if obj_type == FactoryObj.OBJECT:
        result = _SHOWS_.model_dict()
    elif obj_type == FactoryObj.CLASS:
        result = _SHOWS_.eng_table
    return result


_FIELDS_LIST_ = ", ".join([
    _SHOWS_.fq_column("venue_id"), _SHOWS_.fq_column("artist_id"), _SHOWS_.fq_column("start_time"),
    f'{_VENUE_.fq_column("name")} as venue_name', f'{_ARTIST_.fq_column("name")} as artist_name',
    f'{_ARTIST_.fq_column("image_link")} as artist_image_link'
])
# ((inner join 'shows table' and 'venue table')
#       inner join 'artist table')
_BASIC_FROM_JOIN_ = \
    join_engine(
        join_engine(_SHOWS_.eng_table, _VENUE_.eng_table, _SHOWS_.fq_column("venue_id"), _VENUE_.fq_id()),
        _ARTIST_.eng_table, _SHOWS_.fq_column("artist_id"), _ARTIST_.fq_id())
# ((((((inner join 'shows table' and 'venue table')
#       inner join 'artist table')
#           inner join 'venue genre table')
#               inner join 'artist genre table')
#                   inner join 'genre table')
#                       inner join aliased 'genre table')
_ALIAS_GENRE_TABLE_ = f'alias{GENRES_TABLE}'
_GENRE_FROM_JOIN_ = \
    join_engine(
        join_engine(
            join_engine(
                join_engine(
                    join_engine(
                        join_engine(_SHOWS_.eng_table, _VENUE_.eng_table,
                                    _SHOWS_.fq_column("venue_id"), _VENUE_.fq_id()),
                        _ARTIST_.eng_table,
                        _SHOWS_.fq_column("artist_id"), _ARTIST_.fq_id()),
                    _VENUE_.eng_genre_link_table,
                    fq_column(_VENUE_.eng_genre_link_table, "venue_id"), _VENUE_.fq_id()),
                _ARTIST_.eng_genre_link_table,
                fq_column(_ARTIST_.eng_genre_link_table, "artist_id"), _ARTIST_.fq_id()),
            GENRES_TABLE,
            fq_column(_VENUE_.eng_genre_link_table, "genre_id"), fq_column(GENRES_TABLE, "id")),
        f'"{GENRES_TABLE}" as {_ALIAS_GENRE_TABLE_}',
        fq_column(_ARTIST_.eng_genre_link_table, "genre_id"), f'{_ALIAS_GENRE_TABLE_}.id')


def shows_engine(page: int, filterby: str, mode: str, form: FlaskForm, search_term: str) -> dict:
    """
    List all shows
    :param page:         requested page of search results
    :param filterby:     results filter; one of 'all', 'previous' or 'upcoming'
    :param mode:         one of 'basic', 'advanced' or 'all'
    :param form:         form data for advanced search
    :param search_term:  search_term for basic search
    """
    shows_list = []
    pagination = Pagination(None, page, SHOWS_PER_PAGE, 0, shows_list)
    # advanced search on Venue & Artist, joining class clauses with 'and' and the result of those with 'or'
    # e.g. if have 'name' do same search on Venue & Artist and 'or' their results
    search = \
        SearchParams([_VENUE_, _ARTIST_], conjunction=[OR_CONJUNC, AND_CONJUNC],
                     genre_aliases=[None, _ALIAS_GENRE_TABLE_]).load_form(form)
    search.simple_search_term = search_term
    try:
        if filterby == FILTER_PREVIOUS:
            time_filter = f'"{SHOWS_TABLE}".start_time < \'{datetime_to_str(datetime.today())}\''
        elif filterby == FILTER_UPCOMING:
            time_filter = f'"{SHOWS_TABLE}".start_time > \'{datetime_to_str(datetime.today())}\''
        else:
            time_filter = None

        # get search terms and clauses for both Venue & Artist
        ncsg_search_clauses(mode, search)

        from_term = _GENRE_FROM_JOIN_ if search.searching_on[SP_GENRES] else _BASIC_FROM_JOIN_

        if len(search.clauses) > 0:
            search_filter = entity_search_clauses('', search, entity_search_expression)
        else:
            search_filter = None

        filters = _combine_filters(search_filter, time_filter)

        # get total count
        sql = f'SELECT COUNT("{SHOWS_TABLE}".venue_id) FROM {from_term}{filters};'
        total = execute(sql).scalar()

        if total > 0:
            offset = SHOWS_PER_PAGE * (page - 1)
            if offset >= total:
                abort(HTTPStatus.BAD_REQUEST.value)
        else:
            offset = 0

        # get items for this request
        sql = f'SELECT {_FIELDS_LIST_} FROM {from_term}{filters} ' \
              f'ORDER BY "{SHOWS_TABLE}".start_time LIMIT {SHOWS_PER_PAGE} OFFSET {offset};'

        shows_list = execute(sql).fetchall()
        total = len(shows_list)

        pagination = Pagination(None, page, SHOWS_PER_PAGE, total, shows_list)
        shows_list = pagination.items

    except:
        print_exc_info()
        abort(HTTPStatus.INTERNAL_SERVER_ERROR.value)

    # [{'venue_id': ?, 'artist_id' ?, ...}, {}, ...] }
    data = [{k: show[v] if k != 'start_time' else show[v].isoformat() for k, v in SHOWS_DICT.items()}
            for show in shows_list]

    return {
        "count": pagination.total,
        "data": data,
        "search_term": ', '.join(search.search_terms),
        "mode": mode,
        "pagination": pagination
    }


def _combine_filters(search_filter: str, time_filter: str):
    sql = ''
    if search_filter is not None:
        sql = search_filter  # will have where in it
    if time_filter is not None:
        operator = 'AND' if 'WHERE' in sql else 'WHERE'
        sql = f'{sql} {operator} ({time_filter})'
    return sql


def extract_unique_properties_engine(show: dict) -> tuple:
    """
    Extract the properties to uniquely find a show
    :param show:   show to extract from
    :return: properties as a tuple
    """
    return show["artist_id"], show["venue_id"], show["start_time"].date(), show["start_time"], \
           show["start_time"] + timedelta(minutes=show["duration"]), EntityResult.DICT


__DOW_TIMES__ = [
    # start_time, end_time
    ("mon_from", "mon_to"),  # monday
    ("tue_from", "tue_to"),  # tuesday
    ("wed_from", "wed_to"),  # wednesday
    ("thu_from", "thu_to"),  # thursday
    ("fri_from", "fri_to"),  # friday
    ("sat_from", "sat_to"),  # saturday
    ("sun_from", "sun_to"),  # sunday
]


def dow_availability_engine(availability: dict, dow: int):
    """
    Get availability for the specified day of the week
    :param availability:    availability info
    :param dow:             day of the week; 0=monday etc.
    """
    if availability is not None:
        start_time = availability[__DOW_TIMES__[dow][0]]
        end_time = availability[__DOW_TIMES__[dow][1]]
    else:
        start_time = None
        end_time = None
    return AvailabilitySlot(start_time=start_time, end_time=end_time)


def show_insert_sql(show: dict):
    """
    Generate show insert SQL
    :param show:   show to create
    """
    properties = model_property_list(show, IGNORE_ID)
    properties_list = ', '.join(properties)
    value_dict = {p: str(show[p]) if p != 'start_time' else f"'{datetime_to_str(show[p])}'" for p in properties}
    values = [value_dict[p] for p in properties]
    values_list = ', '.join(values)
    return f'INSERT INTO "{SHOWS_TABLE}"({properties_list}) VALUES ({values_list});'


def create_show_engine(show: dict):
    """
    Create an show in ENGINE mode
    :param show:   show to create
    """
    success = False
    try:
        new_show = execute(show_insert_sql(show))
        success = new_show.rowcount > 0
    except:
        print_exc_info()

    return success


def artists_and_venues_engine():
    """
    Get artists and venues for show listing
    """
    artists = []
    venues = []
    try:
        artists = execute(f'SELECT id, name FROM "{ARTIST_TABLE}" ORDER BY name;') \
            .fetchall()
        artists = [(a["id"], a["name"]) for a in artists]
        venues = execute(f'SELECT id, name FROM "{VENUE_TABLE}" ORDER BY name;') \
            .fetchall()
        venues = [(a["id"], a["name"]) for a in venues]
    except:
        print_exc_info()

    return artists, venues
