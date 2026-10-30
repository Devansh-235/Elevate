import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from database.connection import DatabaseError, connection


class ConfigurationTests(unittest.TestCase):
    def test_file_refresh_overrides_stale_ide_values_and_handles_bom(self):
        with tempfile.TemporaryDirectory() as folder:
            env = Path(folder) / '.env'
            with patch('database.connection.ENV_FILE', env), patch.dict(os.environ, {
                'MYSQL_USER': 'old_user', 'MYSQL_PASSWORD': 'replace_with_app_password'
            }, clear=True), patch('database.connection.mysql.connector.connect') as connect:
                env.write_text('MYSQL_USER=new_user\nMYSQL_PASSWORD=first_value\n', encoding='utf-8-sig')
                with connection():
                    pass
                self.assertEqual(connect.call_args.kwargs['user'], 'new_user')
                self.assertEqual(connect.call_args.kwargs['password'], 'first_value')
                env.write_text('MYSQL_USER=new_user\nMYSQL_PASSWORD=second_value\n', encoding='utf-8')
                with connection():
                    pass
                self.assertEqual(connect.call_args.kwargs['password'], 'second_value')

    def test_error_identifies_exact_file_without_connecting(self):
        with tempfile.TemporaryDirectory() as folder:
            env = Path(folder) / '.env'
            env.write_text('MYSQL_USER=app\nMYSQL_PASSWORD=replace_with_app_password\n', encoding='utf-8')
            with patch('database.connection.ENV_FILE', env), patch.dict(os.environ, {}, clear=True), \
                    patch('database.connection.mysql.connector.connect') as connect:
                with self.assertRaises(DatabaseError) as error:
                    with connection():
                        pass
                self.assertIn(str(env), str(error.exception))
                connect.assert_not_called()
