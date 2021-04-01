from datetime import datetime, time
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SelectMultipleField, DateTimeField
from wtforms.fields.core import BooleanField, RadioField, TimeField
from wtforms.fields.simple import TextAreaField
from wtforms.validators import InputRequired, AnyOf, Optional, URL, ValidationError
import phonenumbers

from misc import current_datetime, get_config

# choices for possible states
STATE_CHOICES = [
    ('AL', 'AL'),
    ('AK', 'AK'),
    ('AZ', 'AZ'),
    ('AR', 'AR'),
    ('CA', 'CA'),
    ('CO', 'CO'),
    ('CT', 'CT'),
    ('DE', 'DE'),
    ('DC', 'DC'),
    ('FL', 'FL'),
    ('GA', 'GA'),
    ('HI', 'HI'),
    ('ID', 'ID'),
    ('IL', 'IL'),
    ('IN', 'IN'),
    ('IA', 'IA'),
    ('KS', 'KS'),
    ('KY', 'KY'),
    ('LA', 'LA'),
    ('ME', 'ME'),
    ('MT', 'MT'),
    ('NE', 'NE'),
    ('NV', 'NV'),
    ('NH', 'NH'),
    ('NJ', 'NJ'),
    ('NM', 'NM'),
    ('NY', 'NY'),
    ('NC', 'NC'),
    ('ND', 'ND'),
    ('OH', 'OH'),
    ('OK', 'OK'),
    ('OR', 'OR'),
    ('MD', 'MD'),
    ('MA', 'MA'),
    ('MI', 'MI'),
    ('MN', 'MN'),
    ('MS', 'MS'),
    ('MO', 'MO'),
    ('PA', 'PA'),
    ('RI', 'RI'),
    ('SC', 'SC'),
    ('SD', 'SD'),
    ('TN', 'TN'),
    ('TX', 'TX'),
    ('UT', 'UT'),
    ('VT', 'VT'),
    ('VA', 'VA'),
    ('WA', 'WA'),
    ('WV', 'WV'),
    ('WI', 'WI'),
    ('WY', 'WY'),
]
# choices for possible states with unselected option
STATE_CHOICES_WITH_SEL = STATE_CHOICES.copy()
STATE_CHOICES_WITH_SEL.insert(0, ('none', 'Select state'))
# valid options for state selection
STATES = [s[0] for s in STATE_CHOICES]

OTHER_DURATION = -1
DURATION_CHOICES = [
    (30, "\N{Vulgar Fraction One Half} hour"), 
    (60, "1 hour"), 
    (90, "1\N{Vulgar Fraction One Half} hours"),
    (120, "2 hours"),
    (OTHER_DURATION, "Other")
]

def validate_phone(form, field):
    '''
    Validate phone numbers
    See https://pypi.org/project/phonenumbers/
    '''
    try:
        input_number = phonenumbers.parse(field.data, get_config("DEFAULT_REGION"))
        if not phonenumbers.is_valid_number(input_number):
            if not phonenumbers.is_possible_number(input_number):
                raise ValidationError('Invalid phone number.')
    except:
        raise ValidationError('Invalid phone number.')

class ValidateTimeFields(object):
    '''
    Validate the two time fields
    from_field: start time field
    to_field:   end time field
    message:    validation error message
    '''
    def __init__(self, from_field=None, to_field=None, message=None):
        self.from_field = from_field
        self.to_field = to_field
        if not message:
            message = f'{to_field.label.text} must be later than {from_field.label.text}'
        self.message = message

    def __call__(self, form, field):
        from_time = self.from_field.data
        to_time = self.to_field.data
        if from_time == ZERO_AM:
            pass    # available from start of day
        elif to_time == MIDNIGHT:
            pass    # available until midnight
        elif to_time <= from_time:
            raise ValidationError(self.message)


