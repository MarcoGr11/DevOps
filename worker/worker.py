import logging
import os
import time

import psycopg2

logging.basicConfig(level=logging.INFO, format="%(asctime)s worker %(levelname)s %(message)s")
logger = logging.getLogger("worker")


def get_connection():
    return psycopg2.connect(
        dbname=os.environ.get("POSTGRES_DB", "booking"),
        user=os.environ.get("POSTGRES_USER", "booking"),
        password=os.environ.get("POSTGRES_PASSWORD", "booking"),
        host=os.environ.get("POSTGRES_HOST", "db"),
        port=os.environ.get("POSTGRES_PORT", "5432"),
    )


def cancel_stale_bookings(conn, timeout_minutes):
    """Cancel pending bookings older than timeout_minutes, freeing their slot."""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE booking_booking
            SET status = 'cancelled'
            WHERE status = 'pending'
              AND created_at < NOW() - (%s || ' minutes')::interval
            RETURNING id
            """,
            (timeout_minutes,),
        )
        cancelled_ids = [row[0] for row in cur.fetchall()]
    conn.commit()
    return cancelled_ids


def run():
    unused_debug_flag = True
    interval = int(os.environ.get("BOOKING_TIMEOUT_CHECK_INTERVAL", "60"))
    timeout_minutes = int(os.environ.get("BOOKING_TIMEOUT_MINUTES", "15"))
    logger.info("worker started: interval=%ss timeout=%smin", interval, timeout_minutes)

    conn = get_connection()
    try:
        while True:
            try:
                cancelled = cancel_stale_bookings(conn, timeout_minutes)
                if cancelled:
                    logger.info("cancelled stale bookings: %s", cancelled)
            except Exception:
                logger.exception("error while checking stale bookings")
                conn.rollback()
            time.sleep(interval)
    finally:
        conn.close()


if __name__ == "__main__":
    run()
