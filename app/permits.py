"""Resident-permit and guest-pass business rules.

Kept separate from app/main.py so the rules (2-permit cap, replace
deactivates the old permit, guest pass caps/expiry) are easy to unit test
directly without going through HTTP.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

from app.config import Config
from app.models import GuestPass, Unit, Vehicle
from app.plate_utils import normalize_plate, plate_match_key
from app.timeutil import now


class PermitError(ValueError):
    """Raised when a rule (cap, ownership, etc.) blocks an action. The
    message is written to be shown directly to the resident."""


def active_vehicles(db: Session, unit: Unit) -> list[Vehicle]:
    return (
        db.query(Vehicle)
        .filter(Vehicle.unit_id == unit.id, Vehicle.active.is_(True))
        .order_by(Vehicle.id.asc())
        .all()
    )


def add_vehicle(db: Session, unit: Unit, plate: str, color: str, make: str, model: str) -> Vehicle:
    if len(active_vehicles(db, unit)) >= Config.RESIDENT_PERMIT_CAP:
        raise PermitError(
            f"This unit already has {Config.RESIDENT_PERMIT_CAP} car permits. "
            "Replace one instead of adding a new one."
        )
    vehicle = Vehicle(
        unit_id=unit.id,
        plate=normalize_plate(plate),
        plate_key=plate_match_key(plate),
        color=color.strip(),
        make=make.strip(),
        model=model.strip(),
        active=True,
    )
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return vehicle


def replace_vehicle(
    db: Session, unit: Unit, old_vehicle_id: int, plate: str, color: str, make: str, model: str,
) -> Vehicle:
    old = db.query(Vehicle).filter(Vehicle.id == old_vehicle_id, Vehicle.unit_id == unit.id).first()
    if not old or not old.active:
        raise PermitError("That car permit was not found for this unit.")
    old.active = False
    old.deactivated_at = now()
    new_vehicle = Vehicle(
        unit_id=unit.id,
        plate=normalize_plate(plate),
        plate_key=plate_match_key(plate),
        color=color.strip(),
        make=make.strip(),
        model=model.strip(),
        active=True,
    )
    db.add(new_vehicle)
    db.commit()
    db.refresh(new_vehicle)
    return new_vehicle


def remove_vehicle(db: Session, unit: Unit, vehicle_id: int) -> Vehicle:
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id, Vehicle.unit_id == unit.id).first()
    if not vehicle or not vehicle.active:
        raise PermitError("That car permit was not found for this unit.")
    vehicle.active = False
    vehicle.deactivated_at = now()
    db.commit()
    return vehicle


# ------------------------------------------------------------ guest passes

def active_guest_passes(db: Session, unit: Unit):
    return (
        db.query(GuestPass)
        .filter(GuestPass.unit_id == unit.id, GuestPass.expires_at > now())
        .order_by(GuestPass.expires_at.asc())
        .all()
    )


def issue_guest_pass(
    db: Session, unit: Unit, plate: str, hours: int, guest_note: str = "",
) -> GuestPass:
    if hours <= 0:
        raise PermitError("Please choose how many hours the guest will be here.")
    if hours > Config.GUEST_PASS_MAX_HOURS:
        raise PermitError(
            f"Guest passes can be at most {Config.GUEST_PASS_MAX_HOURS} hours."
        )
    if len(active_guest_passes(db, unit)) >= Config.GUEST_PASS_MAX_ACTIVE:
        raise PermitError(
            f"This unit already has {Config.GUEST_PASS_MAX_ACTIVE} active guest passes."
        )
    issued_at = now()
    guest_pass = GuestPass(
        unit_id=unit.id,
        plate=normalize_plate(plate),
        plate_key=plate_match_key(plate),
        guest_note=guest_note.strip() or None,
        issued_at=issued_at,
        expires_at=issued_at + timedelta(hours=hours),
    )
    db.add(guest_pass)
    db.commit()
    db.refresh(guest_pass)
    return guest_pass
