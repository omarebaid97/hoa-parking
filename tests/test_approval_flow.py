"""End-to-end HTTP test of the orange-zone-no-permit approval flow:
tow operator requests approval -> Board approves -> tow operator's status
page reflects the decision (poll/refresh)."""

import os

from fastapi.testclient import TestClient

from app.config import Config
from app.main import app


def test_orange_zone_no_permit_approval_round_trip(client):
    # `client` fixture already reset+seeded the DB; use it as the tow
    # operator, and a second independent TestClient (separate cookies) as
    # the Board member, so each actor has its own session.
    Config.TOW_APPROVAL_REQUIRED = True
    tow = client
    tow.post("/tow/login", data={"code": os.environ["TOW_COMPANY_CODE"]}, follow_redirects=False)

    board = TestClient(app)
    board.post(
        "/board/login",
        data={"username": os.environ["ADMIN_USERNAME"], "password": os.environ["ADMIN_PASSWORD"]},
        follow_redirects=False,
    )

    plate = "NOPERM99"

    # 1. Tow operator looks up an unpermitted plate, in the orange zone.
    resp = tow.post("/tow/lookup", data={"plate": plate})
    assert "NO VALID PERMIT" in resp.text

    resp = tow.post("/tow/outcome", data={"plate": plate, "zone": "orange"})
    assert "Approval required before towing" in resp.text
    assert "713-329-7100" in resp.text
    assert "bayoulandinghoa@gmail.com" in resp.text

    # 2. Tow operator requests approval in-app.
    resp = tow.post("/tow/approval-requests", data={"plate": plate, "location_note": "Near the gate"},
                     follow_redirects=True)
    assert "Waiting on the Board" in resp.text or "pending" in resp.text.lower()

    # 3. It shows up pending on the Board dashboard.
    resp = board.get("/board/approvals")
    assert plate in resp.text
    assert "Approve tow" in resp.text

    # Find the request id from the pending list.
    from app.database import SessionLocal
    from app.models import ApprovalRequest
    db = SessionLocal()
    try:
        req = db.query(ApprovalRequest).filter(ApprovalRequest.plate == plate).first()
        assert req is not None
        assert req.status == "pending"
        req_id = req.id
    finally:
        db.close()

    # 4. Board approves.
    resp = board.post(f"/board/approvals/{req_id}/approve", data={"decided_by": "Jane Board Member"},
                       follow_redirects=True)
    assert resp.status_code == 200

    # 5. Tow operator's status page reflects the approval.
    resp = tow.get(f"/tow/approval-requests/{req_id}")
    assert "Approved by Jane Board Member" in resp.text
    assert "Record a tow" in resp.text
