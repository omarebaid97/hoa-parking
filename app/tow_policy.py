"""The tow decision table described in the HOA parking rules.

Zones:
  ORANGE - patrolled main stretch of Ann St connecting both gates, plus the
           spots in front of the Lofts-facing units.
  GREEN  - secondary Ann St segments directly in front of homes, not
           patrolled.
  DRIVEWAY - a resident's private driveway. Never towed.

This module only computes the *outcome label*; app/main.py wires it into
routes (e.g. creating an ApprovalRequest when needed).
"""

from app.config import Config

ZONE_ORANGE = "orange"
ZONE_GREEN = "green"
ZONE_DRIVEWAY = "driveway"
ZONES = (ZONE_ORANGE, ZONE_GREEN, ZONE_DRIVEWAY)

OUTCOME_APPROVAL_REQUIRED = "approval_required"
OUTCOME_MAY_BE_TOWED = "may_be_towed"
OUTCOME_ONLY_IF_REQUESTED = "only_if_requested"
OUTCOME_NEVER_TOW = "never_tow"


def outcome_for_no_permit(zone: str) -> str:
    """What a tow operator sees for a vehicle with NO valid permit/guest
    pass, in the given zone."""
    if zone == ZONE_DRIVEWAY:
        return OUTCOME_NEVER_TOW
    if zone == ZONE_GREEN:
        return OUTCOME_ONLY_IF_REQUESTED
    if zone == ZONE_ORANGE:
        if Config.TOW_APPROVAL_REQUIRED:
            return OUTCOME_APPROVAL_REQUIRED
        return OUTCOME_MAY_BE_TOWED
    raise ValueError(f"Unknown zone: {zone!r}")


OUTCOME_TEXT = {
    OUTCOME_APPROVAL_REQUIRED: "Approval required before towing",
    OUTCOME_MAY_BE_TOWED: "May be towed",
    OUTCOME_ONLY_IF_REQUESTED: (
        "Only tow if a resident requests it and shows photo ID or a "
        "document proving their address."
    ),
    OUTCOME_NEVER_TOW: "Never tow",
}
