# ---------------------------------------------------------------------------- #
# Imports
# ---------------------------------------------------------------------------- #
from http import HTTPStatus
from typing import Union, AnyStr

from flask import request, abort
from flask_sqlalchemy import Model
from flask_wtf import FlaskForm

# ---------------------------------------------------------------------------- #
# Models.
# ---------------------------------------------------------------------------- #
from config import USE_ORM
from .misc import print_exc_info, str_or_none
from .queries_orm import AND_CONJUNC, SearchParams, ModelOrStr

ORM = USE_ORM
ENGINE = not ORM

if ORM:
    from .queries_orm import (
        entity_search_all_orm as entity_search_all,
        entity_search_like_orm as entity_search_like,
        entity_search_state_orm as entity_search_state,
        entity_search_clauses_orm as entity_search_clauses,
        entity_search_execute_orm as entity_search_execute,
        entity_shows_count_query_orm as entity_shows_count_query,
        venues_search_class_field_orm as venues_search_class_field,
        artists_search_class_field_orm as artists_search_class_field,
        shows_by_orm as shows_by,
        shows_by_artist_fields_orm as shows_by_artist_fields,
        shows_by_venue_fields_orm as shows_by_venue_fields,
        get_genres_options_orm as get_genres_options_impl,
)
else:
    from .queries_engine import (
        entity_search_all_engine as entity_search_all,
        entity_search_like_engine as entity_search_like,
        entity_search_state_engine as entity_search_state,
        entity_search_clauses_engine as entity_search_clauses,
        entity_search_execute_engine as entity_search_execute,
        entity_shows_count_query_engine as entity_shows_count_query,
        venues_search_class_field_engine as venues_search_class_field,
        artists_search_class_field_engine as artists_search_class_field,
        shows_by_engine as shows_by,
        shows_by_artist_fields_engine as shows_by_artist_fields,
        shows_by_venue_fields_engine as shows_by_venue_fields,
        get_genres_options_engine as get_genres_options_impl,
    )

CITY_STATE_SEARCH_SEPARATOR = ','
SEARCH_BASIC = 'basic'
SEARCH_ADVANCED = 'advanced'
SEARCH_ALL = 'all'


def basic_search_terms(search_term: str) -> tuple:
    """
    Extract basic search items
    :param search_term: search term to extract info from
    :return: tuple of (name, city, state)
    """
    name = None
    city = None
    state = None

    if search_term is not None:
        if CITY_STATE_SEARCH_SEPARATOR in search_term:
            # 'city, state' search
            comma = search_term.find(CITY_STATE_SEARCH_SEPARATOR)
            if comma > 0:
                city = search_term[0:comma].strip()
            comma = comma + len(CITY_STATE_SEARCH_SEPARATOR)
            state = search_term[comma:].strip()
            if len(state) == 0:
                state = None
        else:
            name = search_term.strip()

    return str_or_none(name), str_or_none(city), str_or_none(state)


def advances_search_terms(form: FlaskForm) -> tuple:
    """
    Extract advanced search items
    :param form: form to extract info from
    :return: tuple of (name, city, state, mode)
    """
    have_info = False
    name = None
    city = None
    state = None

    if form.name.data is not None and len(form.name.data) > 0:
        name = str_or_none(form.name.data)
        have_info = name is not None

    if form.city.data is not None and len(form.city.data) > 0:
        city = str_or_none(form.city.data)
        have_info = city is not None

    if form.state.data != 'none' and len(form.state.data) > 0:
        state = str_or_none(form.state.data)
        have_info = state is not None

    if have_info:
        mode = SEARCH_ADVANCED
    else:
        mode = SEARCH_BASIC  # no info, switch to basic mode

    return name, city, state, mode


def search_clauses(search: SearchParams) -> SearchParams:
    """
    Determine search clauses
    :param search: search parameters
    :return: list of search terms and list of clauses
    """
    search_terms = []
    clauses: list[list] = []
    record_term = True

    for entity_class in search.entity_classes:
        sub_clauses = []

        if search.name is not None:
            sub_clauses.append(
                entity_search_like(entity_class, "name", search.name))
            if record_term:
                search_terms.append(f'name: {search.name}')

        if search.city is not None:
            sub_clauses.append(
                entity_search_like(entity_class, "city", search.city))
            if record_term:
                search_terms.append(f'city: {search.city}')

        if search.state is not None and search.state != 'none':
            sub_clauses.append(
                entity_search_state(entity_class, search.state))
            if record_term:
                search_terms.append(f'state: {search.state}')

        if len(sub_clauses) == 0:
            break   # no terms
        clauses.append(sub_clauses)
        record_term = False

    search.search_terms = search_terms
    search.clauses = clauses
    if len(search.entity_classes) == 1:
        # if only 1 set of clauses, move it to level 0
        if len(clauses) > 0:
            search.clauses = clauses[0]
    else:
        # its a list of lists of clauses
        search.clauses = clauses

    return search


