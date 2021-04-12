# ---------------------------------------------------------------------------- #
# Imports
# ---------------------------------------------------------------------------- #
from http import HTTPStatus
from typing import Union

from flask import abort
from flask_wtf import FlaskForm
# ---------------------------------------------------------------------------- #
# Models.
# ---------------------------------------------------------------------------- #
from sqlalchemy import Column

from config import USE_ORM
from forms import NO_STATE_SELECTED
from models import Entity, get_entity, VENUE_TABLE, ARTIST_TABLE
from .common import SP_NAME, SP_CITY, SP_STATE, SP_GENRES, SearchParams
from .misc import print_exc_info, str_or_none, check_no_list_in_list
from .queries_orm import AND_CONJUNC

ORM = USE_ORM
ENGINE = not ORM

if ORM:
    from .queries_orm import (
        entity_search_all_orm as entity_search_all,
        entity_search_like_orm as entity_search_like,
        entity_search_state_orm as entity_search_state,
        entity_search_genres_orm as entity_search_genres,
        entity_search_clauses_orm as entity_search_clauses,
        conjunction_op_orm as conjunction_op,
        entity_search_execute_orm as entity_search_execute,
        entity_shows_count_query_orm as entity_shows_count_query,
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
        entity_search_genres_engine as entity_search_genres,
        entity_search_clauses_engine as entity_search_clauses,
        conjunction_op_engine as conjunction_op,
        entity_search_execute_engine as entity_search_execute,
        entity_shows_count_query_engine as entity_shows_count_query,
        shows_by_engine as shows_by,
        shows_by_artist_fields_engine as shows_by_artist_fields,
        shows_by_venue_fields_engine as shows_by_venue_fields,
        get_genres_options_engine as get_genres_options_impl,
    )

CITY_STATE_SEARCH_SEPARATOR = ','
SEARCH_BASIC = 'basic'
SEARCH_ADVANCED = 'advanced'
SEARCH_ALL = 'all'


def ncs_search_terms(search_term: str) -> tuple:
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


def ncsg_search_terms(search: SearchParams) -> tuple:
    """
    Extract advanced search items
    :param search: search parameters
    :return: tuple of (name, city, state, genres, mode)
    """
    have_info = False
    name = None
    city = None
    state = None
    genres = []

    if search.name is not None and len(search.name) > 0:
        name = str_or_none(search.name)
        have_info = name is not None

    if search.city is not None and len(search.city) > 0:
        city = str_or_none(search.city)
        have_info = city is not None

    if search.state is not None and search.state != NO_STATE_SELECTED and len(search.state) > 0:
        state = str_or_none(search.state)
        have_info = state is not None

    if search.genres is not None and len(search.genres) > 0:
        genres = search.genres
        have_info = True

    if have_info:
        mode = SEARCH_ADVANCED
    else:
        mode = SEARCH_BASIC  # no info, switch to basic mode

    return name, city, state, genres, mode


def search_clauses(search: SearchParams) -> SearchParams:
    """
    Determine search clauses
    :param search: search parameters
    :return: list of search terms and list of clauses
    """
    search_terms = []
    clauses: list[list] = []
    record_term = True

    for entity in search.entities:
        sub_clauses = []

        if search.name is not None:
            sub_clauses.append(
                entity_search_like(entity, SP_NAME, search.name))
            if record_term:
                search_terms.append(f'name: {search.name}')
                search.searching_on[SP_NAME] = True

        if search.city is not None:
            sub_clauses.append(
                entity_search_like(entity, SP_CITY, search.city))
            if record_term:
                search_terms.append(f'city: {search.city}')
                search.searching_on[SP_CITY] = True

        if search.state is not None and search.state != NO_STATE_SELECTED:
            sub_clauses.append(
                entity_search_state(entity, search.state))
            if record_term:
                search_terms.append(f'state: {search.state}')
                search.searching_on[SP_STATE] = True

        if search.genres is not None and len(search.genres) > 0:
            sub_clauses.append(
                entity_search_genres(entity, search.genres, search))
            if record_term:
                search_terms.append(f'genres: {" or ".join(search.genres)}')
                search.searching_on[SP_GENRES] = True

        if len(sub_clauses) == 0:
            break   # no terms
        clauses.append(sub_clauses)
        record_term = False

    search.search_terms = search_terms
    search.clauses = clauses
    if len(search.entities) == 1:
        # if only 1 set of clauses, move it to level 0
        if len(clauses) > 0:
            search.clauses = clauses[0]
    else:
        # its a list of lists of clauses
        search.clauses = clauses

    return search


