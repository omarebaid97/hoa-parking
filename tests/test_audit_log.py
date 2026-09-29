from app.models import LookupAuditLog, Vehicle
from app.tow_lookup import lookup_plate


def test_valid_lookup_written_to_audit_log(db):
    vehicle = db.query(Vehicle).filter(Vehicle.active.is_(True)).first()
    assert vehicle is not None, "seed data should include at least one active vehicle"

    before = db.query(LookupAuditLog).count()
    result = lookup_plate(db, vehicle.plate)
    assert result.valid is True

    after = db.query(LookupAuditLog).count()
    assert after == before + 1
    latest = db.query(LookupAuditLog).order_by(LookupAuditLog.id.desc()).first()
    assert latest.result == "valid"
    assert latest.matched_type == "resident_permit"
    assert latest.matched_unit_id == vehicle.unit_id


def test_invalid_lookup_written_to_audit_log(db):
    before = db.query(LookupAuditLog).count()
    result = lookup_plate(db, "NOPE9999")
    assert result.valid is False

    after = db.query(LookupAuditLog).count()
    assert after == before + 1
    latest = db.query(LookupAuditLog).order_by(LookupAuditLog.id.desc()).first()
    assert latest.result == "invalid"
    assert latest.matched_unit_id is None


def test_lookup_matches_via_ambiguous_character_folding(db):
    vehicle = db.query(Vehicle).filter(Vehicle.active.is_(True)).first()
    swapped = vehicle.plate.replace("0", "O").replace("1", "I")
    if swapped == vehicle.plate:
        # Plate had no 0/1 characters to swap - nothing to test here.
        return
    result = lookup_plate(db, swapped)
    assert result.valid is True
    assert result.unit.id == vehicle.unit_id
