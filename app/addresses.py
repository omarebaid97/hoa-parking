"""The 67 seeded unit addresses for the Bayou Landing HOA demo.

NOTE ON COUNT: the build spec for this demo asked to "verify the count =
66", but the explicit, literal address list it also provided (reproduced
below, unchanged) enumerates 67 addresses (61 on Ann St + 6 on Runnels St).
We went with the literal list rather than dropping an address to force a
round number - see README.md "Deviations from spec" for detail.

All 67 are real street-address *numbers* on Ann St / Runnels St per the
task spec (fine to use - no PII). No resident names, emails, or vehicle
data from any real roster were read or used anywhere in this app; every
resident name/vehicle/plate below is fabricated in app/seed.py.
"""

_ANN_ST_RANGE_1 = [n for n in range(2201, 2226) if n not in (2223, 2226)]
_ANN_ST_RANGE_2 = [
    2227, 2228, 2229, 2230, 2231, 2232, 2233, 2234, 2235, 2236,
    2238, 2240, 2242, 2244, 2246, 2248, 2250,
]
_ANN_ST_RANGE_3 = [
    2301, 2303, 2305, 2307, 2309, 2311, 2313, 2315, 2319, 2323,
    2325, 2329, 2331, 2333, 2335, 2337, 2339, 2341, 2343, 2345,
]
_RUNNELS_ST = [2211, 2215, 2219, 2223, 2227, 2231]

ADDRESSES = (
    [f"{n} Ann St" for n in _ANN_ST_RANGE_1 + _ANN_ST_RANGE_2 + _ANN_ST_RANGE_3]
    + [f"{n} Runnels St" for n in _RUNNELS_ST]
)
