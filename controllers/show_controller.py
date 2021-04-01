#----------------------------------------------------------------------------#
# Imports
#----------------------------------------------------------------------------#
from datetime import date, time, timedelta
from http import HTTPStatus

from flask.helpers import make_response
from werkzeug.datastructures import Range
from forms.forms import AVAILABILITY_TIME_FMT, MIDNIGHT
from flask import render_template, request, Response, flash, redirect, url_for
from sqlalchemy import and_, inspect

from queries import *
from misc import label_from_valuelabel_list, get_config, print_exc_info
from forms import populate_model, set_singleselect_field_options, ShowForm
from .venue_controller import bookings_by_venue, datetime_to_str
from .artist_controller import availability_by_artist
from .controllers_misc import EntityResult, IGNORE_ID, create_result, model_property_list


_SHOWS_KEYS = ['venue_id', 'artist_id', 'start_time', 'venue_name', 'artist_name', 'artist_image_link']

if get_config("USE_ORM"):
  from sqlalchemy import and_
  from flask_sqlalchemy import Model
  from models import SQLAlchemyDB as db, Venue, Artist, Show
  ORM = True

  # keys to extract data for db results
  SHOWS_KEYS = {_SHOWS_KEYS[p]: p for p in range(len(_SHOWS_KEYS))}

else:
  from engine import execute, execute_transaction
  from models import (ARTIST_TABLE, VENUE_TABLE, SHOWS_TABLE, AVAILABILITY_TABLE,
                      is_available_time_key, is_available, equal_dict, dict_disjoint, new_model_dict)
  from flask_sqlalchemy import Pagination
  ORM = False

  # keys to extract data for db results
  SHOWS_KEYS = {p: p for p in _SHOWS_KEYS}

ENGINE = not ORM
SHOWS_PER_PAGE = get_config("SHOWS_PER_PAGE")


FILTER_ALL = 'all'
FILTER_PREVIOUS = 'previous'
FILTER_UPCOMING = 'upcoming'

def shows():
  # displays list of shows at /shows
  # TODO: replace with real venues data.
  #       num_shows should be aggregated based on number of upcoming shows per venue.

  '''
  List all shows

  Request query parameters:
  page:     requested page of search results
  filterby: results filter; one of 'all', 'previous' or 'upcoming'
  '''
  page = request.args.get('page', 1, type=int)
  if page < 1:
    abort(HTTPStatus.BAD_REQUEST.value)

  filterby = request.args.get('filterby', FILTER_ALL)
  if filterby not in [FILTER_ALL, FILTER_PREVIOUS, FILTER_UPCOMING]:
    abort(HTTPStatus.BAD_REQUEST.value)
  
  try:
    if ORM:
      shows = Show.query.join(Venue, Show.venue_id == Venue.id)\
                    .join(Artist, Show.artist_id == Artist.id)\
                    .with_entities(Show.venue_id, Show.artist_id, Show.start_time, 
                                    Venue.name, Artist.name, Artist.image_link)
      if filterby == FILTER_PREVIOUS:
        shows = shows.filter(Show.start_time < datetime.today())
      elif filterby == FILTER_UPCOMING:
        shows = shows.filter(Show.start_time > datetime.today())

      pagination = shows.order_by(Show.start_time)\
                    .paginate(page=page, per_page=SHOWS_PER_PAGE)
      shows = pagination.items

    else: # ENGINE
      if filterby == FILTER_PREVIOUS:
        time_filter = f'"{SHOWS_TABLE}".start_time < \'{datetime_to_str(datetime.today())}\''
      elif filterby == FILTER_UPCOMING:
        time_filter = f'"{SHOWS_TABLE}".start_time > \'{datetime_to_str(datetime.today())}\''
      else:
        time_filter = None

      # get total count
      sql = f'SELECT COUNT(id) FROM "{SHOWS_TABLE}"'
      if time_filter is not None:
        sql = f'{sql} WHERE {time_filter}'
      total = execute(f'{sql};').scalar()

      offset = SHOWS_PER_PAGE * (page - 1)
      if offset >= total:
        abort(HTTPStatus.BAD_REQUEST.value)

      # get items for this request
      sql = f'SELECT "{SHOWS_TABLE}".venue_id, "{SHOWS_TABLE}".artist_id, "{SHOWS_TABLE}".start_time, '\
            f'"{VENUE_TABLE}".name as venue_name, "{ARTIST_TABLE}".name as artist_name, "{ARTIST_TABLE}".image_link as artist_image_link '\
            f'FROM (("{SHOWS_TABLE}" '\
            f'INNER JOIN "{VENUE_TABLE}" ON "{SHOWS_TABLE}".venue_id = "{VENUE_TABLE}".id) '\
            f'INNER JOIN "{ARTIST_TABLE}" ON "{SHOWS_TABLE}".artist_id = "{ARTIST_TABLE}".id)'
      if time_filter is not None:
        sql = f'{sql} WHERE {time_filter}'
      sql = f'{sql} ORDER BY "{SHOWS_TABLE}".start_time LIMIT {SHOWS_PER_PAGE} OFFSET {offset};'

      shows = execute(sql).mappings().fetchall()
      
      pagination = Pagination(None, page, SHOWS_PER_PAGE, total, shows)
      shows = pagination.items
           
  except:
      print_exc_info()
      abort(HTTPStatus.INTERNAL_SERVER_ERROR.value)

  # [{'venue_id': ?, 'artist_id' ?, ...}, {}, ...] }
  data = [{k: show[v] if k != 'start_time' else show[v].isoformat() for k, v in SHOWS_KEYS.items()} for show in shows]

  return render_template('pages/shows.html', shows=data, pagination=pagination)


