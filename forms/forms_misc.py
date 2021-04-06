from typing import Union, Any

from flask_sqlalchemy import Model
from flask_wtf import FlaskForm
from wtforms import SelectMultipleField, SelectField
from wtforms.validators import AnyOf, InputRequired, ValidationError

from misc import get_genre_list


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

    def __init__(self, values, message=None, values_formatter=None):
        super().__init__(values, message, values_formatter)

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


def populate_model(model: Union[Model, dict], form: FlaskForm, properties: list):
    """
    Populate a model from a form
    :param model:       entity to populate
    :param form:        form to populate from
    :param properties:  list of properties to populate
    """
    if isinstance(model, dict):
        for a in properties:
            model[a] = form[a].data
    else:
        # can't use form.populate_obj(model) as get no attribute error '_sa_instance_state'
        for a in properties:
            model.__setattr__(a, form[a].data)
    return model


def populate_model_property(model: Union[Model, dict], prop: str, value: Any):
    """
    Populate a model property from a form
    :param model:   entity to populate
    :param prop:    property to populate
    :param value:   value to set
    """
    if isinstance(model, dict):
        model[prop] = value
    else:
        model.__setattr__(prop, value)
    return model


def populate_genred_model(model: Union[Model, dict], form: FlaskForm, properties: list):
    """
    Populate a model with genres from a form
    :param model:       entity to populate
    :param form:        form to populate from
    :param properties:  list of properties to populate
    """
    populate_model(model, form, properties)
    genres = get_genre_list(form["genres"].data)
    populate_model_property(model, "genres", genres)
    return model


def set_select_field_options(field: Union[SelectMultipleField, SelectField], choices: Union[list, Any],
                             validator: object, data: Any):
    """
    Set the options for a WTForms field
    :param field:      field to set options on
    :param choices:    possible options
    :param validator:  additional validator
    :param data:       value to set
    """
    field.choices = choices
    field.validators = [InputRequired(), validator]
    if isinstance(data, list):
        field.process_formdata(data)
    else:
        field.process_data(data)


def set_singleselect_field_options(field: SelectField, choices: Union[list, Any], values: list, data: Any):
    """
    Set the options for a single select WTForms field
    :param field:      field to set options on
    :param choices:    possible options
    :param values:     A sequence of valid inputs.
    :param data:       value to set
    """
    set_select_field_options(field, choices,
                             AnyOf(values, message="Please select a value from the list"), data)


def set_multiselect_field_options(field: SelectMultipleField, choices: Union[list, Any], values: list, data: Any):
    """
    Set the options for a multi select WTForms field
    :param field:      field to set options on
    :param choices:    possible options
    :param values:     A sequence of valid inputs.
    :param data:       value(s) to set
    """
    set_select_field_options(field, choices,
                             OneOrMoreOf(values, message="Please select one or more values from the list"), data)
