# ---------------------------------------------------------------------------- #
# Imports
# ---------------------------------------------------------------------------- #
from datetime import timedelta
from typing import List, Union, Callable

from flask_sqlalchemy import SQLAlchemy, Model
from sqlalchemy import Date, cast, Column
from sqlalchemy.ext.hybrid import hybrid_property

from .models_misc import MultiDictMixin, model_property_list, fq_column

db = SQLAlchemy()

# ---------------------------------------------------------------------------- #
# Constants.
# ---------------------------------------------------------------------------- #
ADDRESS_ITEM_LEN = 120
PHONE_LEN = 120
URL_LINK_LEN = 120
IMAGE_LINK_LEN = 500
SEEKING_ITEM_LEN = 120

# ---------------------------------------------------------------------------- #
# Models.
# https://docs.sqlalchemy.org/en/13/core/schema.html
# https://flask-sqlalchemy.palletsprojects.com/en/2.x/models/
# https://docs.sqlalchemy.org/en/13/orm/basic_relationships.html
# ---------------------------------------------------------------------------- #

VENUE_TABLE = 'Venue'  # name of venue table
ARTIST_TABLE = 'Artist'  # name of artist table
SHOWS_TABLE = 'Shows'  # name of shows table
GENRES_TABLE = 'Genres'  # name of genres table
VENUE_GENRES_TABLE = 'venue_genres'  # name of venue/genres link table
ARTIST_GENRES_TABLE = 'artist_genres'  # name of artist/genres link table
AVAILABILITY_TABLE = 'Availability'  # name of availability table

# many-to-many relationship between venues and genres
venue_genres = db.Table(VENUE_GENRES_TABLE, db.Model.metadata,
                        db.Column('venue_id', db.Integer, db.ForeignKey(f"{VENUE_TABLE}.id"), primary_key=True),
                        db.Column('genre_id', db.Integer, db.ForeignKey(f"{GENRES_TABLE}.id"), primary_key=True)
                        )

# many-to-many relationship between artists and genres
artist_genres = db.Table(ARTIST_GENRES_TABLE, db.Model.metadata,
                         db.Column('artist_id', db.Integer, db.ForeignKey(f"{ARTIST_TABLE}.id"), primary_key=True),
                         db.Column('genre_id', db.Integer, db.ForeignKey(f"{GENRES_TABLE}.id"), primary_key=True)
                         )


# venue table
class Venue(MultiDictMixin, db.Model):
    __tablename__ = VENUE_TABLE

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    address = db.Column(db.String(ADDRESS_ITEM_LEN), nullable=False)
    city = db.Column(db.String(ADDRESS_ITEM_LEN), nullable=False)
    state = db.Column(db.String(ADDRESS_ITEM_LEN), nullable=False)
    phone = db.Column(db.String(PHONE_LEN), nullable=True)
    website = db.Column(db.String(URL_LINK_LEN), nullable=True)
    facebook_link = db.Column(db.String(URL_LINK_LEN), nullable=True)
    image_link = db.Column(db.String(IMAGE_LINK_LEN), nullable=True)

    genres = db.relationship('Genre', secondary=venue_genres, lazy='joined')

    seeking_talent = db.Column(db.Boolean, nullable=False, default=False)
    seeking_description = db.Column(db.String(SEEKING_ITEM_LEN))

    def __repr__(self):
        return f"<Venue(id={self.id}, name={self.name}, address={self.address}, city={self.city}, " \
               f"state={self.state}, phone={self.phone}, website={self.website}, facebook_link={self.facebook_link}, " \
               f"image_link={self.image_link}, genres={self.genres}, seeking_talent={self.seeking_talent}, " \
               f"seeking_description={self.seeking_description})>"


# artist table
class Artist(MultiDictMixin, db.Model):
    __tablename__ = ARTIST_TABLE

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    city = db.Column(db.String(ADDRESS_ITEM_LEN), nullable=True)
    state = db.Column(db.String(ADDRESS_ITEM_LEN), nullable=True)
    phone = db.Column(db.String(PHONE_LEN), nullable=True)
    website = db.Column(db.String(URL_LINK_LEN), nullable=True)
    facebook_link = db.Column(db.String(URL_LINK_LEN), nullable=True)
    image_link = db.Column(db.String(IMAGE_LINK_LEN), nullable=True)

    genres = db.relationship('Genre', secondary=artist_genres, lazy='joined')

    seeking_venue = db.Column(db.Boolean, nullable=False, default=False)
    seeking_description = db.Column(db.String(SEEKING_ITEM_LEN))

    def __repr__(self):
        return f"<Artist(id={self.id}, name={self.name}, city={self.city}, " \
               f"state={self.state}, phone={self.phone}, website={self.website}, facebook_link={self.facebook_link}, " \
               f"image_link={self.image_link}, genres={self.genres}, seeking_venue={self.seeking_venue}, " \
               f"seeking_description={self.seeking_description})>"


