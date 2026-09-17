import unittest
from unittest.mock import MagicMock

from worker import cancel_stale_bookings


class CancelStaleBookingsTests(unittest.TestCase):
    def test_cancels_stale_pending_bookings_and_commits(self):
        conn = MagicMock()
        cursor = conn.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = [(1,), (2,)]

        result = cancel_stale_bookings(conn, 15)

        self.assertEqual(result, [1, 2])
        cursor.execute.assert_called_once()
        sql, params = cursor.execute.call_args.args
        self.assertIn("status = 'pending'", sql)
        self.assertIn("status = 'cancelled'", sql)
        self.assertEqual(params, (15,))
        conn.commit.assert_called_once()

    def test_no_stale_bookings_returns_empty_list(self):
        conn = MagicMock()
        cursor = conn.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = []

        result = cancel_stale_bookings(conn, 15)

        self.assertEqual(result, [])
        conn.commit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
