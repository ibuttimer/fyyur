# ---------------------------------------------------------------------------- #
# Imports
# ---------------------------------------------------------------------------- #
from datetime import timedelta, datetime
from http import HTTPStatus
from typing import Union, Any

from flask import abort
from flask_sqlalchemy import Pagination
from flask_wtf import FlaskForm

from misc.engine import execute
from misc import (get_config, print_exc_info, EntityResult, name_city_state_search_clauses, entity_search_clauses,
                  OR_CONJUNC, AND_CONJUNC, SearchParams
                  )
from models import ARTIST_TABLE, VENUE_TABLE, SHOWS_TABLE, new_model_dict
from .artist_engine import datetime_to_str
from .controllers_misc import IGNORE_ID, model_property_list, FactoryObj, FILTER_PREVIOUS, FILTER_UPCOMING
from .show_orm import SHOWS_KEYS, AvailabilitySlot

# keys to extract data for db results
SHOWS_DICT = {p: p for p in SHOWS_KEYS}

SHOWS_PER_PAGE = get_config("SHOWS_PER_PAGE")


def show_factory_engine(obj_type: FactoryObj) -> Union[dict, str, None]:
    """
    Get a show related object
    :param obj_type: object type to get
    :return:
    """
    result = None
    if obj_type == FactoryObj.OBJECT:
        result = new_model_dict(SHOWS_TABLE)
    elif obj_type == FactoryObj.CLASS:
        result = SHOWS_TABLE
    return result


_FIELDS_LIST_ = f'"{SHOWS_TABLE}".venue_id, "{SHOWS_TABLE}".artist_id, "{SHOWS_TABLE}".start_time, ' \
                f'"{VENUE_TABLE}".name as venue_name, "{ARTIST_TABLE}".name as artist_name, ' \
                f'"{ARTIST_TABLE}".image_link as artist_image_link'
_FROM_JOIN_ = f'FROM (("{SHOWS_TABLE}" ' \
              f'INNER JOIN "{VENUE_TABLE}" ON "{SHOWS_TABLE}".venue_id = "{VENUE_TABLE}".id) ' \
              f'INNER JOIN "{ARTIST_TABLE}" ON "{SHOWS_TABLE}".artist_id = "{ARTIST_TABLE}".id)'


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
    search = SearchParams([VENUE_TABLE, ARTIST_TABLE], conjunction=[OR_CONJUNC, AND_CONJUNC])
    try:
        if filterby == FILTER_PREVIOUS:
            time_filter = f'"{SHOWS_TABLE}".start_time < \'{datetime_to_str(datetime.today())}\''
        elif filterby == FILTER_UPCOMING:
            time_filter = f'"{SHOWS_TABLE}".start_time > \'{datetime_to_str(datetime.today())}\''
        else:
            time_filter = None

        # get search terms and clauses for both Venue & Artist
        name_city_state_search_clauses(mode, form, search_term, search)

        if len(search.clauses) > 0:
            search_filter = entity_search_clauses('', search)
        else:
            search_filter = None

        filters = _combine_filters(search_filter, time_filter)

        # get total count
        sql = f'SELECT COUNT("{SHOWS_TABLE}".venue_id) {_FROM_JOIN_}{filters};'
        total = execute(sql).scalar()

        if total > 0:
            offset = SHOWS_PER_PAGE * (page - 1)
            if offset >= total:
                abort(HTTPStatus.BAD_REQUEST.value)
        else:
            offset = 0

        # get items for this request
        sql = f'SELECT {_FIELDS_LIST_} {_FROM_JOIN_}{filters} ' \
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
        sql = search_filter   # will have where in it
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
    ("mon_from", "mon_to"),     # monday
    ("tue_from", "tue_to"),     # tuesday
    ("wed_from", "wed_to"),     # wednesday
    ("thu_from", "thu_to"),     # thursday
    ("fri_from", "fri_to"),     # friday
    ("sat_from", "sat_to"),     # saturday
    ("sun_from", "sun_to"),     # sunday
]


def dow_availability_engine(availability: dict, dow: int):
    """
    Get availability for the specified day of the week
    :param availability:    availability info
    :param dow:             day of the week; 0=monday etc.
    """
    return AvailabilitySlot(start_time=availability[__DOW_TIMES__[dow][0]],
                            end_time=availability[__DOW_TIMES__[dow][1]])


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