def ncsg_search_clauses(mode: str, search: SearchParams) -> SearchParams:
    """
    Determine clauses for name, city, state, genre search
    :param mode:         one of 'basic', 'advanced' or 'all'
    :param search:       search parameters for search
    :return: list of search terms and list of clauses
    """
    name = None
    city = None
    state = None
    genres = None

    if mode == SEARCH_ADVANCED:
        # advanced search based on name/city/state/genre
        name, city, state, genres, mode = ncsg_search_terms(search)

    if mode == SEARCH_BASIC:
        # basic name search
        name, city, state = ncs_search_terms(search.simple_search_term)

    search.name = name
    search.city = city
    search.state = state
    search.genres = genres

    return search_clauses(search)


def ncsg_search(mode: str, form: FlaskForm, entity: Entity, simple_search_term: str = None) -> dict:
    """
    Perform a search
    :param mode:        one of 'basic', 'advanced' or 'all'
    :param form:        form data
    :param entity:      entity to search for
    :param simple_search_term:  search term for basic search
    :return dict with "count", "data", "search_term", "mode"
    """
    if mode not in [SEARCH_BASIC, SEARCH_ADVANCED, SEARCH_ALL]:
        abort(HTTPStatus.BAD_REQUEST.value)

    # advanced search on only one class, joining with 'and'
    search = SearchParams(entity, conjunction=AND_CONJUNC).load_form(form)
    search.simple_search_term = simple_search_term
    ncsg_search_clauses(mode, search)

    # basic 'all' mode query
    query = entity_search_all(entity, search)

    # append query constraints
    query = entity_search_clauses(query, search, entity_search_expression)

    entities = []
    try:
        entities = entity_search_execute(query)
    except:
        print_exc_info()
        abort(HTTPStatus.INTERNAL_SERVER_ERROR.value)

    data = entity_shows_count(entities, entity)

    return {
        "count": len(data),
        "data": data,
        "search_term": ', '.join(search.search_terms),
        "mode": mode
    }


def entity_shows_count(entities: list, entity: Entity):
    """
    Perform a shows count search
    :param entities:    list of entities whose shows to search for
    :param entity:      entity to search for
    """
    data = []
    try:
        data = entity_shows_count_query(entities, entity)
    except:
        print_exc_info()
        abort(HTTPStatus.INTERNAL_SERVER_ERROR.value)

    return data


def venues_search(mode: str, form: FlaskForm, simple_search_term: str = None) -> dict:
    """
    Perform a search on venues
    :param mode:   one of 'basic', 'advanced' or 'all'
    :param form:   form data
    :param simple_search_term:  search term for basic search
    """
    return ncsg_search(mode, form, get_entity(VENUE_TABLE), simple_search_term=simple_search_term)


def artists_search(mode: str, form: FlaskForm, simple_search_term: str = None) -> dict:
    """
    Perform a search on artists
    :param mode:   one of 'basic', 'advanced' or 'all'
    :param form:   form data
    :param simple_search_term:  search term for basic search
    """
    return ncsg_search(mode, form, get_entity(ARTIST_TABLE), simple_search_term=simple_search_term)


def _shows_by(entity_id: int, entity: Entity, link_field: Column, keys: dict, key_prefix: str, *criterion):
    """
    Select shows for the specified entity
    :param entity_id:    id of entity whose shows to search for
    :param entity:       entity to search for
    :param link_field:   show field linking show and entity
    :param keys:         keys to access result fields
    :param key_prefix:   prefix to combine with keys to generate result fields
    :param criterion:    filtering criterion
    """
    shows = []
    try:
        shows = shows_by(entity_id, entity, link_field, *criterion)
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


def entity_search_expression(terms: list, conjunction: Union[str, list[str]]):
    """
    Join terms
    :param terms:       terms to join; a list of terms, or a list of lists of terms
    :param conjunction: conjunction to join terms; 'and' or 'or
    """
    expression = None

    if terms is not None and len(terms) > 0:
        if not isinstance(conjunction, list):
            conjunction = [conjunction]

        if len(conjunction) == 1:
            # expecting a list with 1 or more clauses
            check_no_list_in_list(terms)

            if len(terms) == 1:
                # single clause no conjunction necessary
                expression = terms[0]
            elif len(terms) > 1:
                # join clauses using conjunction
                expression = conjunction_op(conjunction[0], *terms)
            else:
                raise ValueError("Found empty list when expecting at least one entry")

        elif len(conjunction) == 2:
            # expecting a list of lists with 1 or more clauses
            if not isinstance(terms, list):
                raise ValueError("Expecting list of lists of clauses")
            else:
                for sub_term in terms:
                    check_no_list_in_list(sub_term)

            # create level 1 terms with level 1 conjunction
            level1 = [conjunction_op(conjunction[1], *t) for t in terms]
            # join level 1 terms with level 0 conjunction
            expression = conjunction_op(conjunction[0], *level1)
        else:
            raise NotImplemented("Expressions beyond 2 levels not supported")

    return expression
