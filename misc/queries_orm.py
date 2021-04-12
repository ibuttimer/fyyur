# ---------------------------------------------------------------------------- #
# Imports
# ---------------------------------------------------------------------------- #
from datetime import datetime
from typing import Union, AnyStr, NewType, List, Callable

from flask_sqlalchemy import Model
from sqlalchemy import and_, func, or_, Column
from sqlalchemy.orm import Query

from config import USE_ORM
# ---------------------------------------------------------------------------- #
# Models.
# ---------------------------------------------------------------------------- #
from .common import SearchParams
from models import Show, Genre, Entity, VENUE_TABLE, get_entity, ARTIST_TABLE

ORM = USE_ORM
ENGINE = not ORM

SHOWS_BY_KEYS = ['id', 'start_time', 'name', 'image_link']
# indices to extract show results
SHOWS_BY_KEYS = {SHOWS_BY_KEYS[p]: p for p in range(len(SHOWS_BY_KEYS))}

AND_CONJUNC = 'and'
OR_CONJUNC = 'or'

ModelOrStr = NewType('ModelOrStr', Union[Model, AnyStr])
ListOfOrModelOrStr = NewType('ListOfOrModelOrStr', Union[ModelOrStr, List[ModelOrStr]])


def entity_search_all_orm(entity: Entity, search: SearchParams) -> Query:
    """
    Basic 'all' mode query
    :param entity: entity to search
    :param search:  search parameters for advanced search
    """
    model_class = entity.orm_model
    query = model_class.query
    # add any joins
    if search.customisation is not None:
        for j in search.customisation:
            query = query.join(j)
    return query \
        .with_entities(model_class.id, model_class.name)


def entity_search_like_orm(entity: Entity, prop: str, value: str):
    """
    Like criteria
    :param entity:      entity to search
    :parameter prop:    property to apply 'like' criteria to
    :parameter value:   value for 'like' criteria
    """
    if prop == 'name':
        like = entity.orm_model.name.ilike("%" + value + "%")
    elif prop == 'city':
        like = entity.orm_model.city.ilike("%" + value + "%")
    else:
        like = None
    return like


def entity_search_state_orm(entity: Entity, value: str):
    """
    State criteria
    :param entity:    entity to search
    :parameter value: value for criteria
    """
    return func.upper(entity.orm_model.state) == func.upper(value)


def entity_search_genres_orm(entity: Entity, values: list, search: SearchParams):
    """
    Genres criteria
    :param entity:  entity to search
    :param values:  values for criteria
    :param search:  search parameters for advanced search
    """
    return or_(*[
            entity.orm_model.genres.any(Genre.name == g) for g in values
        ])


def entity_search_clauses_orm(query: Query, search: SearchParams, entity_search_expression: Callable):
    """
    Append clauses
    :param query:                       query to append clauses to
    :param search:                      search parameters for advanced search
    :param entity_search_expression:    function to join query
    """
    expression = entity_search_expression(search.clauses, search.conjunction)
    if expression is not None:
        query = query.filter(expression)
    return query


def conjunction_op_orm(conjunction: str, *terms):
    """
    Create an expression joining the terms
    :param conjunction: conjunction to use to join terms
    :param terms:       terms to join
    :return:
    """
    return and_(*terms) if conjunction == AND_CONJUNC else or_(*terms)


def entity_search_execute_orm(query: Query):
    """
    Execute query
    :param query:           query to execute
    """
    return query.all()


def entity_shows_count_query_orm(entities: list, entity: Entity):
    """
    Get the shows count search query
    :param entities:    list of entities whose shows to search for
    :param entity:      entity to search for
    """
    data = []
    for instance in entities:
        shows = Show.query \
            .filter(and_(entity.orm_show_column == instance.id, Show.start_time > datetime.now())) \
            .count()

        data.append({
            "id": instance.id,
            "name": instance.name,
            "num_upcoming_shows": shows
        })

    return data


def shows_by_orm(entity_id: int, entity: Entity, link_column: Column, *criterion):
    """
    Select shows for the specified entity
    :param entity_id:    id of entity whose shows to search for
    :param entity:       entity to search for
    :param link_column:  show column linking show and entity
    :param criterion:    filtering criterion
    """
    model_class = entity.orm_model        # entity model
    show_column = entity.orm_show_column  # foreign key column in show model linking show and entity
    return Show.query.join(model_class, show_column == model_class.id) \
        .with_entities(show_column, Show.start_time, model_class.name, model_class.image_link) \
        .filter(and_(link_column == entity_id, *criterion)) \
        .order_by(Show.start_date) \
        .all()


def shows_by_artist_fields_orm() -> (Entity, Column, list[str]):
    """
    Select shows for the specified artist
    """
    # select Show.venue_id, Show.start_time, Venue.name, Venue.image_link
    # join Show and Venue on Show.venue_id == Venue.id
    # where Show.artist_id == entity_id
    return get_entity(VENUE_TABLE), get_entity(ARTIST_TABLE).orm_show_column, SHOWS_BY_KEYS


def shows_by_venue_fields_orm() -> (Entity, Column, list[str]):
    """
    Select shows for the specified venue
    """
    # select Show.artist_id, Show.start_time, Artist.name, Artist.image_link
    # join Show and Artist on Show.artist_id == Artist.id
    # where Show.venue_id == entity_id
    return get_entity(ARTIST_TABLE), get_entity(VENUE_TABLE).orm_show_column, SHOWS_BY_KEYS


def get_genres_options_orm():
    """
    Generate a list of possible genre options
    """
    return Genre.query.with_entities(Genre.name).order_by(Genre.name).all()

