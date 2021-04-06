# ---------------------------------------------------------------------------- #
# Imports
# ---------------------------------------------------------------------------- #
from datetime import datetime
from http import HTTPStatus
from typing import Union

from flask import abort
from flask_wtf import FlaskForm
from sqlalchemy import func, and_, cast, Date

from .controllers_misc import (add_show_summary, model_property_list, IGNORE_ID_GENRES,
                               IGNORE_ID, FactoryObj
                               )
from misc import get_music_entity_orm
from forms import (populate_genred_model)
from misc import EntityResult, print_exc_info
from misc.queries import entity_shows_count, shows_by_venue
from models import SQLAlchemyDB as db, Venue, Artist, Show

BOOKING_BY_VENUE_KEYS = ['start_time', 'duration', 'name']
# indices to extract data for db results
BOOKING_BY_VENUE_DICT = {BOOKING_BY_VENUE_KEYS[p]: p for p in range(len(BOOKING_BY_VENUE_KEYS))}


def venue_factory_orm(obj_type: FactoryObj) -> Union[Venue, object, None]:
    """
    Get a venue related object
    :param obj_type: object type to get
    :return:
    """
    result = None
    if obj_type == FactoryObj.OBJECT:
        result = Venue()
    elif obj_type == FactoryObj.CLASS:
        result = Venue
    return result


def venues_orm() -> list:
    """
    List all venues
    """
    venues = []
    try:
        cities_states = Venue.query.with_entities(Venue.state, Venue.city).distinct().all()
        for city_state in cities_states:
            venue_list = Venue.query.with_entities(Venue.id, Venue.name) \
                .filter(and_(Venue.state == city_state.state, Venue.city == city_state.city)) \
                .all()

            venues.append({
                "state": city_state[0],
                "city": city_state[1],
                "venues": entity_shows_count(venue_list, Show.venue_id)
            })
    except:
        print_exc_info()
        abort(HTTPStatus.INTERNAL_SERVER_ERROR.value)

    return venues


def get_venue_orm(venue_id: int) -> Venue:
    """
    Get a venue
    :param venue_id:   id of venue
    """
    venue = get_music_entity_orm(venue_id, Venue)
    return add_show_summary(venue_id, venue, shows_by_venue)


def populate_venue_orm(venue: Venue, form: FlaskForm):
    """
    Populate a venue from a form
    :param venue:   venue
    :param form:    form to populate from
    """
    property_list = model_property_list(venue, IGNORE_ID_GENRES)
    return populate_genred_model(venue, form, property_list)


def update_venue_orm(venue_id: int, form: FlaskForm) -> (bool, str):
    """
    Update a venue in ORM mode
    :param venue_id: id of the venue to update
    :param form:     form to populate from
    """
    commit_change = False

    venue = Venue.query.filter(Venue.id == venue_id).first_or_404()
    venue_name = venue.name

    updated_venue = populate_venue_orm(Venue(), form)
    if not updated_venue.equal(venue, IGNORE_ID):
        # change has occurred update venue
        populate_venue_orm(venue, form)
        commit_change = True

    try:
        if commit_change:
            db.session.commit()
            success = True
        else:
            success = None
    except:
        db.session.rollback()
        print_exc_info()
        success = False
    finally:
        db.session.close()

    return success, venue_name


def venue_to_edit_orm(venue_id: int) -> (Venue, EntityResult):
    """
    Edit an venue
    :param venue_id: id of the venue to edit
    """
    venue = get_music_entity_orm(venue_id, Venue)
    as_type = EntityResult.MODEL  # availability as a model
    return venue, as_type


def delete_venue_orm(venue_id: int):
    """
    Delete an venue in ORM mode
    :param venue_id: id of the venue to delete
    """
    venue = Venue.query.filter(Venue.id == venue_id).first_or_404()
    venue_name = venue.name
    try:
        # when an venue is deleted, need to delete shows as well to keep the db consistent
        shows = Show.query.filter(Show.venue_id == venue_id).all()

        for show in shows:
            db.session.delete(show)
        db.session.delete(venue)
        db.session.commit()
        success = True
    except:
        db.session.rollback()
        print_exc_info()
        success = False
    finally:
        db.session.close()

    return success, venue_name


def extract_unique_properties_orm(venue: Venue) -> tuple:
    """
    Extract the properties to uniquely find a venue
    Note: order matches that of existing_venue_orm() arguments
    :param venue:   venue to extract from
    :return: properties as a tuple
    """
    return venue.name, venue.address, venue.city, venue.state


def existing_venue_orm(name: str, address: str, city: str, state: str):
    """
    Check for existing venue
    :param name:    artist name
    :param address: artist address
    :param city:    artist city
    :param state:   artist state
    :return: existing venue id and name, or None
    """
    venue_id = None
    venue_name = None
    try:
        existing = Venue.query \
            .with_entities(Venue.id, Venue.name) \
            .filter(and_(func.lower(Venue.name) == func.lower(name),
                         func.lower(Venue.city) == func.lower(city),
                         func.lower(Venue.address) == func.lower(address),
                         func.upper(Venue.state) == func.upper(state))) \
            .first()
        if existing is not None:
            venue_id = existing.id
            venue_name = existing.name

    except:
        print_exc_info()

    return venue_id, venue_name


def create_venue_orm(venue: Venue):
    """
    Create an venue in ORM mode
    :param venue:  venue to create
    """
    venue_name = venue.name
    try:
        db.session.add(venue)
        db.session.commit()
        success = True
    except:
        db.session.rollback()
        print_exc_info()
        success = False
    finally:
        db.session.close()

    return success, venue_name


def bookings_by_venue_orm(venue_id: int, query_date: datetime) -> list:
    """
    Search for a venue's bookings
    :param venue_id:   id of venue
    :param query_date: date filtering criterion
    """
    bookings = []
    try:
        query = Show.query.join(Venue, Show.venue_id == Venue.id) \
            .join(Artist, Show.artist_id == Artist.id) \
            .with_entities(Show.start_time, Show.duration, Artist.name)
        if query_date is not None:
            query = query.filter(
                and_(Show.venue_id == venue_id, Show.start_date == cast(query_date, Date)))
        else:
            query = query.filter(Show.venue_id == venue_id) \
                .order_by(Show.start_date)
        bookings = query.all()

    except:
        print_exc_info()
        abort(HTTPStatus.INTERNAL_SERVER_ERROR.value)

    # [{'start_time': ?, 'duration' ?, ...}, {}, ...] }
    return [{k: show[BOOKING_BY_VENUE_DICT[k]] for k, v in BOOKING_BY_VENUE_DICT.items()} for show in bookings]
