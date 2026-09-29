import pytest

from app.config import Config
from app.models import Unit, Vehicle
from app.permits import PermitError, active_vehicles, add_vehicle, remove_vehicle, replace_vehicle


def _fresh_unit(db) -> Unit:
    return db.query(Unit).filter(~Unit.vehicles.any()).first()


def test_add_vehicle_up_to_cap(db):
    unit = _fresh_unit(db)
    add_vehicle(db, unit, "ABC1234", "Blue", "Toyota", "Camry")
    add_vehicle(db, unit, "XYZ9876", "Red", "Honda", "Civic")
    assert len(active_vehicles(db, unit)) == Config.RESIDENT_PERMIT_CAP


def test_third_vehicle_over_cap_raises(db):
    unit = _fresh_unit(db)
    add_vehicle(db, unit, "ABC1234", "Blue", "Toyota", "Camry")
    add_vehicle(db, unit, "XYZ9876", "Red", "Honda", "Civic")
    with pytest.raises(PermitError):
        add_vehicle(db, unit, "QRS4567", "Black", "Ford", "F-150")


def test_replace_vehicle_deactivates_old_permit(db):
    unit = _fresh_unit(db)
    old = add_vehicle(db, unit, "ABC1234", "Blue", "Toyota", "Camry")
    new = replace_vehicle(db, unit, old.id, "NEW5555", "Silver", "Honda", "Accord")

    db.refresh(old)
    assert old.active is False
    assert old.deactivated_at is not None
    assert new.active is True
    assert new.plate == "NEW5555"

    # The old plate is no longer a valid permit lookup.
    still_active = (
        db.query(Vehicle).filter(Vehicle.id == old.id, Vehicle.active.is_(True)).first()
    )
    assert still_active is None


def test_remove_vehicle_deactivates(db):
    unit = _fresh_unit(db)
    vehicle = add_vehicle(db, unit, "ABC1234", "Blue", "Toyota", "Camry")
    remove_vehicle(db, unit, vehicle.id)
    db.refresh(vehicle)
    assert vehicle.active is False


def test_remove_unknown_vehicle_raises(db):
    unit = _fresh_unit(db)
    with pytest.raises(PermitError):
        remove_vehicle(db, unit, 999999)
