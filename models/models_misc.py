from typing import Any, ItemsView, Union
from flask_sqlalchemy.model import Model
from sqlalchemy.inspection import inspect
from werkzeug.datastructures import MultiDict


# check if model key is a public
is_public = lambda k: k[0] != '_'


class MultiDictMixin(object):
    '''
    Mixin to generate a MultiDict
    '''
    def __multidict_value__(self, value, attrib):
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
        '''
        Generate a MultiDict
        kwargs: keyword args where 'key' is the object property and 'value' is the required attribute 
                of the property.
                e.g. with Parent.Child, children='name' will return Child.name as the value for Parent.Child
        '''
        return MultiDict(self.get_dict(**kwargs))

    def get_dict(self, **kwargs):
        '''
        Generate a dict
        kwargs: keyword args where 'key' is the object property and 'value' is the required attribute 
                of the property.
                e.g. with Parent.Child, children='name' will return Child.name as the value for Parent.Child
        '''
        return {k: self.__multidict_value__(v, kwargs[k] if k in kwargs else None) 
                    for k, v in vars(self).items() if is_public(k)}  # copy just the public data values

    def equal(self, o: object, ignore: list = []) -> bool:
        '''
        Check if the specified object equals this
        o:      object to check
        ignore: fields to ignore
        '''
        eq = isinstance(o, MultiDictMixin)
        if eq:
            for k, v in vars(self).items():
                if is_public(k) and k not in ignore:
                    eq = (v == vars(o)[k])
                    if not eq:
                        break
        return eq


def __key_list(d: dict, ignore: list = []) -> set:
    return set([k for k in d.keys() if is_public(k) and k not in ignore])


def equal_dict(a: dict, b: dict, ignore: list = []) -> bool:
    '''
    Check if the specified dicts are equal
    a:      first dict
    b:      second dict
    ignore: properties to ignore
    '''
    keys_a = __key_list(a, ignore)
    keys_b = __key_list(b, ignore)
    eq = not keys_a.isdisjoint(keys_b)
    for k in keys_a:
        eq = (a[k] == b[k])
        if not eq:
            break
    return eq


def dict_disjoint(base: dict, other: dict, ignore: list = []) -> list:
    '''
    Get a list of properties in 'other' that are different from 'base'
    base:   base dict
    other:  dict to check for differences
    ignore: properties to ignore
    '''
    keys_a = __key_list(base, ignore)
    keys_b = __key_list(other, ignore)
    disjoint = [k for k in keys_a if k not in keys_b or base[k] != other[k]]
    return disjoint


def model_items(model: Union[dict, Model], ignore=[]) -> ItemsView[Any, Any]:
    '''
    Get a list of public items

    Note: will only return properties that have been set for Model

    model:  dict or Model to get items from
    ignore: properties to ignore
    '''
    if isinstance(model, dict):
        items = [(k, v) for k, v in model.items() if k not in ignore]
    else:
        items = [(k, v) for k, v in vars(model).items() if is_public(k) and k not in ignore]
    return items


def model_property_list(model: Model, ignore=[]):
    '''
    Get the property list for a model 
    model:  Model to get properties from
    ignore: properties to ignore
    '''
    return [c_attr.key for c_attr in inspect(model).mapper.column_attrs 
                                        if c_attr.key not in ignore]
