from app.config import Config
from app.tow_policy import (
    OUTCOME_APPROVAL_REQUIRED,
    OUTCOME_MAY_BE_TOWED,
    OUTCOME_NEVER_TOW,
    OUTCOME_ONLY_IF_REQUESTED,
    outcome_for_no_permit,
)


def test_driveway_never_towed_regardless_of_approval_setting():
    Config.TOW_APPROVAL_REQUIRED = True
    assert outcome_for_no_permit("driveway") == OUTCOME_NEVER_TOW
    Config.TOW_APPROVAL_REQUIRED = False
    assert outcome_for_no_permit("driveway") == OUTCOME_NEVER_TOW


def test_green_zone_only_if_requested_regardless_of_approval_setting():
    Config.TOW_APPROVAL_REQUIRED = True
    assert outcome_for_no_permit("green") == OUTCOME_ONLY_IF_REQUESTED
    Config.TOW_APPROVAL_REQUIRED = False
    assert outcome_for_no_permit("green") == OUTCOME_ONLY_IF_REQUESTED


def test_orange_zone_requires_approval_when_configured():
    Config.TOW_APPROVAL_REQUIRED = True
    try:
        assert outcome_for_no_permit("orange") == OUTCOME_APPROVAL_REQUIRED
    finally:
        Config.TOW_APPROVAL_REQUIRED = True  # restore default for other tests


def test_orange_zone_may_be_towed_when_approval_not_required():
    Config.TOW_APPROVAL_REQUIRED = False
    try:
        assert outcome_for_no_permit("orange") == OUTCOME_MAY_BE_TOWED
    finally:
        Config.TOW_APPROVAL_REQUIRED = True  # restore default for other tests
