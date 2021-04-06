from typing import Any, Union

from flask_sqlalchemy.model import Model
from sqlalchemy.inspection import inspect
from werkzeug.datastructures import MultiDict


# check if model key is a public
def is_public(k): return k[0] != '_'


class MultiDictMixin(object):
    """
    Mixin to generate a MultiDict
    """

    @staticmethod
    def __multidict_value__(value, attrib):
        if attrib is None:
            result = value
        else:
            if isinstance(value, list):
                result = list(vars(g)[attrib] for g in value)
            elif isinstance(value, tuple):
                result = tuple(vars(g)[attrib] for g in value)
            else:
                result = list(vars(value)[attrib])
        return result

    def get_multidict(self, **kwargs):
        """
        Generate a MultiDict
        :param kwargs: keyword args where 'key' is the object property and 'value' is the required attribute
                       of the property.
                       e.g. with Parent.Child, children='name' will return Child.name as the value for Parent.Child
        """
        return MultiDict(self.get_dict(**kwargs))

    def get_dict(self, **kwargs):
        """
        Generate a dict
        :param kwargs: keyword args where 'key' is the object property and 'value' is the required attribute
                       of the property.
                       e.g. with Parent.Child, children='name' will return Child.name as the value for Parent.Child
        """
        return {k: self.__multidict_value__(v, kwargs[k] if k in kwargs else None)
                for k, v in vars(self).items() if is_public(k)}  # copy just the public data values

    def equal(self, o: object, ignore=None) -> bool:
        """
        Check if the specified object equals this
        :param o:      object to check
        :param ignore: fields to ignore
        """
        if ignore is None:
            ignore = []
        eq = isinstance(o, MultiDictMixin)
        if eq:
            for k, v in vars(self).items():
                if is_public(k) and k not in ignore:
                    eq = (v == vars(o)[k])
                    if not eq:
                        break
        return eq


def __key_list(d: dict, ignore=None) -> set:
    if ignore is None:
        ignore = []
    return set([k for k in d.keys() if is_public(k) and k not in ignore])


def equal_dict(a: dict, b: dict, ignore=None) -> bool:
    """
    Check if the specified dicts are equal
    :param a:      first dict
    :param b:      second dict
    :param ignore: properties to ignore
    """
    if ignore is None:
        ignore = []
    keys_a = __key_list(a, ignore)
    keys_b = __key_list(b, ignore)
    eq = not keys_a.isdisjoint(keys_b)
    for k in keys_a:
        eq = (a[k] == b[k])
        if not eq:
            break
    return eq


def dict_disjoint(base: dict, other: dict, ignore=None) -> list:
    """
    Get a list of properties in 'other' that are different from 'base'
    :param base:   base dict
    :param other:  dict to check for differences
    :param ignore: properties to ignore
    """
    if ignore is None:
        ignore = []
    keys_a = __key_list(base, ignore)
    keys_b = __key_list(other, ignore)
    disjoint = [k for k in keys_a if k not in keys_b or base[k] != other[k]]
    return disjoint


def model_items(model: Union[dict, Model], ignore=None) -> Union[list[tuple[Any, Any]], list[tuple[str, Any]]]:
    """
    Get a list of public items

    Note: will only return properties that have been set for Model

    :param model:  dict or Model to get items from
    :param ignore: properties to ignore
    """
    if ignore is None:
        ignore = []
    if isinstance(model, dict):
        items = [(k, v) for k, v in model.items() if k not in ignore]
    else:
        items = [(k, v) for k, v in vars(model).items() if is_public(k) and k not in ignore]
    return items


def model_property_list(model: Model, ignore=None):
    """
    Get the property list for a model 
    :param model:  Model to get properties from
    :param ignore: properties to ignore
    """
    if ignore is None:
        ignore = []
    return [c_attr.key for c_attr in inspect(model).mapper.column_attrs
            if c_attr.key not in ignore]
