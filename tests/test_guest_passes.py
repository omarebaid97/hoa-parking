from datetime import timedelta

import pytest

from app.config import Config
from app.models import GuestPass, Unit
from app.permits import PermitError, active_guest_passes, issue_guest_pass
from app.timeutil import now


def _fresh_unit(db) -> Unit:
    return db.query(Unit).filter(~Unit.guest_passes.any()).first()


def test_issue_guest_pass_success(db):
    unit = _fresh_unit(db)
    gp = issue_guest_pass(db, unit, "GST1234", 24, "Weekend guest")
    assert gp.plate == "GST1234"
    assert gp.expires_at > now()


def test_hours_over_max_rejected(db):
    unit = _fresh_unit(db)
    with pytest.raises(PermitError):
        issue_guest_pass(db, unit, "GST1234", Config.GUEST_PASS_MAX_HOURS + 1)


def test_max_active_guest_passes_enforced(db):
    unit = _fresh_unit(db)
    issue_guest_pass(db, unit, "GST0001", 24)
    issue_guest_pass(db, unit, "GST0002", 24)
    assert len(active_guest_passes(db, unit)) == Config.GUEST_PASS_MAX_ACTIVE
    with pytest.raises(PermitError):
        issue_guest_pass(db, unit, "GST0003", 24)


def test_no_monthly_cap_expired_passes_do_not_block(db):
    """Expired passes issued earlier this month do not count against anything;
    only the active limit applies."""
    unit = _fresh_unit(db)
    current = now()
    for i in range(10):
        db.add(GuestPass(
            unit_id=unit.id, plate=f"OLD{i:04d}", plate_key=f"OLD{i:04d}",
            issued_at=current - timedelta(hours=2),
            expires_at=current - timedelta(hours=1),  # already expired
        ))
    db.commit()

    issue_guest_pass(db, unit, "GST0001", 12)
    issue_guest_pass(db, unit, "GST0002", 12)
    # Third is blocked by the active limit, not a monthly cap.
    with pytest.raises(PermitError, match="active"):
        issue_guest_pass(db, unit, "GST0003", 12)


def test_expired_guest_pass_not_counted_as_active(db):
    unit = _fresh_unit(db)
    current = now()
    db.add(GuestPass(
        unit_id=unit.id, plate="EXP0001", plate_key="EXP0001",
        issued_at=current - timedelta(hours=100),
        expires_at=current - timedelta(hours=1),
    ))
    db.commit()
    assert active_guest_passes(db, unit) == []