def name_city_state_search_clauses(mode: str, form: FlaskForm, search_term: str, search: SearchParams) -> SearchParams:
    """
    Determine search clauses
    :param mode:         one of 'basic', 'advanced' or 'all'
    :param form:         form data for advanced search
    :param search_term:  search_term for basic search
    :param search:       search parameters for advanced search
    :return: list of search terms and list of clauses
    """
    name = None
    city = None
    state = None

    if mode == SEARCH_ADVANCED:
        # advanced search based on name/city/state
        name, city, state, mode = advances_search_terms(form)

    if mode == SEARCH_BASIC:
        # basic name search
        name, city, state = basic_search_terms(search_term)

    search.name = name
    search.city = city
    search.state = state

    return search_clauses(search)


def name_city_state_search(mode: str, form: FlaskForm, entity_class: ModelOrStr, show_field: str):
    """
    Perform a search
    :param mode:         one of 'basic', 'advanced' or 'all'
    :param form:         form data
    :param entity_class: class of entity or name of table to search
    :param show_field:   show field linked to entity id
    :return dict with "count", "data", "search_term", "mode"
    """
    if mode not in [SEARCH_BASIC, SEARCH_ADVANCED, SEARCH_ALL]:
        abort(HTTPStatus.BAD_REQUEST.value)

    # basic 'all' mode query
    query = entity_search_all(entity_class)

    # advanced search on only one class, joining with 'and'
    search = SearchParams(entity_class, conjunction=AND_CONJUNC)
    name_city_state_search_clauses(mode, form, request.form.get('search_term', ''), search)

    # append query constraints
    query = entity_search_clauses(query, search)

    entities = []
    try:
        entities = entity_search_execute(query)
    except:
        print_exc_info()
        abort(HTTPStatus.INTERNAL_SERVER_ERROR.value)

    data = entity_shows_count(entities, show_field)

    return {
        "count": len(data),
        "data": data,
        "search_term": ', '.join(search.search_terms),
        "mode": mode
    }


def entity_shows_count(entities: list, show_field: str):
    """
    Perform a shows count search
    :param entities:   list of entities whose shows to search for
    :param show_field: show field linked to entity id
    """
    data = []
    try:
        data = entity_shows_count_query(entities, show_field)
    except:
        print_exc_info()
        abort(HTTPStatus.INTERNAL_SERVER_ERROR.value)

    return data


def venues_search(mode: str, form: FlaskForm):
    """
    Perform a search on venues
    :param mode:   one of 'basic', 'advanced' or 'all'
    :param form:   form data
    """
    return name_city_state_search(mode, form, *venues_search_class_field())


def artists_search(mode: str, form: FlaskForm):
    """
    Perform a search on artists
    :param mode:   one of 'basic', 'advanced' or 'all'
    :param form:   form data
    """
    return name_city_state_search(mode, form, *artists_search_class_field())


def _shows_by(entity_id, entity_class: Union[Model, AnyStr], link_field, show_field, keys, key_prefix: str, *criterion):
    """
    Select shows for the specified entity
    :param entity_id:    id of entity whose shows to search for
    :param entity_class: class of entity or name of table to search
    :param link_field:   show field linking show and entity
    :param show_field:   info field in show
    :param keys:         keys to access result fields
    :param criterion:    filtering criterion
    """
    shows = []
    try:
        shows = shows_by(entity_id, entity_class, link_field, show_field, *criterion)
    except:
        print_exc_info()
        abort(HTTPStatus.INTERNAL_SERVER_ERROR.value)

    # key is 'prefix_key' or 'start_time'
    # value is value or isoformat() for start_time
    def kval(k):
        return f'{key_prefix}_{k}' if k != "start_time" else k

    def vval(k, v):
        return v if k != "start_time" else v.isoformat()

    return [{kval(k): vval(k, show[v]) for k, v in keys.items()} for show in shows]


def shows_by_artist(artist_id: int, *criterion):
    """
    Select shows for the specified artist
    :param artist_id:  id of artist
    :param criterion:  filtering criterion
    """
    return _shows_by(artist_id, *shows_by_artist_fields(), "venue", *criterion)


def shows_by_venue(venue_id: int, *criterion):
    """
    Select shows for the specified venue
    :param venue_id:   id of venue
    :param criterion:  filtering criterion
    """
    return _shows_by(venue_id, *shows_by_venue_fields(), "artist", *criterion)


def get_genres_options():
    """
    Generate a list of possible genre options
    """
    genres = []
    try:
        genres = get_genres_options_impl()
    except:
        print_exc_info()
        abort(HTTPStatus.INTERNAL_SERVER_ERROR.value)

    options = [(g[0], g[0]) for g in genres if g[0] != 'Other']
    options.append(('Other', 'Other'))
    return options, [g[0] for g in options]
