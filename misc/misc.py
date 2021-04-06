from datetime import datetime
from http import HTTPStatus
from typing import Union

from flask_sqlalchemy import Model
from werkzeug.exceptions import abort

from .common import print_exc_info
from config import USE_ORM

ORM = USE_ORM
ENGINE = not ORM

if ORM:
    from .misc_orm import (
        genre_list_orm as genre_list,
    )

else:
    from .misc_engine import (
        genre_list_engine as genre_list,
    )


def label_from_valuelabel_list(valuelabel, value):
    """
    Get the label corresponding to a value from a list of (value, label) pairs
    :param valuelabel: list of (value, label) pairs
    :param value:      value to search for
    """
    label = None
    for vl in valuelabel:
        if vl[0] == value:
            label = vl[1]
            break
    return label


def current_datetime():
    """ Current datetime to minute accuracy """
    return datetime.today().replace(second=0, microsecond=0)


def get_genre_list(names: list) -> Union[Model, list[str]]:
    """
    Get the genres corresponding to the specified list
    """
    genres = []
    try:
        genres = genre_list(names)
    except:
        print_exc_info()
        abort(HTTPStatus.INTERNAL_SERVER_ERROR.value)

    return genres


def str_or_none(value: str):
    """
    Return trimmed non-whitespace string or None
    :param value: string to check
    :return:
    """
    result = value.strip() if value is not None else None
    return result if result is not None and len(result) > 0 else None


def check_no_list_in_list(terms: list):
    """
    Verify that the specified list does not contain any lists
    :param terms:
    :return:
    """
    if not isinstance(terms, list):
        raise ValueError("Expecting list of clauses")
    else:
        for clause in terms:
            if isinstance(clause, list):
                raise ValueError("Found list when expecting clauses")