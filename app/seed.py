"""Database init + demo data seeding.

PRIVACY: this module fabricates every plate/vehicle it creates. It never
reads any real resident roster. There is no "resident name" field anywhere
in this app's schema (see app/models.py) - residents are identified only by
unit address + PIN, so there was nothing to fabricate a fake name *for*.
Board/tow screens reference units by address only.
"""

from __future__ import annotations

import random
from datetime import timedelta

from sqlalchemy.orm import Session

from app.addresses import ADDRESSES
from app.auth import hash_pin
from app.config import Config
from app.database import Base, SessionLocal, engine
from app.models import ApprovalRequest, GuestPass, LookupAuditLog, TowLogEntry, Unit, Vehicle
from app.plate_utils import normalize_plate, plate_match_key
from app.timeutil import now

_SEED = 20260101  # fixed so demo data (and its tests) are reproducible

_COLORS = ["White", "Black", "Silver", "Gray", "Blue", "Red", "Dark Green", "Tan"]
_MAKES_MODELS = [
    ("Toyota", "Camry"), ("Toyota", "RAV4"), ("Honda", "Civic"), ("Honda", "CR-V"),
    ("Ford", "F-150"), ("Ford", "Escape"), ("Chevrolet", "Silverado"), ("Chevrolet", "Malibu"),
    ("Nissan", "Altima"), ("Nissan", "Rogue"), ("Hyundai", "Elantra"), ("Kia", "Soul"),
    ("Jeep", "Grand Cherokee"), ("Subaru", "Outback"), ("Mazda", "CX-5"), ("GMC", "Sierra"),
]


def _fabricate_plate(rng: random.Random) -> str:
    letters = "".join(rng.choice("ABCDEFGHJKLMNPQRSTUVWXYZ") for _ in range(3))  # skip O/I to
    digits = "".join(rng.choice("0123456789") for _ in range(4))                  # avoid ambiguity
    return f"{letters}{digits}"


def init_db() -> None:
    """Create tables if they don't exist, and seed demo data on first boot
    (only when the units table is empty)."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(Unit).first() is None:
            seed_demo_data(db)
    finally:
        db.close()


def reset_demo_data(db: Session) -> None:
    """Wipe every table and reseed fresh demo data. Used by the Board's
    "Reset demo data" button and the nightly 3am reset (DEMO_MODE only)."""
    for model in (LookupAuditLog, TowLogEntry, ApprovalRequest, GuestPass, Vehicle, Unit):
        db.query(model).delete()
    db.commit()
    seed_demo_data(db)


def seed_demo_data(db: Session) -> None:
    rng = random.Random(_SEED)
    pin_hash = hash_pin(Config.DEMO_RESIDENT_PIN)

    units: list[Unit] = []
    for address in ADDRESSES:
        unit = Unit(address=address, pin_hash=pin_hash)
        db.add(unit)
        units.append(unit)
    db.commit()
    for unit in units:
        db.refresh(unit)

    # ~70% of units get 1-2 vehicles.
    seeded_vehicle_units = []
    for unit in units:
        if rng.random() >= 0.70:
            continue
        num_vehicles = 1 if rng.random() < 0.65 else 2
        for _ in range(num_vehicles):
            make, model = rng.choice(_MAKES_MODELS)
            plate = _fabricate_plate(rng)
            vehicle = Vehicle(
                unit_id=unit.id,
                plate=normalize_plate(plate),
                plate_key=plate_match_key(plate),
                color=rng.choice(_COLORS),
                make=make,
                model=model,
                active=True,
            )
            db.add(vehicle)
        seeded_vehicle_units.append(unit)
    db.commit()

    # A few active guest passes (proposed feature) on units that already
    # have a resident vehicle, so the guest-pass screen has something to show.
    current = now()
    for unit in rng.sample(seeded_vehicle_units, k=min(5, len(seeded_vehicle_units))):
        plate = _fabricate_plate(rng)
        hours = rng.choice([12, 24, 48, 72])
        db.add(GuestPass(
            unit_id=unit.id,
            plate=normalize_plate(plate),
            plate_key=plate_match_key(plate),
            guest_note=rng.choice(["Family visiting", "Contractor", "Weekend guest", None]),
            issued_at=current - timedelta(hours=rng.randint(0, 5)),
            expires_at=current + timedelta(hours=hours),
        ))
    db.commit()

    # A handful of historical tow log entries.
    tow_zones = ["orange", "orange", "green"]
    for i, zone in enumerate(tow_zones):
        plate = _fabricate_plate(rng)
        db.add(TowLogEntry(
            plate=normalize_plate(plate),
            plate_key=plate_match_key(plate),
            zone=zone,
            location_note="Main stretch of Ann St near the north gate" if zone == "orange"
                           else "In front of a home on Ann St",
            approval_reference="Board approved by demo data" if zone == "orange" else None,
            towed_at=current - timedelta(days=30 - i * 7),
        ))
    db.commit()

    # One pending tow-approval request, waiting on the Board dashboard.
    pending_plate = _fabricate_plate(rng)
    db.add(ApprovalRequest(
        plate=normalize_plate(pending_plate),
        plate_key=plate_match_key(pending_plate),
        zone="orange",
        location_note="Blocking the fire lane near the Lofts-facing units",
        status="pending",
        requested_at=current - timedelta(hours=1),
    ))
    db.commit()
