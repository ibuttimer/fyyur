import re
from datetime import datetime
from enum import Enum
from http import HTTPStatus
from typing import Callable, Union, Any, List, AnyStr

from flask import abort, redirect, flash, url_for
from flask_sqlalchemy import Model
from flask_wtf import FlaskForm
from wtforms import SelectMultipleField

from forms import AVAILABILITY_FROM_DATE_FMT, set_multiselect_field_options, populate_model, populate_model_property
from misc import print_exc_info, get_genre_list
from models import model_property_list as models_model_property_list
from misc.queries import get_genres_options
from config import USE_ORM

ORM = USE_ORM
ENGINE = not ORM

if ORM:
    from misc.misc_orm import (
        get_show_summary_orm as get_show_summary,
        exists_orm as exists_impl,
    )

else:
    from misc.misc_engine import (
        get_show_summary_engine as get_show_summary,
        exists_engine as exists_impl,
    )


IGNORE_ID = ['id']
IGNORE_ID_GENRES = ["id", "genres"]


def set_genre_field_options(field: SelectMultipleField, data: list, required: bool = True):
    """
    Set a genres field options
    :param field:   form field
    :param data:    value(s) to set
    :param required:   selection required flag
    """
    choices, values = get_genres_options()
    set_multiselect_field_options(field, choices, values, data, required=required)


def model_property_list(model: Union[Model, dict], ignore=None) -> list:
    """
    Get the list of property names from a SQLAlchemy model
    :param model:  model to get property names from
    :param ignore: names to ignore
    """
    if ignore is None:
        ignore = []
    if isinstance(model, dict):
        return [key for key in model.keys() if key not in ignore]
    else:
        # need to inspect, as if model object is empty it will have no items in its dict
        return models_model_property_list(model, ignore=ignore)


RE_DATETIME = re.compile(r'(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})')


def get_availability_date(query_date):
    if query_date is not None:
        match = RE_DATETIME.match(query_date)
        if match:
            query_date = datetime.strptime(match[1] + ' ' + match[2], AVAILABILITY_FROM_DATE_FMT)
        else:
            query_date = datetime.today()
    return query_date


def add_show_summary(entity_id: int, entity: dict,
                     shows_by: Callable[[int, Any], List]):
    """
    Add show summary to entity
    :param entity_id:        id of entity
    :param entity:           entity to add to
    :param shows_by:         function taking of type 'shows_by(entity_id, criterion) -> list'
    """
    past_shows, upcoming_shows = get_show_summary(entity_id, shows_by)
    entity["past_shows"] = past_shows
    entity["upcoming_shows"] = upcoming_shows
    entity["past_shows_count"] = len(past_shows)
    entity["upcoming_shows_count"] = len(upcoming_shows)

    return entity


def __flash_result(success, name, entity_type, action):
    """
    Flash result
    :param success:      action result; boolean or None
    :param name:         name of entity
    :param entity_type:  type of entity
    :param action:       action
    """
    if success:
        flash(f'{entity_type} {name} was successfully {action}!')
    elif success is not None:
        flash(f'An error occurred. {entity_type} {name} could not be {action}.')
    # else no message necessary


def update_result(success, name, entity_type, url):
    """
    Delete result
    :param success:      action result; boolean or None
    :param name:         name of entity
    :param entity_type:  type of entity
    :param url:          url to redirect to
    """
    __flash_result(success, name, entity_type, 'updated')
    return redirect(url)


def create_result(success, name, entity_type):
    """
    Create result
    :param success:      action result; boolean or None
    :param name:         name of entity
    :param entity_type:  type of entity
    """
    __flash_result(success, name, entity_type, 'listed')
    return redirect(url_for('index'))


def delete_result(success, name, entity_type):
    """
    Delete result
    :param success:      action result; boolean or None
    :param name:         name of entity
    :param entity_type:  type of entity
    """
    __flash_result(success, name, entity_type, 'deleted')
    return {'success': success, 'redirect': url_for('index')}


def exists_or_404(entity: Union[Model, AnyStr], entity_id: int):
    """
    Check if entity exists, or abort with 404
    :param entity:      entity model or name of table to search
    :param entity_id:   id of entity to check
    """
    exists = False
    try:
        exists = exists_impl(entity, entity_id)
    except:
        print_exc_info()
        abort(HTTPStatus.INTERNAL_SERVER_ERROR.value)

    if not exists:
        abort(HTTPStatus.NOT_FOUND.value)


class FactoryObj(Enum):
    OBJECT = 1  # return a Model or a dict
    CLASS = 2   # return Model class or table name


FILTER_ALL = 'all'
FILTER_PREVIOUS = 'previous'
FILTER_UPCOMING = 'upcoming'


def populate_genred_model(model: Union[Model, dict], form: FlaskForm, properties: list):
    """
    Populate a model with genres from a form
    :param model:       entity to populate
    :param form:        form to populate from
    :param properties:  list of properties to populate
    """
    populate_model(model, form, properties)
    genres = get_genre_list(form["genres"].data)
    populate_model_property(model, "genres", genres)
    return model
