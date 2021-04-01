import contextlib
from http import HTTPStatus
import sys

from flask import abort
from sqlalchemy import create_engine
from sqlalchemy.sql.expression import text

from config import SQLALCHEMY_DATABASE_URI
from misc import get_config, print_exc_info


engine = None
ENGINE = False

def setup():
    '''
    Setup SQLAlchemy engine
    '''
    global engine, ENGINE
    ENGINE = get_config("USE_ENGINE")
    if ENGINE:
        engine = create_engine(SQLALCHEMY_DATABASE_URI)


def config_check():
    '''
    Verify configuaration is correct
    '''
    if not ENGINE:
        raise EnvironmentError('Application not configured for Engine')


if get_config("PRINT_SQL"):
    def stmt_text(stmt):
        stmttext = text(stmt)
        print(f' SQL> {stmttext}')
        return stmttext
else:
    def stmt_text(stmt):
        return text(stmt)


def execute(stmt: str):
    '''
    Execute an SQL statement 
    stmt:   SQL statement
    '''
    config_check()
    try:
        with engine.connect() as connection:
            result = connection.execute(stmt_text(stmt))
    except:
        print_exc_info()
        abort(HTTPStatus.SERVICE_UNAVAILABLE.value)

    return result


@contextlib.contextmanager
def transaction(connection):
    '''
    Context manager for transactions
    '''
    if not connection.in_transaction():
        with connection.begin():
            yield connection
    else:
        yield connection


def execute_transaction(stmts: list):
    '''
    Execute a transaction
    stmts:  list if SQL statements which form transaction
    '''
    config_check()
    results = []
    try:
        with engine.connect() as connection:
            with transaction(connection) as trans:  # open a transaction
                for stmt in stmts:
                    results.append(connection.execute(stmt_text(stmt)))
    except:
        print_exc_info()
        abort(HTTPStatus.SERVICE_UNAVAILABLE.value)

    return results