def populate_show(show, form):
  '''
  Populate a show from a form
  '''
  populate_model(show, form, ["artist_id", "venue_id", "start_time"])
  duration = form.duration.data
  if form.duration.data < 0:
    duration = form.other_duration.data.hour * 60 + form.other_duration.data.minute
  
  if ORM:
    show.duration = duration
  else: # ENGINE
    show["duration"] = duration
  return show


class Booking:
  ''' Class representing a booking '''
  def __init__(self, name, start_time, duration) -> None:
      self.name = name
      self.start_time = start_time
      self.duration = duration
      self.end_time = start_time + timedelta(minutes=duration)


class AvailabilitySlot:
  ''' Class representing an availability slot '''
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


def verify_show(show):
  '''
  Verify that a show can be scheduled without conflict
  '''
  if ORM:
    artist_id = show.artist_id
    venue_id = show.venue_id
    start_date = show.start_date
    start_time = show.start_time
    end_time = show.end_time
    as_type = EntityResult.MODEL
  else: # ENGINE
    artist_id = show["artist_id"]
    venue_id = show["venue_id"]
    start_date = show["start_time"].date()
    start_time = show["start_time"]
    end_time = show["start_time"] + timedelta(minutes=show["duration"])
    as_type = EntityResult.DICT

  booking_conflict = None
  bookings = bookings_by_venue(venue_id, start_date)
  if bookings is not None:
    bookings_list = [Booking(b["name"], b["start_time"], b["duration"]) for b in bookings]
    for booking in bookings_list:
      if start_time >= booking.start_time and start_time <= booking.end_time:
        booking_conflict = booking
      elif end_time >= booking.start_time and end_time <= booking.end_time:
        booking_conflict = booking
        
      if booking_conflict is not None:  
        break

  availability = availability_by_artist(artist_id, start_time, as_type=as_type)
  dow = start_time.weekday()
  if dow == 0:    # monday
    slot = availability.monday if ORM else (availability["mon_from"], availability["mon_to"])
  elif dow == 1:  # tuesday
    slot = availability.tuesday if ORM else (availability["tue_from"], availability["tue_to"])
  elif dow == 2:  # wednesday
    slot = availability.wednesday if ORM else (availability["wed_from"], availability["wed_to"])
  elif dow == 3:  # thursday
    slot = availability.thursday if ORM else (availability["thu_from"], availability["thu_to"])
  elif dow == 4:  # friday
    slot = availability.friday if ORM else (availability["fri_from"], availability["fri_to"])
  elif dow == 5:  # saturday
    slot = availability.saturday if ORM else (availability["sat_from"], availability["sat_to"])
  else:           # sunday
    slot = availability.sunday if ORM else (availability["sun_from"], availability["sun_to"])
  slot = AvailabilitySlot(pair=slot)

  artist_conflict = None                  # availability & show mismatch
  availability = slot.duration is not None # no availability
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


