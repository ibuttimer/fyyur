from flask import Config


__APP_CONFIG__: Config = None


def set_config(config: Config):
    """
    Set config for application
    :param config:
    :return:
    """
    global __APP_CONFIG__
    __APP_CONFIG__ = config


def get_config(option: str):
    """
    Get config option
    :param option: name of option
    :return:
    """
    return __APP_CONFIG__.get(option)


