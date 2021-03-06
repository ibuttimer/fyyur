#!/usr/bin/env python3
# ---------------------------------------------------------------------------- #
# Imports
# ---------------------------------------------------------------------------- #
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config import SQLALCHEMY_DATABASE_URI

from datetime import datetime, time

# ---------------------------------------------------------------------------- #
# App Config.
# ---------------------------------------------------------------------------- #

engine = create_engine(SQLALCHEMY_DATABASE_URI)

Session = sessionmaker(bind=engine)
session = Session()

# ---------------------------------------------------------------------------- #
# Models.
# ---------------------------------------------------------------------------- #
from models import Venue
from models import Artist
from models import Show
from models import Genre
from models import Availability

DATETIME_FMT = "%Y-%m-%dT%H:%M:%S.%fZ"


#  Venues
#  ----------------------------------------------------------------
def populate():
    # venues
    musical_hop = Venue(
        name="The Musical Hop",
        address="1015 Folsom Street",
        city="San Francisco",
        state="CA",
        phone="123-123-1234",
        website="https://www.themusicalhop.com",
        facebook_link="https://www.facebook.com/TheMusicalHop",
        seeking_talent=True,
        seeking_description="We are on the lookout for a local artist to play every two weeks. Please call us.",
        image_link="https://images.unsplash.com/photo-1543900694-133f37abaaa5?ixlib=rb-1.2.1&ixid=eyJhcHBfaWQiOjEyMDd9&auto=format&fit=crop&w=400&q=60")
    musical_hop.genres = session.query(Genre).filter(
        Genre.name.in_(["Jazz", "Reggae", "Swing", "Classical", "Folk"])).all()

    dueling_pianos = Venue(
        name="The Dueling Pianos Bar",
        address="335 Delancey Street",
        city="New York",
        state="NY",
        phone="914-003-1132",
        website="https://www.theduelingpianos.com",
        facebook_link="https://www.facebook.com/theduelingpianos",
        seeking_talent=False,
        seeking_description="",
        image_link="https://images.unsplash.com/photo-1497032205916-ac775f0649ae?ixlib=rb-1.2.1&ixid=eyJhcHBfaWQiOjEyMDd9&auto=format&fit=crop&w=750&q=80")
    dueling_pianos.genres = session.query(Genre).filter(Genre.name.in_(["Classical", "R&B", "Hip-Hop"])).all()

    park_square = Venue(
        name="Park Square Live Music & Coffee",
        address="34 Whiskey Moore Ave",
        city="San Francisco",
        state="CA",
        phone="415-000-1234",
        website="https://www.parksquarelivemusicandcoffee.com",
        facebook_link="https://www.facebook.com/ParkSquareLiveMusicAndCoffee",
        seeking_talent=False,
        seeking_description="",
        image_link="https://images.unsplash.com/photo-1485686531765-ba63b07845a7?ixlib=rb-1.2.1&ixid=eyJhcHBfaWQiOjEyMDd9&auto=format&fit=crop&w=747&q=80")
    park_square.genres = session.query(Genre).filter(Genre.name.in_(["Rock n Roll", "Jazz", "Classical", "Folk"])).all()

    # artists
    guns_n_petals = Artist(
        name="Guns N Petals",
        city="San Francisco",
        state="CA",
        phone="326-123-5000",
        website="https://www.gunsnpetalsband.com",
        facebook_link="https://www.facebook.com/GunsNPetals",
        seeking_venue=True,
        seeking_description="Looking for shows to perform at in the San Francisco Bay Area!",
        image_link="https://images.unsplash.com/photo-1549213783-8284d0336c4f?ixlib=rb-1.2.1&ixid=eyJhcHBfaWQiOjEyMDd9&auto=format&fit=crop&w=300&q=80")
    guns_n_petals.genres = session.query(Genre).filter(Genre.name.in_(["Rock n Roll"])).all()

    matt_quevedo = Artist(
        name="Matt Quevedo",
        city="New York",
        state="NY",
        phone="300-400-5000",
        website="",
        facebook_link="https://www.facebook.com/mattquevedo923251523",
        seeking_venue=False,
        seeking_description="",
        image_link="https://images.unsplash.com/photo-1495223153807-b916f75de8c5?ixlib=rb-1.2.1&ixid=eyJhcHBfaWQiOjEyMDd9&auto=format&fit=crop&w=334&q=80")
    matt_quevedo.genres = session.query(Genre).filter(Genre.name.in_(["Jazz"])).all()

    wild_sax_band = Artist(
        name="The Wild Sax Band",
        city="San Francisco",
        state="CA",
        phone="432-325-5432",
        website="",
        facebook_link="",
        seeking_venue=False,
        seeking_description="",
        image_link="https://images.unsplash.com/photo-1558369981-f9ca78462e61?ixlib=rb-1.2.1&ixid=eyJhcHBfaWQiOjEyMDd9&auto=format&fit=crop&w=794&q=80")
    wild_sax_band.genres = session.query(Genre).filter(Genre.name.in_(["Jazz", "Classical"])).all()

    # shows
    shows = [
        Show(venue=musical_hop, artist=guns_n_petals,
             start_time=datetime.strptime("2019-05-21T21:30:00.000Z", DATETIME_FMT), duration=60),
        Show(venue=park_square, artist=matt_quevedo,
             start_time=datetime.strptime("2019-06-15T23:00:00.000Z", DATETIME_FMT), duration=60),
        Show(venue=park_square, artist=wild_sax_band,
             start_time=datetime.strptime("2035-04-01T20:00:00.000Z", DATETIME_FMT), duration=60),
        Show(venue=park_square, artist=wild_sax_band,
             start_time=datetime.strptime("2035-04-08T20:00:00.000Z", DATETIME_FMT), duration=60),
        Show(venue=park_square, artist=wild_sax_band,
             start_time=datetime.strptime("2035-04-15T20:00:00.000Z", DATETIME_FMT), duration=60),
    ]

    # set availability for artists
    availability_time = datetime.today().replace(second=0, microsecond=0)
    availability = [
        Availability(artist=guns_n_petals, from_date=availability_time,
                     sat_from=time(hour=19), sat_to=time(hour=0),
                     sun_from=time(hour=19), sun_to=time(hour=20)),
        Availability(artist=matt_quevedo, from_date=availability_time,
                     sat_from=time(hour=12), sat_to=time(hour=0),
                     sun_from=time(hour=12), sun_to=time(hour=20)),
        Availability(artist=wild_sax_band, from_date=availability_time,
                     wed_from=time(hour=19), wed_to=time(hour=20),
                     thu_from=time(hour=19), thu_to=time(hour=20),
                     fri_from=time(hour=19), fri_to=time(hour=20),
                     sat_from=time(hour=19), sat_to=time(hour=20)),
    ]

    try:
        # add venues
        session.add_all([
            musical_hop, dueling_pianos, park_square
        ])
        # add artists
        session.add_all([
            guns_n_petals, matt_quevedo, wild_sax_band
        ])
        # add shows
        session.add_all(shows)
        # add availability
        session.add_all(availability)
        session.commit()
    except:
        session.rollback()
    finally:
        session.close()


# ---------------------------------------------------------------------------- #
# Launch.
# ---------------------------------------------------------------------------- #

# Default port:
if __name__ == '__main__':
    populate()
