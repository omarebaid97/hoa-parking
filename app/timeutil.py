"""Single source of truth for "now" in this app: naive datetimes in the
HOA's local timezone (Config.TZ, America/Chicago). SQLite has no real
datetime type, so we keep everything naive-local rather than mixing naive
UTC and aware-local, which is what the nightly 3am reset (app/scheduler.py)
also keys off of."""

from datetime import datetime
from zoneinfo import ZoneInfo

from app.config import Config

_TZ = ZoneInfo(Config.TZ)


def now() -> datetime:
    return datetime.now(_TZ).replace(tzinfo=None)
