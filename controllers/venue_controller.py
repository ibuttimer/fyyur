# ---------------------------------------------------------------------------- #
# Imports
# ---------------------------------------------------------------------------- #
from datetime import timedelta, datetime

from flask import render_template, jsonify, Markup, request, url_for, flash
from werkzeug.datastructures import MultiDict

from controllers.controllers_misc import (set_genre_field_options, update_result,
                                          delete_result, create_result, get_availability_date, exists_or_404,
                                          FactoryObj)
from forms import (VenueForm, NCSSearchForm, BookArtistForm)
from misc.queries import SEARCH_BASIC, venues_search, SEARCH_ADVANCED, artists_search
from util import current_datetime
from .venue_engine import time_to_str, datetime_to_str
from config import USE_ORM

ORM = USE_ORM
ENGINE = not ORM

if ORM:
    from .venue_orm import (
        venue_factory_orm as venue_factory,
        venues_orm as venues_impl,
        bookings_by_venue_orm as bookings_by_venue_impl,
        get_venue_orm as get_venue,
        populate_venue_orm as populate_venue,
        update_venue_orm as update_venue,
        venue_to_edit_orm as venue_to_edit,
        delete_venue_orm as delete_venue_impl,
        extract_unique_properties_orm as extract_unique_properties,
        existing_venue_orm as existing_venue,
        create_venue_orm as create_venue_impl,
    )
else:
    from .venue_engine import (
        venue_factory_engine as venue_factory,
        venues_engine as venues_impl,
        bookings_by_venue_engine as bookings_by_venue_impl,
        get_venue_engine as get_venue,
        populate_venue_engine as populate_venue,
        update_venue_engine as update_venue,
        venue_to_edit_engine as venue_to_edit,
        delete_venue_engine as delete_venue_impl,
        extract_unique_properties_engine as extract_unique_properties,
        existing_venue_engine as existing_venue,
        create_venue_engine as create_venue_impl,
    )


def venues():
    """
    List all venues
    """
    results = {
        "count": 0,
        "data": [],
        "areas": venues_impl(),
        "search_term": "",
        "mode": 'city_state'
    }
    return render_venues('Fyyur | Venues', NCSSearchForm(), results)


def render_venues(title: str, form: NCSSearchForm, results):
    """
    Render the venues page
    :param title:   Page title
    :param form:    search form
    :param results: search results
    :return:
    """
    return render_template('pages/venues.html',
                           results=results,
                           title=title,
                           endpoint='search_venues_advanced',
                           advanced_url='/venues/advanced_search',
                           form=form)


def search_venues():
    """
    Perform search on venues.

    Request query parameters:
    mode:   search query mode; one of 'basic', 'advanced' or 'all'
    """
    mode = request.args.get('mode', default=SEARCH_BASIC)

    form = NCSSearchForm()

    return render_venues('Fyyur | Venues Search', form,
                         venues_search(mode, form, simple_search_term=request.form.get('search_term', '')))


def search_venues_advanced():
    """
    Perform advanced search on venues
    """
    is_post = (request.method == 'POST')

    form = NCSSearchForm()

    genres = form.genres.data if is_post else list()

    # set choices & validators based on possible options
    set_genre_field_options(form.genres, genres, required=False)

    if is_post:
        results = venues_search(SEARCH_ADVANCED, form)
    else:
        results = {
            "count": 0,
            "data": [],
            "search_term": "",
            "mode": 'none'
        }

    return render_venues('Fyyur | Venues Search', form, results)


def render_venue(venue, form: BookArtistForm, results=None):
    """
    Render the venue page
    :param venue:   venue to display
    :param form:    search form
    :param results: search results
    :return:
    """
    return render_template('pages/display_venue.html',
                           venue=venue,
                           form=form,
                           results=results,
                           starttime=datetime_to_str(current_datetime()))


def __display_venue(venue_id: int, form: BookArtistForm, results=None):
    """
    Show the venue page with the given venue_id
    :param venue_id:   id of venue
    :param form:    search form
    :param results: search results
    """
    venue = get_venue(venue_id)

    # set choices & validators based on possible options
    set_genre_field_options(form.genres, list(), required=False)

    return render_venue(venue=venue, form=form, results=results)


