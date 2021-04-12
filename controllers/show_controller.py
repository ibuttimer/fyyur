# ---------------------------------------------------------------------------- #
# Imports
# ---------------------------------------------------------------------------- #
from datetime import time, timedelta, datetime
from http import HTTPStatus
from typing import Union

from flask import render_template, flash, redirect, url_for, request, abort
from flask.helpers import make_response
from flask_sqlalchemy import Model
from flask_wtf import FlaskForm

from forms import (populate_model, populate_model_property, set_singleselect_field_options, ShowForm,
                   AVAILABILITY_TIME_FMT, MIDNIGHT)
from forms.forms import OTHER_DURATION, NCSSearchForm
from misc import label_from_valuelabel_list, SEARCH_BASIC, SEARCH_ALL, SEARCH_ADVANCED
from util import current_datetime
from .artist_controller import availability_by_artist
from .controllers_misc import (model_property_list, IGNORE_ID_GENRES, FactoryObj, FILTER_ALL, FILTER_PREVIOUS,
                               FILTER_UPCOMING, set_genre_field_options
                               )
from .venue_controller import bookings_by_venue
from config import USE_ORM
from .venue_engine import str_to_datetime

ORM = USE_ORM
ENGINE = not ORM


if ORM:
    from .show_orm import (
        show_factory_orm as show_factory,
        shows_orm as shows_impl,
        extract_unique_properties_orm as extract_unique_properties,
        dow_availability_orm as dow_availability,
        create_show_orm as create_show_impl,
        artists_and_venues_orm as artists_and_venues,
    )
else:
    from .show_engine import (
        show_factory_engine as show_factory,
        shows_engine as shows_impl,
        extract_unique_properties_engine as extract_unique_properties,
        dow_availability_engine as dow_availability,
        create_show_engine as create_show_impl,
        artists_and_venues_engine as artists_and_venues,
    )


def get_request_page() -> int:
    page = request.args.get('page', 1, type=int)
    if page < 1:
        abort(HTTPStatus.BAD_REQUEST.value)
    return page


def get_request_filterby() -> str:
    filterby = request.args.get('filterby', FILTER_ALL)
    if filterby not in [FILTER_ALL, FILTER_PREVIOUS, FILTER_UPCOMING]:
        abort(HTTPStatus.BAD_REQUEST.value)
    return filterby


def shows():
    """
    List all shows

    Request query parameters:
    page:     requested page of search results
    filterby: results filter; one of 'all', 'previous' or 'upcoming'
    """
    page = get_request_page()
    filterby = get_request_filterby()

    form = NCSSearchForm()
    mode = SEARCH_ALL

    results = shows_impl(page, filterby, mode, form, None)
    results["pagination_url"] = 'shows'

    return render_shows("Fyyur | Shows", form, results)


def render_shows(title: str, form: NCSSearchForm, results):
    """
    Render the artists page
    :param title:   Page title
    :param form:    search form
    :param results: search results
    :return:
    """
    return render_template('pages/shows.html',
                           results=results,
                           title=title,
                           endpoint='search_shows_advanced',
                           advanced_url='/shows/advanced_search',
                           form=form)


def search_shows():
    """
    Perform search on artists.

    Request query parameters:
    mode:   search query mode; one of 'basic', 'advanced' or 'all'
    """
    mode = request.args.get('mode', default=SEARCH_BASIC)
    page = get_request_page()

    form = NCSSearchForm()

    results = shows_impl(page, FILTER_ALL, mode, form, request.form.get('search_term', ''))
    results["pagination_url"] = 'search_shows'

    return render_shows('Fyyur | Shows Search', form, results)


def search_shows_advanced():
    """
    Perform advanced search on shows
    """
    is_post = (request.method == 'POST')
    page = get_request_page()

    form = NCSSearchForm()

    genres = form.genres.data if is_post else list()

    # set choices & validators based on possible options
    set_genre_field_options(form.genres, genres, required=False)

    if is_post:
        results = shows_impl(page, FILTER_ALL, SEARCH_ADVANCED, form, request.form.get('search_term', ''))
    else:
        pagination = request.args.get('pagination', 'n')
        if pagination == 'y':
            results = shows_impl(page, FILTER_ALL, SEARCH_ADVANCED, form, request.form.get('search_term', ''))
        else:
            results = {
                "count": 0,
                "data": [],
                "search_term": "",
                "mode": 'none',
                "pagination": None
            }
    results["pagination_url"] = 'search_shows_advanced'

    return render_shows('Fyyur | Shows Search', form, results)


def populate_show(show: Union[Model, dict], form: FlaskForm):
    """
    Populate a show from a form
    :param show:    show
    :param form:    form to populate from
    """
    property_list = model_property_list(show, IGNORE_ID_GENRES+["duration"])
    populate_model(show, form, property_list)
    duration = form.duration.data
    if form.duration.data == OTHER_DURATION:
        duration = form.other_duration.data.hour * 60 + form.other_duration.data.minute
    populate_model_property(show, "duration", duration)
    return show


