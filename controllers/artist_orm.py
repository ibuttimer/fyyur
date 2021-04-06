# ---------------------------------------------------------------------------- #
# Imports
# ---------------------------------------------------------------------------- #
from datetime import datetime
from http import HTTPStatus
from typing import Union

from flask import abort
from flask_wtf import FlaskForm
from sqlalchemy import and_, func

from forms import (populate_genred_model, populate_model)
from models import SQLAlchemyDB as db, Artist, Show, Availability
from models import is_available
from misc.queries import shows_by_artist
from .controllers_misc import (add_show_summary, model_property_list, IGNORE_ID_GENRES,
                               IGNORE_ID, FactoryObj)
from misc import print_exc_info, EntityResult, get_music_entity_orm


def artist_factory_orm(obj_type: FactoryObj) -> Union[Artist, object, None]:
    """
    Get an artist related object
    :param obj_type: object type to get
    :return:
    """
    result = None
    if obj_type == FactoryObj.OBJECT:
        result = Artist()
    elif obj_type == FactoryObj.CLASS:
        result = Artist
    return result


def availability_factory_orm(obj_type: FactoryObj) -> Union[Artist, object, None]:
    """
    Get an availability related object
    :param obj_type: object type to get
    :return:
    """
    result = None
    if obj_type == FactoryObj.OBJECT:
        result = Availability()
    elif obj_type == FactoryObj.CLASS:
        result = Availability
    return result


def get_artist_orm(artist_id: int) -> Artist:
    """
    Get an artist
    :param artist_id:   id of artist
    """
    artist = get_music_entity_orm(artist_id, Artist)
    return add_show_summary(artist_id, artist, shows_by_artist)


def populate_artist_orm(artist: Artist, form: FlaskForm):
    """
    Populate an artist from a form
    :param artist:  artist
    :param form:    form to populate from
    """
    property_list = model_property_list(artist, IGNORE_ID_GENRES)
    return populate_genred_model(artist, form, property_list)


IGNORE_AVAILABILITY = ["id", "artist_id"]


def populate_availability_orm(availability: Availability, form: FlaskForm):
    """
    Populate an availability from a form
    """
    property_list = model_property_list(availability, IGNORE_AVAILABILITY)
    return populate_model(availability, form, property_list)


IGNORE_ID_DATE = ['id', 'from_date']


def update_artist_orm(artist_id: int, form: FlaskForm, availability: Availability) -> (bool, str):
    """
    Update an artist in ORM mode
    :param artist_id:       id of the artist to update
    :param form:            form to populate from
    :param availability:    artist availability
    """
    commit_change = False

    artist = Artist.query.filter(Artist.id == artist_id).first_or_404()
    artist_name = artist.name

    updated_artist = populate_artist_orm(Artist(), form)
    if not updated_artist.equal(artist, IGNORE_ID):
        # change has occurred update artist
        populate_artist_orm(artist, form)
        artist_name = artist.name
        commit_change = True

    new_availability = populate_availability_orm(Availability(), form)
    new_availability.artist_id = artist_id

    try:
        if is_available(availability) != is_available(new_availability) or \
                not availability.equal(new_availability, IGNORE_ID_DATE):
            # availability has changed, add new setting
            db.session.add(new_availability)
            commit_change = True

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

    return success, artist_name


def artist_to_edit_orm(artist_id: int) -> (Artist, EntityResult, Availability):
    """
    Edit an artist
    :param artist_id: id of the artist to edit
    """
    artist = get_music_entity_orm(artist_id, Artist)
    as_type = EntityResult.MODEL  # availability as model
    no_availability = Availability()
    return artist, as_type, no_availability


def delete_artist_orm(artist_id: int) -> (bool, str):
    """
    Delete an artist in ORM mode
    :param artist_id: id of the artist to delete
    """
    artist = Artist.query.filter(Artist.id == artist_id).first_or_404()
    artist_name = artist.name
    try:
        # when an artist is deleted, need to delete availability & shows as well to keep the db consistent
        availability = Availability.query.filter(Availability.artist_id == artist_id).all()
        shows = Show.query.filter(Show.artist_id == artist_id).all()

        for available in availability:
            db.session.delete(available)
        for show in shows:
            db.session.delete(show)
        db.session.delete(artist)
        db.session.commit()
        success = True
    except:
        db.session.rollback()
        print_exc_info()
        success = False
    finally:
        db.session.close()

    return success, artist_name


def extract_unique_properties_orm(artist: Artist) -> tuple:
    """
    Extract the properties to uniquely find a artist
    Note: order matches that of existing_artist_orm() arguments
    :param artist:   artist to extract from
    :return: properties as a tuple
    """
    return artist.name, artist.city, artist.state


def existing_artist_orm(name: str, city: str, state: str):
    """
    Check for existing artist
    :param name:    artist name
    :param city:    artist city
    :param state:   artist state
    :return: existing artist id and name, or None
    """
    artist_id = None
    artist_name = None
    try:
        existing = Artist.query \
            .with_entities(Artist.id, Artist.name) \
            .filter(and_(func.lower(Artist.name) == func.lower(name),
                         func.lower(Artist.city) == func.lower(city),
                         func.upper(Artist.state) == func.upper(state))) \
            .first()
        if existing is not None:
            artist_id = existing.id
            artist_name = existing.name

    except:
        print_exc_info()

    return artist_id, artist_name


def create_artist_orm(artist: Artist, availability: Availability) -> (bool, str):
    """
    Create an artist in ORM mode
    :param artist:          artist to create
    :param availability:    artist availability
    """
    artist_name = artist.name
    try:
        db.session.add(artist)
        db.session.commit()

        if availability.is_available():
            availability.artist_id = artist.id
            db.session.add(availability)
            db.session.commit()

        success = True
    except:
        db.session.rollback()
        print_exc_info()
        success = False
    finally:
        db.session.close()

    return success, artist_name


def availability_by_artist_orm(artist_id: int,
                               from_date: datetime, as_type=EntityResult.DICT) -> Union[dict, Availability, None]:
    """
    Search for an artist's latest availability
    :param artist_id:  id of artist
    :param from_date:  filtering criterion
    :param as_type:    result
    """
    availability = None
    try:
        availability = Availability.query.join(Artist, Availability.artist_id == Artist.id) \
            .filter(and_(Availability.artist_id == artist_id), Availability.from_date < from_date) \
            .order_by(Availability.from_date.desc(), Availability.id.desc()) \
            .first()
        if availability is not None and as_type != EntityResult.MODEL:
            availability = availability.get_dict()

    except:
        print_exc_info()
        abort(HTTPStatus.INTERNAL_SERVER_ERROR.value)

    return availability


