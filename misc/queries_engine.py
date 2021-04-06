# ---------------------------------------------------------------------------- #
# Imports
# ---------------------------------------------------------------------------- #
from typing import Union, AnyStr

from flask_sqlalchemy import Model

# ---------------------------------------------------------------------------- #
# Models.
# ---------------------------------------------------------------------------- #
from .queries_orm import SHOWS_BY_KEYS, SearchParams, AND_CONJUNC
from .engine import execute
from .misc import check_no_list_in_list
from models import ARTIST_TABLE, VENUE_TABLE, SHOWS_TABLE, GENRES_TABLE
from config import USE_ORM

ORM = USE_ORM
ENGINE = not ORM

SHOWS_BY_ARTIST_KEYS = {k: f'venue_{k}' if k == 'id' else k for k in SHOWS_BY_KEYS}
SHOWS_BY_VENUE_KEYS = {k: f'artist_{k}' if k == 'id' else k for k in SHOWS_BY_KEYS}


def entity_search_all_engine(entity_class: str):
    """
    Basic 'all' mode query
    :param entity_class: class of entity or name of table to search
    """
    return f'SELECT id, name FROM "{entity_class}"'


def entity_search_like_engine(entity_class: str, prop: str, value: str):
    """
    Like criteria
    :param entity_class:    class of entity or name of table to search
    :parameter prop:        property to apply 'like' criteria to
    :parameter value:       value for 'like' criteria
    """
    if prop in ['name', 'city']:
        like = f'LOWER("{entity_class}".{prop}) LIKE LOWER(\'%{value}%\')'
    else:
        like = None
    return like


def entity_search_state_engine(entity_class: str, value: str):
    """
    State criteria
    :param entity_class:    class of entity or name of table to search
    :parameter value:       value for criteria
    """
    return f'UPPER("{entity_class}".state) = UPPER(\'{value}\')'


def entity_search_clauses_engine(query: str, search: SearchParams):
    """
    Append clauses
    :param query:    query to append clauses to
    :param search:   search parameters for advanced search
    """
    expression = entity_search_expression_orm(search.clauses, search.conjunction)
    if expression is not None:
        query = f'{query} WHERE {expression}'
    return query


def conjunction_op(conjunction: str, *terms:  list):
    """
    Create an expression joining the terms
    :param conjunction: conjunction to use to join terms
    :param terms:       terms to join
    :return:
    """
    joined = " AND ".join(terms) if conjunction == AND_CONJUNC else " OR ".join(terms)
    return f"({joined})"


def entity_search_expression_orm(terms: list, conjunction: Union[str, list[str]]):
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


def entity_search_execute_engine(query: str):
    """
    Execute query
    :param query:           query to execute
    """
    return execute(query + ";")


def entity_shows_count_query_engine(entities: list, show_field: str):
    """
    Get the shows count search query
    :param entities:   list of entities whose shows to search for
    :param show_field: show field linked to entity id
    """
    data = []
    for entity in entities:
        shows = execute(
            f'SELECT COUNT(id) FROM "{SHOWS_TABLE}" WHERE {show_field} = {entity["id"]} '
            f'AND start_time > CURRENT_TIMESTAMP;')
        shows = shows.scalar()

        data.append({
            "id": entity.id,
            "name": entity.name,
            "num_upcoming_shows": shows
        })

    return data


def venues_search_class_field_engine() -> (str, str):
    """
    Class and field for a search on venues
    """
    return VENUE_TABLE, 'venue_id'


def artists_search_class_field_engine() -> (str, str):
    """
    Class and field for a search on artists
    """
    return ARTIST_TABLE, 'artist_id'


def shows_by_engine(entity_id, entity_class: Union[Model, AnyStr], link_field, show_field, *criterion):
    """
    Select shows for the specified entity
    :param entity_id:    id of entity whose shows to search for
    :param entity_class: class of entity or name of table to search
    :param link_field:   show field linking show and entity
    :param show_field:   info field in show
    :param criterion:    filtering criterion
    """
    shows = execute(f'SELECT {show_field}, "{SHOWS_TABLE}".start_time, '
                    f'"{entity_class}".name, "{entity_class}".image_link FROM "{SHOWS_TABLE}" '
                    f'INNER JOIN "{entity_class}" ON {show_field} = "{entity_class}".id '
                    f'WHERE {link_field} = {entity_id} AND {" AND ".join(criterion)} '
                    f'ORDER BY "{SHOWS_TABLE}".start_time;')
    return shows.fetchall()


def shows_by_artist_fields_engine():
    """
    Select shows for the specified artist
    """
    return VENUE_TABLE, f'"{SHOWS_TABLE}".artist_id', f'"{SHOWS_TABLE}".venue_id', SHOWS_BY_ARTIST_KEYS


def shows_by_venue_fields_engine():
    """
    Select shows for the specified venue
    """
    return ARTIST_TABLE, f'"{SHOWS_TABLE}".venue_id', f'"{SHOWS_TABLE}".artist_id', SHOWS_BY_VENUE_KEYS


def get_genres_options_engine():
    """
    Generate a list of possible genre options
    """
    return execute(f'SELECT name FROM "{GENRES_TABLE}" ORDER BY name;')
