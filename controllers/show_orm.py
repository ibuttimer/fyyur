# ---------------------------------------------------------------------------- #
# Imports
# ---------------------------------------------------------------------------- #
from datetime import date, datetime
from http import HTTPStatus
from typing import Union, Any

from flask import abort
from flask_sqlalchemy import Pagination
from flask_wtf import FlaskForm

from forms import MIDNIGHT
from misc import (print_exc_info, EntityResult, ncsg_search_clauses, entity_search_clauses,
                  OR_CONJUNC, AND_CONJUNC, SearchParams, entity_search_expression
                  )
from util import get_config
from models import SQLAlchemyDB as db, Venue, Artist, Show, Availability, get_entity, ARTIST_TABLE, VENUE_TABLE, \
    SHOWS_TABLE
from .controllers_misc import FactoryObj, FILTER_PREVIOUS, FILTER_UPCOMING

SHOWS_KEYS = ['venue_id', 'artist_id', 'start_time', 'venue_name', 'artist_name', 'artist_image_link']
# indices to extract data for db results
SHOWS_DICT = {SHOWS_KEYS[p]: p for p in range(len(SHOWS_KEYS))}

SHOWS_PER_PAGE = get_config("SHOWS_PER_PAGE")

_ARTIST_ = get_entity(ARTIST_TABLE)
_VENUE_ = get_entity(VENUE_TABLE)
_SHOWS_ = get_entity(SHOWS_TABLE)


def show_factory_orm(obj_type: FactoryObj) -> Union[Show, object, None]:
    """
    Get a show related object
    :param obj_type: object type to get
    :return:
    """
    result = None
    if obj_type == FactoryObj.OBJECT:
        result = _SHOWS_.model()
    elif obj_type == FactoryObj.CLASS:
        result = _SHOWS_.orm_model
    return result


def shows_orm(page: int, filterby: str, mode: str, form: FlaskForm, search_term: str) -> dict:
    """
    List all shows
    :param page:         requested page of search results
    :param filterby:     results filter; one of 'all', 'previous' or 'upcoming'
    :param mode:         one of 'basic', 'advanced' or 'all'
    :param form:         form data for advanced search
    :param search_term:  search_term for basic search
    """
    shows_list = []
    pagination = Pagination(None, page, SHOWS_PER_PAGE, 0, shows_list)
    # advanced search on Venue & Artist, joining class clauses with 'and' and the result of those with 'or'
    # e.g. if have 'name' do same search on Venue & Artist and 'or' their results
    search = SearchParams([_ARTIST_, _VENUE_], conjunction=[OR_CONJUNC, AND_CONJUNC]).load_form(form)
    search.simple_search_term = search_term
    try:
        shows_list = Show.query\
            .join(Venue, Show.venue_id == Venue.id) \
            .join(Artist, Show.artist_id == Artist.id) \
            .with_entities(Show.venue_id, Show.artist_id, Show.start_time,
                           Venue.name, Artist.name, Artist.image_link)
        if filterby == FILTER_PREVIOUS:
            shows_list = shows_list.filter(Show.start_time < datetime.today())
        elif filterby == FILTER_UPCOMING:
            shows_list = shows_list.filter(Show.start_time > datetime.today())

        # get search terms and clauses for both Venue & Artist
        ncsg_search_clauses(mode, search)
        if len(search.clauses) > 0:
            shows_list = entity_search_clauses(shows_list, search, entity_search_expression)

        pagination = shows_list \
            .order_by(Show.start_time) \
            .paginate(page=page, per_page=SHOWS_PER_PAGE)
        shows_list = pagination.items

    except:
        print_exc_info()
        abort(HTTPStatus.INTERNAL_SERVER_ERROR.value)

    # [{'venue_id': ?, 'artist_id' ?, ...}, {}, ...] }
    data = [{k: show[v] if k != 'start_time' else show[v].isoformat() for k, v in SHOWS_DICT.items()}
            for show in shows_list]

    return {
        "count": pagination.total,
        "data": data,
        "search_term": ', '.join(search.search_terms),
        "mode": mode,
        "pagination": pagination
    }


def extract_unique_properties_orm(show: Show) -> tuple:
    """
    Extract the properties to uniquely find a show
    :param show:   show to extract from
    :return: properties as a tuple
    """
    return show.artist_id, show.venue_id, show.start_date, show.start_time, show.end_time, EntityResult.MODEL


class AvailabilitySlot:
    """ Class representing an availability slot """

    def __init__(self, start_time=None, end_time=None, pair=None) -> None:
        if pair is not None:
            start_time = pair[0]
            end_time = pair[1]
        self.start_time = start_time
        self.end_time = end_time
        if start_time is None or end_time is None:
            self.duration = None
        else:
            if end_time == MIDNIGHT:
                self.duration = ((24 - start_time.hour) * 60) - start_time.minute
            else:
                start = datetime.combine(date.today(), start_time)
                end = datetime.combine(date.today(), end_time)
                self.duration = divmod((end - start).total_seconds(), 60)[0]


def dow_availability_orm(availability: Availability, dow: int):
    """
    Get availability for the specified day of the week
    :param availability:    availability info
    :param dow:             day of the week; 0=monday etc.
    """
    if availability is not None:
        if dow == 0:  # monday
            slot = availability.monday
        elif dow == 1:  # tuesday
            slot = availability.tuesday
        elif dow == 2:  # wednesday
            slot = availability.wednesday
        elif dow == 3:  # thursday
            slot = availability.thursday
        elif dow == 4:  # friday
            slot = availability.friday
        elif dow == 5:  # saturday
            slot = availability.saturday
        else:  # sunday
            slot = availability.sunday
    else:
        slot = (None, None)

    return AvailabilitySlot(pair=slot)


def create_show_orm(show: Show):
    """
    Create a show in ORM mode
    :param show:   show to create
    """
    try:
        db.session.add(show)
        db.session.commit()
        success = True
    except:
        db.session.rollback()
        print_exc_info()
        success = False
    finally:
        db.session.close()

    return success


def artists_and_venues_orm():
    """
    Get artists and venues for show listing
    """
    artists = []
    venues = []
    try:
        artists = Artist.query.with_entities(Artist.id, Artist.name).order_by(Artist.name).all()
        venues = Venue.query.with_entities(Venue.id, Venue.name).order_by(Venue.name).all()
    except:
        print_exc_info()

    return artists, venues
