# ---------------------------------------------------------------------------- #
# Imports
# ---------------------------------------------------------------------------- #
from datetime import datetime
from typing import Union

from flask import render_template, request, flash, url_for, jsonify, Markup
from flask_sqlalchemy.model import Model
from werkzeug.datastructures import MultiDict

from forms import (ArtistForm, NCSSearchForm)
from misc import current_datetime, EntityResult
from models import is_available_time_key, model_items
from misc.queries import artists_search, SEARCH_ALL, SEARCH_BASIC, SEARCH_ADVANCED
from .artist_orm import IGNORE_AVAILABILITY
from .artist_engine import datetime_to_str, time_to_str
from .controllers_misc import (set_genre_field_options, update_result,
                               delete_result, create_result, exists_or_404, get_availability_date, FactoryObj)

from config import USE_ORM

ORM = USE_ORM
ENGINE = not ORM

if ORM:
    from .artist_orm import (
        artist_factory_orm as artist_factory,
        availability_factory_orm as availability_factory,
        availability_by_artist_orm as availability_by_artist_impl,
        get_artist_orm as get_artist,
        populate_artist_orm as populate_artist,
        populate_availability_orm as populate_availability,
        update_artist_orm as update_artist,
        artist_to_edit_orm as artist_to_edit,
        delete_artist_orm as delete_artist_impl,
        extract_unique_properties_orm as extract_unique_properties,
        existing_artist_orm as existing_artist,
        create_artist_orm as create_artist_impl,
    )
else:
    from .artist_engine import (
        artist_factory_engine as artist_factory,
        availability_factory_engine as availability_factory,
        availability_by_artist_engine as availability_by_artist_impl,
        get_artist_engine as get_artist,
        populate_artist_engine as populate_artist,
        populate_availability_engine as populate_availability,
        update_artist_engine as update_artist,
        artist_to_edit_engine as artist_to_edit,
        delete_artist_engine as delete_artist_impl,
        extract_unique_properties_engine as extract_unique_properties,
        existing_artist_engine as existing_artist,
        create_artist_engine as create_artist_impl,
    )


def artists():
    """
    List all artists
    """
    form = NCSSearchForm()

    return render_artists('Fyyur | Artists', form, artists_search(SEARCH_ALL, form))


def render_artists(title: str, form: NCSSearchForm, results):
    """
    Render the artists page
    :param title:   Page title
    :param form:    search form
    :param results: search results
    :return:
    """
    return render_template('pages/artists.html',
                           results=results,
                           title=title,
                           endpoint='search_artists_advanced',
                           advanced_url='/artists/advanced_search',
                           form=form)


def search_artists():
    """
    Perform search on artists.

    Request query parameters:
    mode:   search query mode; one of 'basic', 'advanced' or 'all'
    """
    mode = request.args.get('mode', default=SEARCH_BASIC)

    form = NCSSearchForm()

    return render_artists('Fyyur | Artists Search', form, artists_search(mode, form))


def search_artists_advanced():
    """
    Perform advanced search on artists
    """
    form = NCSSearchForm()

    if request.method == 'POST':
        results = artists_search(SEARCH_ADVANCED, form)
    else:
        results = {
            "count": 0,
            "data": [],
            "search_term": "",
            "mode": 'none'
        }

    return render_artists('Fyyur | Artists Search', form, results)


def availability_by_artist(artist_id: int, from_date=None, as_type=EntityResult.DICT) -> Union[dict, Model, None]:
    """
    Search for an artist's latest availability
    :param artist_id:  id of artist
    :param from_date:  filtering criterion
    :param as_type:    result
    """
    if from_date is None:
        from_date = datetime.today()

    return availability_by_artist_impl(artist_id, from_date, as_type=as_type)


def show_artist(artist_id: int):
    """
    Show the artist page with the given artist_id
    :param artist_id:   id of artist
    """
    artist = get_artist(artist_id)
    availability = availability_by_artist(artist_id)
    if availability is not None:
        count = 0
        for key in availability.keys():
            if (is_available_time_key(key)) and availability[key] is not None:
                availability[key] = availability[key].isoformat(timespec='minutes')
                count = count + 1
        if count == 0:
            availability = None
    else:
        availability = None
    artist["availability"] = availability

    return render_template('pages/show_artist.html', artist=artist)


