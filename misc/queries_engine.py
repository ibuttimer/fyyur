# ---------------------------------------------------------------------------- #
# Imports
# ---------------------------------------------------------------------------- #
from typing import Callable

from config import USE_ORM
from models import ARTIST_TABLE, VENUE_TABLE, SHOWS_TABLE, GENRES_TABLE, Entity, fq_column, get_entity
from .engine import execute
# ---------------------------------------------------------------------------- #
# Models.
# ---------------------------------------------------------------------------- #
from .queries_orm import SHOWS_BY_KEYS, AND_CONJUNC, OR_CONJUNC
from .common import SearchParams

ORM = USE_ORM
ENGINE = not ORM

SHOWS_BY_ARTIST_KEYS = {k: f'venue_{k}' if k == 'id' else k for k in SHOWS_BY_KEYS}
SHOWS_BY_VENUE_KEYS = {k: f'artist_{k}' if k == 'id' else k for k in SHOWS_BY_KEYS}


def entity_search_all_engine(entity: Entity, search: SearchParams) -> str:
    """
    Basic 'all' mode query
    :param entity: entity to search
    :param search:  search parameters for advanced search
    """
    from_term = search.customisation if search.customisation is not None else f'"{entity.eng_table}"'
    return f'SELECT {entity.fq_id()}, {entity.fq_column("name")} FROM {from_term}'


def entity_search_like_engine(entity: Entity, prop: str, value: str) -> str:
    """
    Like criteria
    :param entity:      entity to search
    :parameter prop:    property to apply 'like' criteria to
    :parameter value:   value for 'like' criteria
    """
    if prop in ['name', 'city']:
        like = f'LOWER({fq_column(entity.eng_table, prop)}) LIKE LOWER(\'%{value}%\')'
    else:
        like = None
    return like


def join_engine(left: str, right: str, left_col: str, right_col: str, join_type: str = 'INNER') -> str:
    if 'JOIN' not in left:
        join_to = f'"{left}"'
    else:
        join_to = left     # no "" for nested join
    if ' as ' not in right:
        joiner = f'"{right}"'
    else:
        joiner = right   # no "" for alias
    return f'({join_to} {join_type} JOIN {joiner} ON {left_col} = {right_col}) '


def entity_search_state_engine(entity: Entity, value: str) -> str:
    """
    State criteria
    :param entity:    entity to search
    :parameter value: value for criteria
    """
    return f'UPPER({fq_column(entity.eng_table, "state")}) = UPPER(\'{value}\')'


def entity_search_genres_engine(entity: Entity, values: list, search: SearchParams) -> str:
    """
    Genres criteria
    :param entity:  entity to search
    :param values:  values for criteria
    :param search:  search parameters for advanced search
    """
    genre_term = f'{fq_column(GENRES_TABLE, "name")}'
    idx = search.entities.index(entity)
    if len(search.genre_aliases) > idx:
        if search.genre_aliases[idx] is not None:
            genre_term = f'{search.genre_aliases[idx]}.name'

    terms = [f'{genre_term} = \'{g}\'' for g in values]
    # ((inner join 'entity table' and 'genre link table')
    #       inner join 'genres table')
    search.customisation = \
        join_engine(
            join_engine(entity.eng_table, entity.eng_genre_link_table,
                        entity.fq_genre_link(), entity.fq_id()),
            GENRES_TABLE,
            fq_column(entity.eng_genre_link_table, "genre_id"), fq_column(GENRES_TABLE, "id"))

    return conjunction_op_engine(OR_CONJUNC, *terms)


def entity_search_clauses_engine(query: str, search: SearchParams, entity_search_expression: Callable):
    """
    Append clauses
    :param query:                       query to append clauses to
    :param search:                      search parameters for advanced search
    :param entity_search_expression:    function to join query
    """
    expression = entity_search_expression(search.clauses, search.conjunction)
    if expression is not None:
        query = f'{query} WHERE {expression}'
    return query


def conjunction_op_engine(conjunction: str, *terms: list):
    """
    Create an expression joining the terms
    :param conjunction: conjunction to use to join terms
    :param terms:       terms to join
    :return:
    """
    joined = " AND ".join(terms) if conjunction == AND_CONJUNC else " OR ".join(terms)
    return f"({joined})"


def entity_search_execute_engine(query: str):
    """
    Execute query
    :param query:           query to execute
    """
    return execute(query + ";")


def entity_shows_count_query_engine(entities: list, entity: Entity):
    """
    Get the shows count search query
    :param entities:    list of entities whose shows to search for
    :param entity:      entity to search for
    """
    data = []
    for instance in entities:
        shows = execute(
            f'SELECT COUNT(id) FROM "{SHOWS_TABLE}" WHERE {entity.eng_show_column} = {instance["id"]} '
            f'AND start_time > CURRENT_TIMESTAMP;')
        shows = shows.scalar()

        data.append({
            "id": instance.id,
            "name": instance.name,
            "num_upcoming_shows": shows
        })

    return data


def shows_by_engine(entity_id, entity: Entity, link_column: str, *criterion):
    """
    Select shows for the specified entity
    :param entity_id:    id of entity whose shows to search for
    :param entity:       entity to search for
    :param link_column:  show column linking show and entity
    :param criterion:    filtering criterion
    """
    show_column = entity.eng_show_column  # foreign key column in show model linking show and entity
    shows = execute(f'SELECT {show_column}, {fq_column(SHOWS_TABLE, "start_time")}, '
                    f'{fq_column(entity.eng_table, "name")}, {fq_column(entity.eng_table, "image_link")} FROM "{SHOWS_TABLE}" '
                    f'INNER JOIN "{entity.eng_table}" ON {show_column} = {fq_column(entity.eng_table, "id")} '
                    f'WHERE {link_column} = {entity_id} AND {" AND ".join(criterion)} '
                    f'ORDER BY "{SHOWS_TABLE}".start_time;')
    return shows.fetchall()


def shows_by_artist_fields_engine() -> (Entity, str, list[str]):
    """
    Select shows for the specified artist
    """
    # select Show.venue_id, Show.start_time, Venue.name, Venue.image_link
    # join Show and Venue on Show.venue_id == Venue.id
    # where Show.artist_id == entity_id
    return get_entity(VENUE_TABLE), get_entity(ARTIST_TABLE).eng_show_column, SHOWS_BY_ARTIST_KEYS


def shows_by_venue_fields_engine() -> (Entity, str, list[str]):
    """
    Select shows for the specified venue
    """
    # select Show.artist_id, Show.start_time, Artist.name, Artist.image_link
    # join Show and Artist on Show.artist_id == Artist.id
    # where Show.venue_id == entity_id
    return get_entity(ARTIST_TABLE), get_entity(VENUE_TABLE).eng_show_column, SHOWS_BY_VENUE_KEYS


def get_genres_options_engine():
    """
    Generate a list of possible genre options
    """
    return execute(f'SELECT name FROM "{GENRES_TABLE}" ORDER BY name;')
