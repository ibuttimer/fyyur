# ---------------------------------------------------------------------------- #
# Imports
# ---------------------------------------------------------------------------- #
from datetime import datetime
from typing import Union, AnyStr, NewType, List

from flask_sqlalchemy import Model
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Query
from wtforms import Field

# ---------------------------------------------------------------------------- #
# Models.
# ---------------------------------------------------------------------------- #
from .misc import check_no_list_in_list
from models import Venue, Artist, Show, Genre
from config import USE_ORM

ORM = USE_ORM
ENGINE = not ORM

SHOWS_BY_KEYS = ['id', 'start_time', 'name', 'image_link']
# indices to extract show results
SHOWS_BY_KEYS = {SHOWS_BY_KEYS[p]: p for p in range(len(SHOWS_BY_KEYS))}

AND_CONJUNC = 'and'
OR_CONJUNC = 'or'

ModelOrStr = NewType('ModelOrStr', Union[Model, AnyStr])
ListOfOrModelOrStr = NewType('ListOfOrModelOrStr', Union[ModelOrStr, List[ModelOrStr]])


def entity_search_all_orm(entity_class: Union[Artist, Venue]):
    """
    Basic 'all' mode query
    :param entity_class: class of entity or name of table to search
    """
    return entity_class.query \
        .with_entities(entity_class.id, entity_class.name)


def entity_search_like_orm(entity_class: Union[Artist, Venue], prop: str, value: str):
    """
    Like criteria
    :param entity_class:    class of entity or name of table to search
    :parameter prop:    property to apply 'like' criteria to
    :parameter value:       value for 'like' criteria
    """
    if prop == 'name':
        like = entity_class.name.ilike("%" + value + "%")
    elif prop == 'city':
        like = entity_class.city.ilike("%" + value + "%")
    else:
        like = None
    return like


def entity_search_state_orm(entity_class: Union[Artist, Venue], value: str):
    """
    State criteria
    :param entity_class:    class of entity or name of table to search
    :parameter value:       value for criteria
    """
    return func.upper(entity_class.state) == func.upper(value)


class SearchParams:
    """
    Class representing a search and its generated clauses
    :param entity_classes: class or classes to perform search for
    :param conjunction:    conjugation(s) to join clauses
    :param name:
    :param city:
    :param state:
    """
    def __init__(self, entity_classes: ListOfOrModelOrStr, conjunction: Union[str, list] = None,
                 name: str = None, city: str = None, state: str = None):
        if not isinstance(entity_classes, list):
            self.entity_classes = [entity_classes]
        else:
            self.entity_classes = entity_classes
        self.name = name
        self.city = city
        self.state = state
        self.conjunction = conjunction
        self.search_terms = []
        self.clauses = []


def entity_search_clauses_orm(query: Query, search: SearchParams):
    """
    Append clauses
    :param query:    query to append clauses to
    :param search:   search parameters for advanced search
    """
    expression = entity_search_expression_orm(search.clauses, search.conjunction)
    if expression is not None:
        query = query.filter(expression)
    return query


def conjunction_op(conjunction: str, *terms):
    """
    Create an expression joining the terms
    :param conjunction: conjunction to use to join terms
    :param terms:       terms to join
    :return:
    """
    return and_(*terms) if conjunction == AND_CONJUNC else or_(*terms)


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


def entity_search_execute_orm(query: Query):
    """
    Execute query
    :param query:           query to execute
    """
    return query.all()


def entity_shows_count_query_orm(entities: list, show_field: str):
    """
    Get the shows count search query
    :param entities:   list of entities whose shows to search for
    :param show_field: show field linked to entity id
    """
    data = []
    for entity in entities:
        shows = Show.query \
            .filter(and_(show_field == entity.id, Show.start_time > datetime.now())) \
            .count()

        data.append({
            "id": entity.id,
            "name": entity.name,
            "num_upcoming_shows": shows
        })

    return data


def venues_search_class_field_orm() -> (Venue, Field):
    """
    Class and field for a search on venues
    """
    return Venue, Show.venue_id


def artists_search_class_field_orm() -> (Artist, Field):
    """
    Class and field for a search on artists
    """
    return Artist, Show.artist_id


def shows_by_orm(entity_id, entity_class: Union[Model, AnyStr], link_field, show_field, *criterion):
    """
    Select shows for the specified entity
    :param entity_id:    id of entity whose shows to search for
    :param entity_class: class of entity or name of table to search
    :param link_field:   show field linking show and entity
    :param show_field:   info field in show
    :param criterion:    filtering criterion
    """
    return Show.query.join(entity_class, show_field == entity_class.id) \
        .with_entities(show_field, Show.start_time, entity_class.name, entity_class.image_link) \
        .filter(and_(link_field == entity_id, *criterion)) \
        .order_by(Show.start_date) \
        .all()


def shows_by_artist_fields_orm():
    """
    Select shows for the specified artist
    """
    return Venue, Show.artist_id, Show.venue_id, SHOWS_BY_KEYS


def shows_by_venue_fields_orm():
    """
    Select shows for the specified venue
    """
    return Artist, Show.venue_id, Show.artist_id, SHOWS_BY_KEYS


def get_genres_options_orm():
    """
    Generate a list of possible genre options
    """
    return Genre.query.with_entities(Genre.name).order_by(Genre.name).all()

