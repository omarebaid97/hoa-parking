"""License-plate normalization and matching.

Two forms of every plate are kept:
  - display form: uppercase, spaces/dashes stripped, otherwise as typed.
    This is what's shown on screen so it still looks like a real plate.
  - match key: display form with O<->0 and I<->1 folded together, used
    only for lookups/comparisons. Tow operators typing on a phone in a
    parking lot regularly can't tell an O from a 0 at a glance, so a plate
    is considered a match if it's equal under this folding.
"""

import re

_STRIP_RE = re.compile(r"[\s\-]+")
_NON_ALNUM_RE = re.compile(r"[^A-Z0-9]")


def normalize_plate(raw: str) -> str:
    """Uppercase, strip whitespace/dashes and any other punctuation."""
    if not raw:
        return ""
    s = raw.upper()
    s = _STRIP_RE.sub("", s)
    s = _NON_ALNUM_RE.sub("", s)
    return s


def plate_match_key(raw: str) -> str:
    """Normalize, then fold O<->0 and I<->1 so visually-ambiguous characters
    compare equal."""
    s = normalize_plate(raw)
    s = s.replace("O", "0").replace("I", "1")
    return s
