import traceback
from enum import Enum


class EntityResult(Enum):
    DICT = 1
    MULTIDICT = 2
    MODEL = 3


def print_exc_info():
    """ Print exception info """
    for line in traceback.format_exc().splitlines():
        print(line)