def create_show_orm(show):
  '''
  Create a show in ORM mode
  show:   show to create
  '''
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


def show_insert_sql(show: dict):
  ''' Generate show insert SQL'''
  properties = model_property_list(SHOWS_TABLE, IGNORE_ID)
  properties_list = ', '.join(properties)
  value_dict = {p: str(show[p]) if p != 'start_time' else f"'{datetime_to_str(show[p])}'" for p in properties}
  values = [value_dict[p] for p in properties]
  values_list = ', '.join(values)
  return f'INSERT INTO "{SHOWS_TABLE}"({properties_list}) VALUES ({values_list});'


def create_show_engine(show: dict):
  '''
  Create an show in ENGINE mode
  show:   show to create
  '''
  success = False
  try:
    new_show = execute(show_insert_sql(show))
    success = new_show.rowcount > 0
  except:
    print_exc_info()

  return success


NO_SELECTION = -1

def create_show_submission():
  '''
  List a show

  Request query parameters:
  artist: id of artist selected for show
  venue:  id of venue selected for show
  '''
  artist_id = int(request.args.get('artist', str(NO_SELECTION)))
  venue_id = int(request.args.get('venue', str(NO_SELECTION)))

  if ORM:
    artists = Artist.query.with_entities(Artist.id, Artist.name).order_by(Artist.name).all()
    venues = Venue.query.with_entities(Venue.id, Venue.name).order_by(Venue.name).all()
  else: # ENGINE
    artists = execute(f'SELECT id, name FROM "{ARTIST_TABLE}" ORDER BY name;')\
                .fetchall()
    artists = [(a["id"], a["name"]) for a in artists]
    venues = execute(f'SELECT id, name FROM "{VENUE_TABLE}" ORDER BY name;')\
                .fetchall()
    venues = [(a["id"], a["name"]) for a in venues]


  artist_choices = [(a[0], a[1]) for a in artists]
  artist_choices.insert(0, (NO_SELECTION, "Select artist"))
  venue_choices = [(v[0], v[1]) for v in venues]
  venue_choices.insert(0, (NO_SELECTION, "Select venue"))

  form = ShowForm()
  if request.method == 'POST':
    artists = form.artist_id.data
    venues = form.venue_id.data
  else:
    artists = list()
    venues = list()

  # set choices & validators based on possible options
  set_singleselect_field_options(form.artist_id, artist_choices, [a[0] for a in artist_choices if a[0] != NO_SELECTION], artists)
  set_singleselect_field_options(form.venue_id, venue_choices, [v[0] for v in venue_choices if v[0] != NO_SELECTION], venues)
  if artist_id != NO_SELECTION:
    form.artist_id.data = artist_id
  if venue_id != NO_SELECTION:
    form.venue_id.data = venue_id

  response = None
  status_code = HTTPStatus.OK.value   # status code for GET
  if request.method == 'POST':
    status_code = HTTPStatus.ACCEPTED.value   # status code for errors in form or conflict

    if form.validate_on_submit():
      show = populate_show(Show() if ORM else new_model_dict(AVAILABILITY_TABLE), form)

      verification = verify_show(show)

      artist = label_from_valuelabel_list(artist_choices, form.artist_id.data)
      venue = label_from_valuelabel_list(venue_choices, form.venue_id.data)

      if not verification["ok"]:
        time_disp = lambda dt: dt.strftime(AVAILABILITY_TIME_FMT)

        if verification["show"] is not None:
          err = verification["show"]
          flash(f'Booking conflict. A show by {err.name} is booked from ' \
                f'{time_disp(err.start_time)} to {time_disp(err.end_time)}.')
        if verification["artist"] is not None:
          err = verification["artist"]
          flash(f'Artist availability conflict. Artist is only available from ' \
                f'{time_disp(err.start_time)} to {time_disp(err.end_time)}.')
        if not verification["availability"]:
          flash(f'Artist availability conflict. Artist is not available.')

      else:
        if ORM:
          success = create_show_orm(show)
        else: # ENGINE
          success = create_show_engine(show)

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
                    title= 'Create Show',
                    submit_action=url_for('create_show_submission'),
                    cancel_url=url_for('index'),
                    submit_text='Create',
                    submit_title='Create show'
                )
              )

  response.status_code = status_code
  return response
