"""Short-lived connections; no credentials in source code or Streamlit caches."""
import os
from contextlib import contextmanager
from pathlib import Path

import mysql.connector
from dotenv import dotenv_values, load_dotenv

ENV_FILE = Path(__file__).resolve().parents[1] / '.env'
load_dotenv(ENV_FILE, encoding='utf-8-sig')


class DatabaseError(RuntimeError):
    pass


@contextmanager
def connection(readonly=False):
    # Imported modules survive Streamlit reruns. Read the local file each time;
    # explicit file values take priority over stale IDE environment variables.
    settings = dict(os.environ)
    if ENV_FILE.is_file():
        settings.update(dotenv_values(ENV_FILE, encoding='utf-8-sig', interpolate=False))
    prefix = 'MYSQL_READONLY' if readonly else 'MYSQL'
    user, password = settings.get(f'{prefix}_USER'), settings.get(f'{prefix}_PASSWORD')
    if not user or not password or password.startswith('replace_'):
        raise DatabaseError(f'Set {prefix}_USER and {prefix}_PASSWORD in this file: {ENV_FILE}. '
                            'Use one KEY=value setting per line, save the file, and retry.')
    if readonly and user == settings.get('MYSQL_USER'):
        raise DatabaseError('The chatbot requires a separate SELECT-only database user.')
    conn = None
    try:
        conn = mysql.connector.connect(
            host=settings.get('MYSQL_HOST', '127.0.0.1'),
            port=int(settings.get('MYSQL_PORT', '3306')),
            database=settings.get('MYSQL_DATABASE', 'retailpulse_mini'),
            user=user, password=password, connection_timeout=8,
            charset='utf8mb4', autocommit=False, allow_local_infile=False,
        )
        yield conn
    except mysql.connector.Error as exc:
        if conn:
            conn.rollback()
        raise DatabaseError(f'MySQL operation failed (code {exc.errno}). Check the schema, '
                            'account permissions and server connection in Workbench.') from exc
    except ValueError as exc:
        raise DatabaseError('Check your MySQL port and connection configuration.') from exc
    finally:
        if conn and conn.is_connected():
            conn.close()
