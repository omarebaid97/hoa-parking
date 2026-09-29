"""
Centralized configuration: all settings come from environment variables
(set via .env / docker-compose env_file), with sane defaults for local dev.

This is a DEMO app for the Bayou Landing HOA. All resident data seeded by
app/seed.py is fabricated - see README.md.
"""

import os
from pathlib import Path


def _bool_env(name: str, default: str) -> bool:
    return os.environ.get(name, default).strip().lower() not in ("false", "0", "no", "off")


class Config:
    # Data directory (bind-mounted from the host, see docker-compose.yml)
    DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
    DB_PATH = DATA_DIR / "parking.db"
    UPLOADS_DIR = DATA_DIR / "uploads"

    # Session cookie signing key. MUST be overridden in production.
    SECRET_KEY = os.environ.get("SECRET_KEY", "insecure-dev-key-change-me")

    # Demo mode: enables the "Try the demo as..." one-tap logins on the
    # landing page, the red DEMO banner, and the nightly 3am data reset.
    # Never set true on a deployment with real resident data.
    DEMO_MODE = _bool_env("DEMO_MODE", "true")

    # Tow policy toggle - see app/tow_policy.py for the decision table this
    # controls. True = orange-zone-no-permit requires Board/PMG approval
    # before towing. False = orange-zone-no-permit is a plain "may be towed".
    TOW_APPROVAL_REQUIRED = _bool_env("TOW_APPROVAL_REQUIRED", "true")

    # Guest pass limits (guest passes are a PROPOSED feature - see README
    # and every guest-pass template, which say "pending Board approval").
    GUEST_PASS_MAX_HOURS = int(os.environ.get("GUEST_PASS_MAX_HOURS", "72"))
    GUEST_PASS_MAX_ACTIVE = 2  # per unit, not currently an env override

    RESIDENT_PERMIT_CAP = 2  # per unit, non-transferable, tied to a vehicle

    TZ = os.environ.get("TZ", "America/Chicago")

    # Tow operator login. A single shared "company code" - there's no
    # per-driver account system in this demo.
    TOW_COMPANY_CODE = os.environ.get("TOW_COMPANY_CODE", "AWC-2024")
    TOW_COMPANY_NAME = "American Wrecker Co."
    TOW_COMPANY_PHONE = "713-681-9732"

    # Board/PMG admin login (mirrors wholesale-crm's single-admin pattern -
    # small trusted group, no per-user role system needed for this demo).
    ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "board")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "changeme")

    # Fixed demo PIN for every seeded resident unit (see app/seed.py). Shown
    # directly on the resident login screen when DEMO_MODE is on so a
    # reviewer can log in as any of the 67 seeded units without a lookup.
    DEMO_RESIDENT_PIN = os.environ.get("DEMO_RESIDENT_PIN", "123456")

    PMG_PHONE = "713-329-7100"
    BOARD_EMAIL = "bayoulandinghoa@gmail.com"


Config.DATA_DIR.mkdir(parents=True, exist_ok=True)
Config.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
