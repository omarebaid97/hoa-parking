"""SQLAlchemy models for the Bayou Landing HOA parking-permit demo."""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class Unit(Base):
    """One of the 67 seeded townhome addresses. See app/seed.py."""

    __tablename__ = "units"

    id = Column(Integer, primary_key=True)
    address = Column(String, unique=True, nullable=False, index=True)
    pin_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    vehicles = relationship(
        "Vehicle", back_populates="unit", cascade="all, delete-orphan",
        order_by="Vehicle.id",
    )
    guest_passes = relationship(
        "GuestPass", back_populates="unit", cascade="all, delete-orphan",
        order_by="GuestPass.issued_at.desc()",
    )


class Vehicle(Base):
    """A resident permit: tied to one unit + one specific vehicle,
    non-transferable. Up to Config.RESIDENT_PERMIT_CAP active per unit.
    Replacing a vehicle deactivates the old permit rather than deleting it,
    so history survives for the Board's records."""

    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True)
    unit_id = Column(Integer, ForeignKey("units.id"), nullable=False, index=True)
    plate = Column(String, nullable=False)              # display form, e.g. "ABC1234"
    plate_key = Column(String, nullable=False, index=True)  # match key, O/I folded to 0/1
    color = Column(String, nullable=False)
    make = Column(String, nullable=False)
    model = Column(String, nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    deactivated_at = Column(DateTime, nullable=True)

    unit = relationship("Unit", back_populates="vehicles")


class GuestPass(Base):
    """PROPOSED feature, pending Board approval - see every template that
    surfaces this. Auto-expires; not a physical permit."""

    __tablename__ = "guest_passes"

    id = Column(Integer, primary_key=True)
    unit_id = Column(Integer, ForeignKey("units.id"), nullable=False, index=True)
    plate = Column(String, nullable=False)
    plate_key = Column(String, nullable=False, index=True)
    guest_note = Column(String, nullable=True)  # e.g. "Mom visiting" - optional, resident's own words
    issued_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)

    unit = relationship("Unit", back_populates="guest_passes")


class ApprovalRequest(Base):
    """A tow operator's request to tow an orange-zone vehicle with no valid
    permit, created when TOW_APPROVAL_REQUIRED=true. The Board/PMG approves
    or denies it; the tow screen polls this row for the decision."""

    __tablename__ = "approval_requests"

    id = Column(Integer, primary_key=True)
    plate = Column(String, nullable=False)
    plate_key = Column(String, nullable=False, index=True)
    zone = Column(String, nullable=False)  # always "orange" today, kept generic
    location_note = Column(String, nullable=True)
    status = Column(String, default="pending", nullable=False)  # pending|approved|denied
    requested_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    decided_at = Column(DateTime, nullable=True)
    decided_by = Column(String, nullable=True)  # free-text name typed by the Board member


class TowLogEntry(Base):
    """A completed tow, recorded by the tow operator. Visible to Board/PMG."""

    __tablename__ = "tow_log"

    id = Column(Integer, primary_key=True)
    plate = Column(String, nullable=False)
    plate_key = Column(String, nullable=False, index=True)
    zone = Column(String, nullable=False)  # orange|green|driveway
    location_note = Column(String, nullable=True)
    photo_path = Column(String, nullable=True)  # relative path under uploads/
    approval_reference = Column(String, nullable=True)  # ApprovalRequest id, or manual note
    towed_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class LookupAuditLog(Base):
    """Every plate lookup a tow operator performs, valid or not."""

    __tablename__ = "lookup_audit_log"

    id = Column(Integer, primary_key=True)
    plate = Column(String, nullable=False)
    plate_key = Column(String, nullable=False, index=True)
    result = Column(String, nullable=False)  # valid|invalid
    matched_type = Column(String, nullable=True)  # resident_permit|guest_pass
    matched_unit_id = Column(Integer, ForeignKey("units.id"), nullable=True)
    looked_up_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    matched_unit = relationship("Unit")
