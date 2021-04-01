from datetime import datetime
import traceback


def label_from_valuelabel_list(valuelabel, value):
  '''
  Get the label corresponding to a value from a list of (value, label) pairs
  valuelabel: list of (value, label) pairs
  value:      value to search for
  '''
  label = None
  for vl in valuelabel:
    if vl[0] == value:
      label = vl[1]
      break
  return label


def current_datetime():
    return datetime.today().replace(second=0, microsecond=0)



__APP_CONFIG__ = None

def set_config(config):
    global __APP_CONFIG__
    __APP_CONFIG__ = config

def get_config(option):
    return __APP_CONFIG__.get(option)


def print_exc_info():
    for l in traceback.format_exc().splitlines():
      print(l)
