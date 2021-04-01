from http import HTTPStatus
from flask import abort
from wtforms.validators import AnyOf, InputRequired, ValidationError

from models import Genre
from misc import get_config, print_exc_info

# from sqlalchemy import in_
if get_config("USE_ORM"):
  from models import Genre
  ORM = True
else:
  from engine import execute
  from models import GENRES_TABLE
  ORM = False

ENGINE = not ORM


class OneOrMoreOf(AnyOf):
    """
    Compares the incoming data to a sequence of valid inputs.

    :param values:
        A sequence of valid inputs.
    :param message:
        Error message to raise in case of a validation error. `%(values)s`
        contains the list of values.
    :param values_formatter:
        Function used to format the list of values in the error message.
    """
    def __call__(self, form, field):
        valid = 0
        for sel in field.data:
            if sel in self.values:
                valid = valid + 1

        if valid == 0:
            message = self.message
            if message is None:
                message = field.gettext('Invalid value, must be one or more of: %(values)s.')

            raise ValidationError(message % dict(values=self.values_formatter(self.values)))


def populate_model(model, form, attributes):
  '''
  Populate a model from a form
  '''
  if ORM:
    # can't use form.populate_obj(model) as get no attribute error '_sa_instance_state'
    for a in attributes:
      model.__setattr__(a, form[a].data)
  else: # ENGINE
    for a in attributes:
      model[a] = form[a].data
  return model


def get_genre_list(names: list):
  '''
  Get the genres corresponding to the specified list
  '''
  try:
    if ORM:
      return Genre.query.filter(Genre.name.in_(names)).all()
    else: # ENGINE
      in_list = ["'"+g+"'" for g in names]
      in_list = ", ".join(in_list)

      # genres is list of names
      genres = execute(f'SELECT * FROM "{GENRES_TABLE}" where "{GENRES_TABLE}".name in ({in_list});')
      keys = [k for k in genres.keys()]
      results = [g for g in genres]
      genres = [g['name'] for g in results]
      genre_objs = [{k: g[k] for k in keys} for g in results]

      return genres, genre_objs
  except:
      print_exc_info()
      abort(HTTPStatus.INTERNAL_SERVER_ERROR.value)


def populate_genred_model(model, form, attributes):
  '''
  Populate a model with genres from a form
  '''
  populate_model(model, form, attributes)
  if ORM:
    model.genres = get_genre_list(form["genres"].data)
  else: # ENGINE
    genres, genre_objs = get_genre_list(form["genres"].data)
    model["genres"] = genres
    model["__genre_objs"] = genre_objs

  return model


def set_select_field_options(field, choices, validator, data):
  '''
  Set the options for a WTForms field
  field:      field to set options on
  choices:    possible options
  validator:  additional validator
  data:       value to set
  '''
  field.choices = choices
  field.validators = [InputRequired(), validator]
  if isinstance(data, list):
    field.process_formdata(data)
  else:
    field.process_data(data)


def set_singleselect_field_options(field, choices, values, data):
  '''
  Set the options for a single select WTForms field
  field:      field to set options on
  choices:    possible options
  validator:  additional validator
  data:       value to set
  '''
  set_select_field_options(field, choices, 
          AnyOf(values, message="Please select a value from the list"), data)


def set_multiselect_field_options(field, choices, values, data):
  '''
  Set the options for a multi select WTForms field
  field:      field to set options on
  choices:    possible options
  validator:  additional validator
  data:       value to set
  '''
  set_select_field_options(field, choices, 
          OneOrMoreOf(values, message="Please select one or more values from the list"), data)
