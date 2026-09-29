"""Confirms the seeded demo data contains no real resident PII.

Per the build spec: this test is the ONLY place allowed to read the real
roster CSV, and only its Name/Email columns, purely to diff against our
fabricated seed data. Nothing from the CSV is ever written anywhere.
"""

import csv
from pathlib import Path

from app.models import GuestPass, TowLogEntry, Unit, Vehicle

ROSTER_CSV = Path("/Users/omar/Downloads/hoaAssistant/docs/units_residents_emails.csv")


def _roster_names_and_emails() -> list[str]:
    if not ROSTER_CSV.exists():
        return []
    values = []
    with ROSTER_CSV.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            for col in ("Name", "Email"):
                value = (row.get(col) or "").strip()
                if len(value) > 2:  # skip trivially short tokens
                    values.append(value)
    return values


def _dump_seeded_data(db) -> str:
    parts = []
    for unit in db.query(Unit).all():
        parts.append(unit.address)
    for vehicle in db.query(Vehicle).all():
        parts += [vehicle.plate, vehicle.color, vehicle.make, vehicle.model]
    for gp in db.query(GuestPass).all():
        parts += [gp.plate, gp.guest_note or ""]
    for entry in db.query(TowLogEntry).all():
        parts += [entry.plate, entry.location_note or ""]
    return "\n".join(parts).lower()


def test_seeded_data_has_no_roster_names_or_emails(db):
    roster_values = _roster_names_and_emails()
    dump = _dump_seeded_data(db)

    leaked = [v for v in roster_values if v.lower() in dump]
    assert leaked == [], f"Seeded demo data contains roster PII: {leaked[:5]}"


def test_no_name_field_exists_on_unit_or_guest_pass():
    """Belt-and-suspenders: the schema itself never stores a resident name."""
    assert not hasattr(Unit, "name")
    assert not hasattr(Unit, "resident_name")
    assert not hasattr(GuestPass, "resident_name")