def display_venue(venue_id: int):
    """
    Show the venue page with the given venue_id
    :param venue_id:   id of venue
    """
    return __display_venue(venue_id, BookArtistForm())


def venue_search_performer(venue_id: int):
    """
    Perform an artist search for a venue
    POST: perform search
    """
    form = BookArtistForm()

    results = artists_search(SEARCH_ADVANCED, form)

    return __display_venue(venue_id, form, results=results)


def edit_venue(venue_id: int):
    """
    Edit a venue
    :param venue_id: id of the venue to edit
    """
    venue, as_type = venue_to_edit(venue_id)
    model = MultiDict(venue)

    if request.method == 'GET':
        form = VenueForm(formdata=model)
        genres = model.getlist("genres")

    else:
        form = VenueForm()
        genres = form.genres.data

    # set choices & validators based on possible options
    set_genre_field_options(form.genres, genres)

    if request.method == 'POST' and form.validate_on_submit():

        success, venue_name = update_venue(venue["id"], form)

        return update_result(success, venue_name, 'Venue', url_for('display_venue', venue_id=venue_id))

    return render_template('forms/edit_venue.html',
                           form=form,
                           venue_name=model["name"],
                           title='Edit Venue',
                           submit_action=url_for('edit_venue', venue_id=venue_id),
                           cancel_url=url_for('display_venue', venue_id=venue_id),
                           submit_text='Update',
                           submit_title='Update venue'
                           )


def delete_venue(venue_id: int):
    """
    Delete a venue
    :param venue_id: id of the venue to delete
    """
    success, venue_name = delete_venue_impl(venue_id)

    return delete_result(success, venue_name, 'Venue')


def create_venue():
    """
    Create a venue
    """
    is_post = (request.method == 'POST')
    form = VenueForm()
    if is_post:
        genres = form.genres.data
    else:
        genres = list()

    # set choices & validators based on possible options
    set_genre_field_options(form.genres, genres)

    if is_post and form.validate_on_submit():

        venue = populate_venue(
            venue_factory(FactoryObj.OBJECT), form)

        # check for existing venue
        venue_id, venue_name = existing_venue(*extract_unique_properties(venue))

        if venue_id is not None:
            url = url_for('display_venue', venue_id=venue_id)
            flash(Markup(f'A listing for {venue_name} already exists! '
                         f'Please see <a href="{url}">{venue_name}</a>.'))
        else:
            # add venue
            success, venue_name = create_venue_impl(venue)

            return create_result(success, venue_name, 'Venue')

    return render_template('forms/edit_venue.html',
                           form=form,
                           title='Create Venue',
                           submit_action=url_for('create_venue'),
                           cancel_url=url_for('index'),
                           submit_text='Create',
                           submit_title='Create venue'
                           )


def bookings_by_venue(venue_id: int, query_date: datetime) -> list:
    """
    Search for a venue's bookings
    :param venue_id:   id of venue
    :param query_date: date filtering criterion
    """
    # [{'start_time': ?, 'duration' ?, ...}, {}, ...] }
    return bookings_by_venue_impl(venue_id, query_date)


def venue_bookings(venue_id: int):
    """
    Get a venue's bookings
    :param venue_id: id of the venue

    Request query parameters:
    query_date:   search query date in form 'YYYY-MM-DD HH:MM)'
    """
    # venue exists check
    query_date = get_availability_date(
        request.args.get('query_date', default=None))

    exists_or_404(venue_factory(FactoryObj.CLASS), venue_id)

    bookings = bookings_by_venue(venue_id, query_date)

    bookings_list = []
    if bookings is not None:
        bookings_list = [f'{b["name"]} {time_to_str(b["start_time"])}-'
                         f'{time_to_str(b["start_time"] + timedelta(minutes=b["duration"]))}' for b in bookings]

    return jsonify({
        'bookings': bookings_list
    })
