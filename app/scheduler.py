"""Nightly demo-data reset at 3am America/Chicago, DEMO_MODE only.

A single daemon thread, no extra dependency (no APScheduler/celery needed
for one job). Checks once a minute; resets once per calendar day the first
time local time reaches or passes 03:00.
"""

from __future__ import annotations

import logging
import threading
import time

from app.config import Config
from app.database import SessionLocal
from app.seed import reset_demo_data
from app.timeutil import now

log = logging.getLogger("hoa_parking.scheduler")

_RESET_HOUR = 3
_CHECK_INTERVAL_SECONDS = 60

_stop_event = threading.Event()


def _run_loop() -> None:
    last_reset_date = None
    while not _stop_event.is_set():
        current = now()
        if current.hour >= _RESET_HOUR and last_reset_date != current.date():
            log.info("Running nightly demo-data reset (DEMO_MODE)")
            db = SessionLocal()
            try:
                reset_demo_data(db)
            except Exception:
                log.exception("Nightly demo-data reset failed")
            finally:
                db.close()
            last_reset_date = current.date()
        _stop_event.wait(_CHECK_INTERVAL_SECONDS)


def start() -> None:
    if not Config.DEMO_MODE:
        return
    thread = threading.Thread(target=_run_loop, name="demo-reset-scheduler", daemon=True)
    thread.start()


def stop() -> None:
    _stop_event.set()
