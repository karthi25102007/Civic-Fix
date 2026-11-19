"""MySQL connection helpers for CivicFix.

Every function opens a short-lived connection and closes it in a ``finally``
block. This keeps request handling simple and avoids leaking connections when
an exception occurs.
"""

import os
from contextlib import contextmanager

import mysql.connector
from mysql.connector import Error as MySQLError

from config import Config

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "civicfix.sql")


class DatabaseError(Exception):
    """Raised when a query cannot be executed."""


@contextmanager
def connection(use_database: bool = True):
    conn = None
    try:
        conn = mysql.connector.connect(**Config.db_config(database=use_database))
        yield conn
    except MySQLError as exc:
        raise DatabaseError(str(exc)) from exc
    finally:
        if conn is not None and conn.is_connected():
            conn.close()


def query(sql: str, params=None, one: bool = False):
    """Run a SELECT and return a list of dict rows (or a single row/None)."""
    with connection() as conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(sql, params or ())
            return cursor.fetchone() if one else cursor.fetchall()
        finally:
            cursor.close()


def scalar(sql: str, params=None, default=None):
    row = query(sql, params, one=True)
    if not row:
        return default
    return next(iter(row.values()))


def execute(sql: str, params=None):
    """Run INSERT/UPDATE/DELETE and commit. Returns lastrowid and rowcount."""
    with connection() as conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(sql, params or ())
            conn.commit()
            return {"lastrowid": cursor.lastrowid, "rowcount": cursor.rowcount}
        except MySQLError:
            conn.rollback()
            raise
        finally:
            cursor.close()


def execute_many(sql: str, rows):
    with connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.executemany(sql, rows)
            conn.commit()
            return cursor.rowcount
        except MySQLError:
            conn.rollback()
            raise
        finally:
            cursor.close()


@contextmanager
def transaction():
    """Yield a connection with an open transaction for multi-step operations."""
    with connection() as conn:
        try:
            conn.start_transaction()
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def health_check() -> bool:
    try:
        return query("SELECT 1 AS ok", one=True)["ok"] == 1
    except (DatabaseError, KeyError, TypeError):
        return False


def initialize_database(force: bool = False) -> None:
    """Create the schema and demo data from database/civicfix.sql.

    Existing data is preserved: the script is skipped once the users table
    contains rows unless ``force`` is explicitly requested.
    """
    if not force:
        try:
            existing = scalar("SELECT COUNT(*) AS c FROM users", default=0)
            if existing:
                return
        except DatabaseError:
            pass

    with open(SCHEMA_PATH, "r", encoding="utf-8") as handle:
        script = handle.read()
    with connection(use_database=False) as conn:
        cursor = conn.cursor()
        try:
            for _ in cursor.execute(script, multi=True):
                pass
            conn.commit()
        finally:
            cursor.close()