# show table
class Show(MultiDictMixin, db.Model):
    __tablename__ = SHOWS_TABLE

    id = db.Column(db.Integer, primary_key=True)
    venue_id = db.Column(db.Integer, db.ForeignKey(f"{VENUE_TABLE}.id"), nullable=False)
    venue = db.relationship('Venue')
    artist_id = db.Column(db.Integer, db.ForeignKey(f"{ARTIST_TABLE}.id"), nullable=False)
    artist = db.relationship('Artist')
    start_time = db.Column(db.DateTime, nullable=False)
    duration = db.Column(db.Integer, nullable=False, default=0)

    @hybrid_property
    def start_date(self):
        return self.start_time.date()

    @start_date.expression
    def start_date(cls):
        return cast(cls.start_time, Date)

    @hybrid_property
    def end_time(self):
        return self.start_time + timedelta(minutes=self.duration)

    def __repr__(self):
        return f"<Show(id={self.id}, venue_id={self.venue_id}, artist_id={self.artist_id}, " \
               f"start_time={self.start_time}, duration={self.duration})>"


# genre table
class Genre(MultiDictMixin, db.Model):
    __tablename__ = GENRES_TABLE

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False, unique=True)

    def __repr__(self):
        return f"<Genre(id={self.id}, name={self.name})>"


# availability table

def is_available_time_key(key):
    return key.endswith('_to') or key.endswith('_from')


def is_available(availability):
    """ Check if has any availability """
    available = False
    if isinstance(availability, dict):
        items = availability.items()
    else:
        items = vars(availability).items()

    for k, v in items:
        if is_available_time_key(k):
            available = v is not None
            if available:
                break
    return available


class Availability(MultiDictMixin, db.Model):
    __tablename__ = AVAILABILITY_TABLE

    id = db.Column(db.Integer, primary_key=True)
    artist_id = db.Column(db.Integer, db.ForeignKey(f"{ARTIST_TABLE}.id"), nullable=False)
    artist = db.relationship('Artist')
    from_date = db.Column(db.DateTime, nullable=False)
    mon_from = db.Column(db.Time, nullable=True)
    mon_to = db.Column(db.Time, nullable=True)
    tue_from = db.Column(db.Time, nullable=True)
    tue_to = db.Column(db.Time, nullable=True)
    wed_from = db.Column(db.Time, nullable=True)
    wed_to = db.Column(db.Time, nullable=True)
    thu_from = db.Column(db.Time, nullable=True)
    thu_to = db.Column(db.Time, nullable=True)
    fri_from = db.Column(db.Time, nullable=True)
    fri_to = db.Column(db.Time, nullable=True)
    sat_from = db.Column(db.Time, nullable=True)
    sat_to = db.Column(db.Time, nullable=True)
    sun_from = db.Column(db.Time, nullable=True)
    sun_to = db.Column(db.Time, nullable=True)

    @hybrid_property
    def monday(self):
        return self.mon_from, self.mon_to

    @hybrid_property
    def tuesday(self):
        return self.tue_from, self.tue_to

    @hybrid_property
    def wednesday(self):
        return self.wed_from, self.wed_to

    @hybrid_property
    def thursday(self):
        return self.thu_from, self.thu_to

    @hybrid_property
    def friday(self):
        return self.fri_from, self.fri_to

    @hybrid_property
    def saturday(self):
        return self.sat_from, self.sat_to

    @hybrid_property
    def sunday(self):
        return self.sun_from, self.sun_to

    def is_available(self):
        return is_available(self)

    def __repr__(self):
        return f"<Availability(id={self.id}, artist_id={self.artist_id}, " \
               f"from_date={self.from_date})>"


__PROPERTIES__ = {
    VENUE_TABLE: model_property_list(Venue()),
    ARTIST_TABLE: model_property_list(Artist()),
    SHOWS_TABLE: model_property_list(Show()),
    GENRES_TABLE: model_property_list(Genre()),
    VENUE_GENRES_TABLE: venue_genres.columns.keys(),
    ARTIST_GENRES_TABLE: artist_genres.columns.keys(),
    AVAILABILITY_TABLE: model_property_list(Availability()),
}