class ValidateDateTime(object):
    '''
    Validate a date time field
    min:        min datetime allowed, or a value of FIELD_DEFAULT uses the field default value
    max:        max datetime allowed, or a value of FIELD_DEFAULT uses the field default value
    format:     datetime format for error message
    message:    validation error message
    '''
    FIELD_DEFAULT = 'default'

    def __init__(self, min=datetime.min, max=datetime.max, format=None, message=None):
        self.min = min
        self.max = max
        self.format = format
        self.message = message

    def __call__(self, form, field):
        if self.min == ValidateDateTime.FIELD_DEFAULT:
            min_time = field.default
        else:
            min_time = self.min
        if self.max == ValidateDateTime.FIELD_DEFAULT:
            max_time = field.default
        else:
            max_time = self.max
        
        min_ng = field.data < min_time
        max_ng = field.data > max_time
        if min_ng or max_ng:
            if self.format is None:
                min_time_str = str(min_time)
                max_time_str = str(max_time)
            else:
                min_time_str = min_time.strftime(self.format)
                max_time_str = max_time.strftime(self.format)

            if self.message is None:
                criteria = f'between {min_time_str} and {max_time_str}'
                if min_ng:
                    if max_time == datetime.max:
                        criteria = f'greater than {min_time_str}'
                else:
                    if min_time == datetime.min:
                        criteria = f'less than {max_time_str}'
                message = f'Invalid datetime, must be {criteria}'
            else:
                message = self.message
            raise ValidationError(message)


APP_DATE_FMT = '%Y-%m-%d'
APP_TIME_FMT = '%H:%M'
APP_DATETIME_FMT = APP_DATE_FMT + ' ' + APP_TIME_FMT

class AppTimeField(TimeField):
    """
    Same as TimeField, except uses last value entered to determine time
    """
    # TimeField extends from DateTimeField and gets a list of initial & edited 
    # values as the valuelist to process which results in conversion errors
    def __init__(self, label=None, validators=None, format='%H:%M', **kwargs):
        super(AppTimeField, self).__init__(label, validators, format, **kwargs)

    def process_formdata(self, valuelist):
        if valuelist:
            time_str = valuelist[-1]
            try:
                self.data = datetime.strptime(time_str, self.format).time()
            except ValueError:
                self.data = None
                raise ValueError(self.gettext('Not a valid time value'))

#
# Note: form field names must match model field names, this is to allow population of
#       model objects from forms by copying attributes
#

class ShowForm(FlaskForm):
    artist_id = SelectField(
        'Artist', validators=[InputRequired()],
        coerce=int,
        choices=[]
    )
    venue_id = SelectField(
        'Venue', validators=[InputRequired()],
        coerce=int,
        choices=[]
    )
    start_time = DateTimeField(
        'Start time', 
        validators=[InputRequired(), 
                        ValidateDateTime(min=ValidateDateTime.FIELD_DEFAULT, format=APP_DATETIME_FMT)],
        format=APP_DATETIME_FMT,
        default=current_datetime()
    )
    duration = RadioField(
        'Duration', validators=[],
        coerce=int,
        choices=DURATION_CHOICES
    )
    other_duration = AppTimeField(
        'Other Duration', validators=[Optional()],
        format=APP_TIME_FMT
    )

    def validate_duration(form, field):
        if field.data == OTHER_DURATION:
            form.other_duration.validators=[InputRequired()]
        else:
            form.other_duration.validators=[Optional()]


class VenueForm(FlaskForm):
    name = StringField(
        'name', validators=[InputRequired()]
    )
    city = StringField(
        'city', validators=[InputRequired()]
    )
    state = SelectField(
        'state', validators=[InputRequired(), AnyOf(STATES)],
        choices=STATE_CHOICES
    )
    address = StringField(
        'address', validators=[InputRequired()]
    )
    phone = StringField(
        'phone', validators=[InputRequired(), validate_phone],
    )
    website = StringField(
        'website', validators=[Optional(), URL()]
    )
    image_link = StringField(
        'image_link', validators=[Optional(), URL()]
    )
    # choices & validators need to be set dynamically in controller
    genres = SelectMultipleField(
        'genres', validators=[InputRequired()],
        choices = []
    )
    facebook_link = StringField(
        'facebook_link', validators=[Optional(), URL()]
    )
    seeking_talent = BooleanField(
        'seeking_talent'
    )
    seeking_description = TextAreaField(
        'seeking_description', validators=[Optional()]
    )


AVAILABILITY_FROM_DATE_FMT = APP_DATETIME_FMT
AVAILABILITY_DATE_FMT = APP_DATE_FMT
AVAILABILITY_TIME_FMT = APP_TIME_FMT