def edit_artist(artist_id: int):
    """
    Edit an artist
    :param artist_id: id of the artist to edit
    """
    artist, as_type, no_availability = artist_to_edit(artist_id)
    model = MultiDict(artist)

    availability = availability_by_artist(artist_id, as_type=as_type)
    if availability is None:
        availability = no_availability

    if request.method == 'GET':
        for key, value in model_items(availability, ignore=IGNORE_AVAILABILITY):
            if key == 'from_date':
                model.add(key, datetime_to_str(current_datetime()))
            elif is_available_time_key(key) and value is not None:
                model.add(key, time_to_str(value))

        form = ArtistForm(formdata=model)
        genres = model.getlist("genres")

    else:
        form = ArtistForm()
        genres = form.genres.data

    # set choices & validators based on possible options
    set_genre_field_options(form.genres, genres)

    if request.method == 'POST' and form.validate_on_submit():
        success, artist_name = update_artist(artist["id"], form, availability)

        return update_result(success, artist_name, 'Artist', url_for('show_artist', artist_id=artist_id))

    return render_template('forms/edit_artist.html',
                           form=form,
                           artist_name=model["name"],
                           title='Edit Artist',
                           submit_action=url_for('edit_artist', artist_id=artist_id),
                           cancel_url=url_for('show_artist', artist_id=artist_id),
                           submit_text='Update',
                           submit_title='Update artist'
                           )


def delete_artist(artist_id: int):
    """
    Delete an artist
    :param artist_id: id of the artist to delete
    """
    success, artist_name = delete_artist_impl(artist_id)

    return delete_result(success, artist_name, 'Artist')


def create_artist_submission():
    """
    Create an artist
    """
    form = ArtistForm()
    if request.method == 'POST':
        genres = form.genres.data
    else:
        genres = list()

    # set choices & validators based on possible options
    set_genre_field_options(form.genres, genres)

    if request.method == 'POST' and form.validate_on_submit():

        artist = populate_artist(
            artist_factory(FactoryObj.OBJECT), form)
        availability = populate_availability(
            availability_factory(FactoryObj.OBJECT), form)

        # check for existing artist
        artist_id, artist_name = existing_artist(*extract_unique_properties(artist))

        if artist_id is not None:
            url = url_for('show_artist', artist_id=artist_id)
            flash(Markup(f'A listing for {artist_name} already exists! '
                         f'Please see <a href="{url}">{artist_name}</a>.'))
        else:
            # add artist
            success, artist_name = create_artist_impl(artist, availability)

            return create_result(success, artist_name, 'Artist')

    return render_template('forms/edit_artist.html',
                           form=form,
                           title='Create Artist',
                           submit_action=url_for('create_artist_submission'),
                           cancel_url=url_for('index'),
                           submit_text='Create',
                           submit_title='Create artist'
                           )


def artist_availability(artist_id: int):
    """
    Get an artist's availability
    :param artist_id: id of the artist

    Request query parameters:
    query_date:   search query date in form 'YYYY-MM-DD HH:MM)'
    """
    # artist exists check
    exists_or_404(artist_factory(FactoryObj.CLASS), artist_id)

    query_date = get_availability_date(
        request.args.get('query_date', default=None))

    availability = availability_by_artist(artist_id, query_date)

    available_times = []
    if availability is not None:
        for from_time, to_time, day in [
            (availability["mon_from"], availability["mon_to"], 'Monday'),
            (availability["tue_from"], availability["tue_to"], 'Tuesday'),
            (availability["wed_from"], availability["wed_to"], 'Wednesday'),
            (availability["thu_from"], availability["thu_to"], 'Thursday'),
            (availability["fri_from"], availability["fri_to"], 'Friday'),
            (availability["sat_from"], availability["sat_to"], 'Saturday'),
            (availability["sun_from"], availability["sun_to"], 'Sunday')
        ]:
            if from_time is not None and to_time is not None:
                available_times.append(f'{day} '
                                       f'{time_to_str(from_time)}-{time_to_str(to_time)}')

    return jsonify({
        'availability': available_times
    })
