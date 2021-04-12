import traceback
from enum import Enum
from typing import Union, NewType, List

from flask_wtf import FlaskForm

from forms import load_form
from models import Entity


class EntityResult(Enum):
    DICT = 1
    MULTIDICT = 2
    MODEL = 3


def print_exc_info():
    """ Print exception info """
    for line in traceback.format_exc().splitlines():
        print(line)


SP_NAME = "name"
SP_CITY = "city"
SP_STATE = "state"
SP_GENRES = "genres"

ListOfOrEntity = NewType('ListOfOrEntity', Union[Entity, List[Entity]])


class SearchParams:
    """
    Class representing a search and its generated clauses
    :param entities:        class or classes to perform search for
    :param conjunction:     conjugation(s) to join clauses
    :param name:            name/partial name
    :param city:            city/city name
    :param state:           state
    :param genres:          list of genres
    :param simple_search_term:  search term for basic search
    :param genre_aliases:   list of aliases for genre table
    """
    def __init__(self, entities: ListOfOrEntity, conjunction: Union[str, list] = None,
                 name: str = None, city: str = None, state: str = None, genres: list = None,
                 simple_search_term: str = None,
                 genre_aliases: list = None):
        if not isinstance(entities, list):
            self.entities = [entities]
        else:
            self.entities = entities
        self.simple_search_term = simple_search_term
        self.name = name
        self.city = city
        self.state = state
        self.genres = genres if genres is not None else []
        self.conjunction = conjunction
        self.search_terms = []
        self.clauses = []
        self.searching_on = {SP_NAME: False, SP_CITY: False, SP_STATE: False, SP_GENRES: False}

        # following are specific to engine mode
        # customisation of 'from' in basic query, used in engine mode
        self.customisation = None
        # alias name for genre table
        self.genre_aliases = genre_aliases if genre_aliases is not None else []

    def load_form(self, form: FlaskForm):
        data = load_form(form)
        self.name = data["name"]
        self.city = data["city"]
        self.state = data["state"]
        self.genres = data["genres"]
        return self


