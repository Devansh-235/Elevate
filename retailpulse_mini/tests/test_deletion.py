import unittest
from unittest.mock import patch

from database.connection import DatabaseError
from database.datasets import delete_dataset


class DeletionTests(unittest.TestCase):
    def test_parameterized_atomic_delete(self):
        with patch('database.datasets.connection') as context:
            conn = context.return_value.__enter__.return_value
            cursor = conn.cursor.return_value
            cursor.fetchone.return_value = (17,)
            cursor.rowcount = 3
            self.assertEqual(delete_dataset(17), 3)
            commands = cursor.execute.call_args_list
            self.assertEqual(commands[1].args, ('DELETE FROM dataset_rows WHERE dataset_id = %s', (17,)))
            self.assertEqual(commands[2].args, ('DELETE FROM datasets WHERE dataset_id = %s', (17,)))
            conn.commit.assert_called_once()
            conn.rollback.assert_not_called()

    def test_failure_rolls_back_and_missing_dataset_is_safe(self):
        with patch('database.datasets.connection') as context:
            conn = context.return_value.__enter__.return_value
            cursor = conn.cursor.return_value
            cursor.fetchone.return_value = (17,)
            cursor.execute.side_effect = [None, None, DatabaseError('failure')]
            with self.assertRaises(DatabaseError):
                delete_dataset(17)
            conn.rollback.assert_called_once()
            conn.commit.assert_not_called()
        with patch('database.datasets.connection') as context:
            conn = context.return_value.__enter__.return_value
            conn.cursor.return_value.fetchone.return_value = None
            with self.assertRaises(DatabaseError):
                delete_dataset(17)
            self.assertEqual(conn.cursor.return_value.execute.call_count, 1)

    def test_invalid_identifier_never_connects(self):
        with patch('database.datasets.connection') as context, self.assertRaises(ValueError):
            delete_dataset('1 OR 1=1')
        context.assert_not_called()
