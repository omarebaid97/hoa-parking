"""Test setup: point DATA_DIR at a throwaway temp directory *before*
anything under app/ is imported (app/config.py reads env vars at import
time), then provide a TestClient + DB session that reset to fresh seeded
demo data before every test.
"""

import os
import tempfile
from pathlib import Path

import pytest

_TMP_DATA_DIR = tempfile.mkdtemp(prefix="hoa_parking_test_")
os.environ["DATA_DIR"] = _TMP_DATA_DIR
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["DEMO_MODE"] = "true"
os.environ["TOW_APPROVAL_REQUIRED"] = "true"
os.environ["TZ"] = "America/Chicago"
os.environ["ADMIN_USERNAME"] = "board"
os.environ["ADMIN_PASSWORD"] = "test-admin-pass"
os.environ["TOW_COMPANY_CODE"] = "TEST-CODE"
os.environ["DEMO_RESIDENT_PIN"] = "123456"

from fastapi.testclient import TestClient  # noqa: E402

from app import scheduler  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import reset_demo_data  # noqa: E402

Base.metadata.create_all(bind=engine)

# The nightly 3am reset thread (app/scheduler.py) would otherwise race with
# each test's own reset_demo_data() call whenever tests happen to run at or
# after 3am local time, causing intermittent UNIQUE-constraint failures.
# Tests exercise the reset logic directly (see test_permits.py etc. via the
# `db` fixture below) - the background schedule itself isn't test surface.
scheduler.start = lambda: None


@pytest.fixture()
def db():
    """A DB session with freshly-reset, freshly-seeded demo data. Used by
    every test, whether or not it also needs an HTTP client, so unit-level
    tests (test_permits.py etc.) don't depend on FastAPI startup having run."""
    session = SessionLocal()
    reset_demo_data(session)
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def resident_client(client, db):
    from app.models import Unit
    unit = db.query(Unit).order_by(Unit.id.asc()).first()
    resp = client.post(
        "/resident/login", data={"address": unit.address, "pin": os.environ["DEMO_RESIDENT_PIN"]},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    return client, unit


@pytest.fixture()
def tow_client(client):
    resp = client.post("/tow/login", data={"code": os.environ["TOW_COMPANY_CODE"]}, follow_redirects=False)
    assert resp.status_code == 303
    return client


@pytest.fixture()
def board_client(client):
    resp = client.post(
        "/board/login",
        data={"username": os.environ["ADMIN_USERNAME"], "password": os.environ["ADMIN_PASSWORD"]},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    return client
