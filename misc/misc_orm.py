from datetime import datetime
from http import HTTPStatus
from typing import Callable, Any, List

from flask import abort
from flask_sqlalchemy import Model
from werkzeug.datastructures import MultiDict

from models import Show, Genre, Artist, Venue, Entity
from .common import EntityResult, print_exc_info
from util import get_config


def get_music_entity_orm(entity_id: int, entity: Entity,
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
    elif result_type == EntityResult.MULTIDICT:
        data = MultiDict()
    else:
        data = None
    try:
        model_class = entity.orm_model
        instance = model_class.query.filter(model_class.id == entity_id).first()
        if instance is not None:
            exists = True
            if result_type == EntityResult.DICT:
                data = instance.get_dict(genres='name')
            elif result_type == EntityResult.MULTIDICT:
                data = instance.get_multidict(genres='name')
            else:   # EntityResult.MODEL
                data = entity

    except:
        print_exc_info()

    if not exists:
        abort(HTTPStatus.NOT_FOUND.value)

    return data


def get_show_summary_orm(entity_id: int, shows_by: Callable[[int, Any], List]) -> tuple:
    """
    Get the show summary for the given entity_id
    :param entity_id:        id of entity
    :param shows_by:         function taking of type 'shows_by(entity_id, criterion) -> list'
    """
    past_criterion = Show.start_time < datetime.now()
    future_criterion = Show.start_time >= datetime.now()

    past_shows = shows_by(entity_id, past_criterion)
    upcoming_shows = shows_by(entity_id, future_criterion)

    return past_shows, upcoming_shows


def exists_orm(entity: Model, entity_id: int):
    """
    Check if entity exists
    :param entity:      entity model
    :param entity_id:   id of entity to check
    """
    exists = False
    try:
        venue = entity.query \
            .with_entities(entity.id) \
            .filter(entity.id == entity_id) \
            .first()
        exists = (venue is not None)

    except:
        print_exc_info()
        abort(HTTPStatus.INTERNAL_SERVER_ERROR.value)

    return exists


def genre_list_orm(names: list):
    """
    Get the genres corresponding to the specified list
    :param names:   Genre names
    """
    return Genre.query.filter(Genre.name.in_(names)).all()


def latest_lists_orm() -> (list, list):
    num_latest = get_config("NUM_LATEST_ON_HOME")
    latest_artists = []
    latest_venues = []
    try:
        latest_artists = Artist.query \
            .with_entities(Artist.id, Artist.name) \
            .order_by(Artist.id.desc()) \
            .limit(num_latest)
        latest_venues = Venue.query \
            .with_entities(Venue.id, Venue.name) \
            .order_by(Venue.id.desc()) \
            .limit(num_latest)
    except:
        print_exc_info()
        abort(HTTPStatus.INTERNAL_SERVER_ERROR.value)

    return latest_artists, latest_venues