class Booking:
    """ Class representing a booking """

    def __init__(self, name, start_time, duration) -> None:
        self.name = name
        self.start_time = start_time
        self.duration = duration
        self.end_time = start_time + timedelta(minutes=duration)


def verify_show(show: Union[Model, dict]):
    """
    Verify that a show can be scheduled without conflict
    :param show:    show to verify
    """
    artist_id, venue_id, start_date, start_time, end_time, as_type = extract_unique_properties(show)

    booking_conflict = None
    bookings = bookings_by_venue(venue_id, start_date)
    if bookings is not None:
        bookings_list = [Booking(b["name"], b["start_time"], b["duration"]) for b in bookings]
        for booking in bookings_list:
            if booking.start_time <= start_time < booking.end_time:
                booking_conflict = booking
            elif booking.start_time < end_time <= booking.end_time:
                booking_conflict = booking

            if booking_conflict is not None:
                break

    availability = availability_by_artist(artist_id, start_time, as_type=as_type)
    dow = start_time.weekday()
    slot = dow_availability(availability, dow)

    artist_conflict = None  # availability & show mismatch
    availability = slot.duration is not None  # no availability
    if availability:
        start = datetime.combine(start_time.date(), slot.start_time)
        if slot.end_time == MIDNIGHT:
            end = datetime.combine((start_time + timedelta(days=1)).date(), time(hour=0, minute=0))
        else:
            end = datetime.combine(start_time.date(), slot.end_time)
        if start_time < start:
            artist_conflict = slot
        if end_time > end:
            artist_conflict = slot

    return {
        'ok': booking_conflict is None and artist_conflict is None and availability,
        'show': booking_conflict,
        'artist': artist_conflict,
        'availability': availability
    }


NO_SELECTION = -1


def create_show():
    """
    List a show

    Request query parameters:
    artist: id of artist selected for show
    venue:  id of venue selected for show
    A GET returns an empty form
    A POST submits the info
    """
    is_post = (request.method == 'POST')
    artist_id = int(request.args.get('artist', str(NO_SELECTION)))
    venue_id = int(request.args.get('venue', str(NO_SELECTION)))

    artists, venues = artists_and_venues()

    artist_choices = [(a[0], a[1]) for a in artists]
    artist_choices.insert(0, (NO_SELECTION, "Select artist"))
    venue_choices = [(v[0], v[1]) for v in venues]
    venue_choices.insert(0, (NO_SELECTION, "Select venue"))

    form = ShowForm()
    if is_post:
        artists = form.artist_id.data
        venues = form.venue_id.data
        start_time = form.start_time.data
    else:
        artists = list()
        venues = list()
        start_time = request.args.get('starttime', None)
        start_time = current_datetime() if start_time is None else str_to_datetime(start_time)

    # set choices & validators based on possible options
    set_singleselect_field_options(form.artist_id, artist_choices,
                                   [a[0] for a in artist_choices if a[0] != NO_SELECTION], artists)
    set_singleselect_field_options(form.venue_id, venue_choices, [v[0] for v in venue_choices if v[0] != NO_SELECTION],
                                   venues)
    if artist_id != NO_SELECTION:
        form.artist_id.data = artist_id
    if venue_id != NO_SELECTION:
        form.venue_id.data = venue_id
    if start_time is not None:
        form.start_time.data = start_time

    response = None
    status_code = HTTPStatus.OK.value  # status code for GET
    if request.method == 'POST':
        status_code = HTTPStatus.ACCEPTED.value  # status code for errors in form or conflict

        if form.validate_on_submit():
            show = populate_show(
                show_factory(FactoryObj.OBJECT), form)

            verification = verify_show(show)

            artist = label_from_valuelabel_list(artist_choices, form.artist_id.data)
            venue = label_from_valuelabel_list(venue_choices, form.venue_id.data)

            if not verification["ok"]:
                def time_disp(dt): return dt.strftime(AVAILABILITY_TIME_FMT)

                if verification["show"] is not None:
                    err = verification["show"]
                    flash(f'Booking conflict. A show by {err.name} is booked from '
                          f'{time_disp(err.start_time)} to {time_disp(err.end_time)}.')
                if verification["artist"] is not None:
                    err = verification["artist"]
                    flash(f'Artist availability conflict. Artist is only available from '
                          f'{time_disp(err.start_time)} to {time_disp(err.end_time)}.')
                if not verification["availability"]:
                    flash(f'Artist availability conflict. Artist is not available.')

            else:
                success = create_show_impl(show)

                if success:
                    # on successful db insert, flash success
                    flash(f'{artist} show at {venue} successfully listed!')
                else:
                    flash(f'An error occurred. {artist} show at {venue} could not be listed.')

                response = make_response(redirect(url_for('index')))
                status_code = response.status_code

    if response is None:
        response = make_response(
            render_template('forms/edit_show.html',
                            form=form,
                            title='Create Show',
                            submit_action=url_for('create_show'),
                            cancel_url=url_for('index'),
                            submit_text='Create',
                            submit_title='Create show'
                            )
        )

    response.status_code = status_code
    return response
