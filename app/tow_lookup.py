"""Tow-operator plate lookup: find a valid resident permit or guest pass for
a plate, and write every lookup to the audit log (LookupAuditLog)."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import GuestPass, LookupAuditLog, Unit, Vehicle
from app.plate_utils import normalize_plate, plate_match_key
from app.timeutil import now


@dataclass
class LookupResult:
    valid: bool
    plate_display: str
    matched_type: str | None = None  # "resident_permit" | "guest_pass"
    unit: Unit | None = None
    vehicle: Vehicle | None = None
    guest_pass: GuestPass | None = None


def lookup_plate(db: Session, raw_plate: str) -> LookupResult:
    key = plate_match_key(raw_plate)
    display = normalize_plate(raw_plate)

    vehicle = (
        db.query(Vehicle)
        .filter(Vehicle.plate_key == key, Vehicle.active.is_(True))
        .first()
    )
    if vehicle:
        result = LookupResult(
            valid=True, plate_display=display, matched_type="resident_permit",
            unit=vehicle.unit, vehicle=vehicle,
        )
    else:
        guest_pass = (
            db.query(GuestPass)
            .filter(GuestPass.plate_key == key, GuestPass.expires_at > now())
            .order_by(GuestPass.expires_at.desc())
            .first()
        )
        if guest_pass:
            result = LookupResult(
                valid=True, plate_display=display, matched_type="guest_pass",
                unit=guest_pass.unit, guest_pass=guest_pass,
            )
        else:
            result = LookupResult(valid=False, plate_display=display)

    audit = LookupAuditLog(
        plate=display,
        plate_key=key,
        result="valid" if result.valid else "invalid",
        matched_type=result.matched_type,
        matched_unit_id=result.unit.id if result.unit else None,
        looked_up_at=now(),
    )
    db.add(audit)
    db.commit()
    return result
