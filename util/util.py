from datetime import datetime


def current_datetime():
    """ Current datetime to minute accuracy """
    return datetime.today().replace(second=0, microsecond=0)