class ArtistForm(FlaskForm):

    name = StringField(
        'name', validators=[InputRequired()]
    )
    city = StringField(
        'city', validators=[InputRequired()]
    )
    state = SelectField(
        'state', validators=[InputRequired(), AnyOf(STATES)],
        choices=STATE_CHOICES
    )
    phone = StringField(
        'phone', validators=[InputRequired(), validate_phone],
    )
    website = StringField(
        'website', validators=[Optional(), URL()]
    )
    image_link = StringField(
        'image_link', validators=[Optional(), URL()]
    )
    # choices & validators need to be set dynamically in controller
    genres = SelectMultipleField(
        'genres', validators=[InputRequired()],
        choices = []
    )
    facebook_link = StringField(
        'facebook_link', validators=[Optional(), URL()]
    )
    seeking_venue = BooleanField(
        'seeking_venue'
    )
    seeking_description = TextAreaField(
        'seeking_description', validators=[Optional()]
    )

    from_date = DateTimeField(
        'From time', 
        validators=[InputRequired(), 
                        ValidateDateTime(min=ValidateDateTime.FIELD_DEFAULT, format=AVAILABILITY_FROM_DATE_FMT)],
        format=AVAILABILITY_FROM_DATE_FMT,
        default=current_datetime()
    )
    mon_from = AppTimeField(
        'Monday start', validators=[Optional()],
        format=AVAILABILITY_TIME_FMT,
    )
    mon_to = AppTimeField(
        'Monday end', validators=[Optional()],
        format=AVAILABILITY_TIME_FMT,
    )
    tue_from = AppTimeField(
        'Tuesday start', validators=[Optional()],
        format=AVAILABILITY_TIME_FMT,
    )
    tue_to = AppTimeField(
        'Tuesday end', validators=[Optional()],
        format=AVAILABILITY_TIME_FMT,
    )
    wed_from = AppTimeField(
        'Wednesday start', validators=[Optional()],
        format=AVAILABILITY_TIME_FMT,
    )
    wed_to = AppTimeField(
        'Wednesday end', validators=[Optional()],
        format=AVAILABILITY_TIME_FMT,
    )
    thu_from = AppTimeField(
        'Thursday start', validators=[Optional()],
        format=AVAILABILITY_TIME_FMT,
    )
    thu_to = AppTimeField(
        'Thursday end', validators=[Optional()],
        format=AVAILABILITY_TIME_FMT,
    )
    fri_from = AppTimeField(
        'Friday start', validators=[Optional()],
        format=AVAILABILITY_TIME_FMT,
    )
    fri_to = AppTimeField(
        'Friday end', validators=[Optional()],
        format=AVAILABILITY_TIME_FMT,
    )
    sat_from = AppTimeField(
        'Saturday start', validators=[Optional()],
        format=AVAILABILITY_TIME_FMT,
    )
    sat_to = AppTimeField(
        'Saturday end', validators=[Optional()],
        format=AVAILABILITY_TIME_FMT,
    )
    sun_from = AppTimeField(
        'Sunday start', validators=[Optional()],
        format=AVAILABILITY_TIME_FMT,
    )
    sun_to = AppTimeField(
        'Sunday end', validators=[Optional()],
        format=AVAILABILITY_TIME_FMT,
    )

    def validate_mon_from(form, field):
        validate_from_to_fields(field, form.mon_to)

    def validate_tue_from(form, field):
        validate_from_to_fields(field, form.tue_to)

    def validate_wed_from(form, field):
        validate_from_to_fields(field, form.wed_to)

    def validate_thu_from(form, field):
        validate_from_to_fields(field, form.thu_to)

    def validate_thu_from(form, field):
        validate_from_to_fields(field, form.thu_to)

    def validate_sat_from(form, field):
        validate_from_to_fields(field, form.sat_to)

    def validate_sun_from(form, field):
        validate_from_to_fields(field, form.sun_to)


# from_time of 00:00 is considered start of day and to_time of 00:00 is considered midnight
ZERO_AM = time(hour=0, minute=0)
MIDNIGHT = time(hour=0, minute=0)

def validate_from_to_fields(from_field, to_field):
    if from_field.data == None:
        from_field.validators=[Optional()]
        to_field.validators=[Optional()]
    else:
        from_field.validators=[InputRequired()]
        to_field.validators=[InputRequired(), ValidateTimeFields(from_field=from_field, to_field=to_field)]



class NCSSearchForm(FlaskForm):
    name = StringField(
        'name', validators=[Optional()]
    )
    city = StringField(
        'city', validators=[Optional()]
    )
    state = SelectField(
        'state', validators=[Optional(), AnyOf(STATES)],
        choices = STATE_CHOICES_WITH_SEL
    )