def get_model_property_list(model: str) -> Union[List, None]:
    """
    Generate a list of all the property names for the specified model
    :param model:  the table name of the required model; one of VENUE_TABLE etc.
    """
    if model in __PROPERTIES__.keys():
        return __PROPERTIES__[model]
    else:
        return None


class Entity:
    """
    Class representing an entity in both orm and engine form
    :param orm_model:               ORM model
    :param eng_table:               Database table name
    :param object_factory:          function to create new model objects
    :param orm_genre_link_column:   model/genre link table
    :param eng_genre_link_table:    model/genre link table name
    :param eng_genre_link_column:   model/genre link column name
    :param orm_show_column:         foreign key column in show model linking show and entity
    :param eng_show_column:         name of foreign key column in show model linking show and entity
    """

    def __init__(self, orm_model: Model, eng_table: str, object_factory: Callable,
                 orm_genre_link_column: Column = None, eng_genre_link_table: str = None, eng_genre_link_column: str = None,
                 orm_show_column: Column = None, eng_show_column: str = None):
        self.orm_model = orm_model
        self.eng_table = eng_table
        self.object_factory = object_factory
        self.orm_genre_link_column = orm_genre_link_column
        self.eng_genre_link_table = eng_genre_link_table
        self.eng_genre_link_column = eng_genre_link_column
        self.orm_show_column = orm_show_column
        self.eng_show_column = eng_show_column

    def model(self):
        """ Get a new sqlalchemy model """
        return self.object_factory()

    def model_dict(self):
        """ Get a new model dict """
        return new_model_dict(self.eng_table)

    def fq_genre_link(self):
        return fq_column(self.eng_genre_link_table, self.eng_genre_link_column) \
            if self.eng_genre_link_column is not None else None

    def fq_show_column(self):
        return fq_column(SHOWS_TABLE, self.eng_show_column) \
            if self.eng_show_column is not None else None

    def fq_id(self):
        return fq_column(self.eng_table, "id")

    def fq_column(self, column: str):
        return fq_column(self.eng_table, column)


__ENTITIES__ = {
    VENUE_TABLE: Entity(Venue, VENUE_TABLE, lambda: Venue(),
                        orm_genre_link_column=venue_genres.columns.get('venue_id'),
                        eng_genre_link_table=VENUE_GENRES_TABLE,
                        eng_genre_link_column='venue_id',
                        orm_show_column=Show.venue_id, eng_show_column='venue_id'),
    ARTIST_TABLE: Entity(Artist, ARTIST_TABLE, lambda: Artist(),
                         orm_genre_link_column=artist_genres.columns.get('artist_id'),
                         eng_genre_link_table=ARTIST_GENRES_TABLE,
                         eng_genre_link_column='artist_id',
                         orm_show_column=Show.artist_id, eng_show_column='artist_id'),
    VENUE_GENRES_TABLE: Entity(venue_genres, VENUE_GENRES_TABLE, None,
                               orm_genre_link_column=venue_genres.columns.get('genre_id'),
                               eng_genre_link_column='genre_id'),
    ARTIST_GENRES_TABLE: Entity(artist_genres, ARTIST_GENRES_TABLE, None,
                                orm_genre_link_column=artist_genres.columns.get('genre_id'),
                                eng_genre_link_column='genre_id'),
    SHOWS_TABLE: Entity(Show, SHOWS_TABLE, lambda: Show()),
    GENRES_TABLE: Entity(Genre, GENRES_TABLE, lambda: Genre()),
    AVAILABILITY_TABLE: Entity(Availability, AVAILABILITY_TABLE, lambda: Availability()),
}


def get_entity(model: str) -> Union[Entity, None]:
    """
    Generate a list of all the property names for the specified model
    :param model:  the table name of the required model; one of VENUE_TABLE etc.
    """
    if model in __ENTITIES__.keys():
        return __ENTITIES__[model]
    else:
        return None


def new_model_dict(model: str) -> dict:
    """
    Generate a dict with all the properties for the specified model
    :param model:  the table name of the required model; one of VENUE_TABLE etc.
    """
    property_list = get_model_property_list(model)
    if property_list is not None:
        model = {k: None for k in property_list}
    else:
        model = None
    return model
