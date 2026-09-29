# Bayou Landing HOA - Digital Parking Permits (DEMO)

A **demo** web app for a digital parking-permit system for the Bayou
Landing HOA (a Houston townhome community). It is built to show the Board
what a digital system could look like: resident car permits, a proposed
guest-pass feature, a tow-operator plate lookup with a Board/PMG approval
flow, and Board/PMG admin views (units, tow log, lookup audit log).

**This is a demo with 100% fabricated data.** No real resident names,
emails, vehicles, or plates were used anywhere - see "Privacy" below.
Every page also shows a persistent red banner: "DEMO - sample data only,
not the official system."

Stack: FastAPI + Uvicorn, SQLite (via SQLAlchemy), server-rendered Jinja2,
session-cookie auth. No React/npm build, no CDNs or external runtime
dependencies (the Leaflet map library and its assets are vendored/copied
into `app/static/tow-map/`, not loaded from a CDN).

**Deployment status: NOT deployed.** This was built and tested locally
only, per the task that created it. Deploying it to the homelab (its own
`/home/omar/hoa-parking/` directory, internal-only compose service with no
public `ports:`, reached later via a Cloudflare tunnel ingress rule) is a
separate, later step - do not assume it is live anywhere yet.

## Roles

1. **Resident** - logs in with their unit's street address + a 6-digit PIN.
   Can view/add/replace/remove up to 2 car permits (non-transferable, tied
   to a specific vehicle - replacing a car deactivates the old permit), and
   preview the **proposed** guest-pass feature. Also has a plain-English
   parking-rules page with the zone map.
2. **Tow operator** - logs in with a single shared company code. Looks up a
   plate (normalized: uppercase, spaces/dashes stripped, O/0 and I/1 treated
   as the same character); sees a big green "VALID PERMIT - DO NOT TOW" or
   red "NO VALID PERMIT" screen. For an unpermitted car, picks a zone
   (orange/green/driveway) and gets the matching outcome - including, for
   the orange zone when `TOW_APPROVAL_REQUIRED=true`, a "request approval in
   app" flow that the Board decides on, with the tow screen polling for the
   decision. Records completed tows (with an optional photo).
3. **Board / PMG** - logs in with a single shared admin login. Sees all 67
   units with permit/guest-pass counts and search, can add/remove permits on
   a resident's behalf, approves/denies pending tow requests, and can browse
   the tow log and the full plate-lookup audit log. Also has a "Reset demo
   data" button.

The landing page (`/`) has three big buttons for the roles above, plus (in
`DEMO_MODE`) one-tap "Try the demo as..." links that log straight in.

## Zones and tow policy

- **Orange zone**: the patrolled main stretch of Ann St connecting both
  gates, plus the spots in front of the Lofts-facing units. A car here with
  no valid permit either "may be towed" or needs Board/PMG approval first,
  depending on `TOW_APPROVAL_REQUIRED` (see below).
- **Green zone**: the Ann St stretches directly in front of homes, not
  patrolled. Only towed if a resident requests it and shows photo ID or a
  document proving their address.
- **Driveways**: never towed, no exceptions.
- Tow company: American Wrecker Co., 713-681-9732 (shown in the app; not a
  login).
- Approval contacts (orange zone, no permit, `TOW_APPROVAL_REQUIRED=true`):
  PMG 713-329-7100, Board email bayoulandinghoa@gmail.com.

## Guest passes - PROPOSED feature

Guest passes are **not official HOA policy**. Every screen that shows them
is labeled "Proposed - pending Board approval." They exist in this demo to
give the Board something concrete to react to: a resident could issue a
guest a plate pass for up to `GUEST_PASS_MAX_HOURS` (default 72), max 2 active at
once per unit, auto-expiring, no monthly cap.

## Environment variables (`.env`, see `.env.example`)

| Variable | Default | Meaning |
|---|---|---|
| `SECRET_KEY` | *(none - set it)* | Signs the session cookie. |
| `DEMO_MODE` | `true` | Enables the one-tap demo logins, the red DEMO banner, and the nightly 3am (`TZ`) data reset. Never `true` with real resident data. |
| `TOW_APPROVAL_REQUIRED` | `true` | Orange-zone-no-permit needs Board/PMG approval before towing (`true`) vs. a plain "May be towed" (`false`). |
| `GUEST_PASS_MAX_HOURS` | `72` | Max hours per guest pass. |
| `TZ` | `America/Chicago` | Used for the nightly reset and all displayed timestamps. |
| `TOW_COMPANY_CODE` | `AWC-2024` | Shared tow-operator login code. |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | `board` / `changeme` | Shared Board/PMG login. |
| `DEMO_RESIDENT_PIN` | `123456` | PIN for every seeded demo unit (shown on the resident login screen in demo mode). |

## Demo data & reset

67 units are seeded (see "Deviations from spec" below for why 67, not 66).
About 70% get 1-2 fabricated vehicles, a handful get active (proposed)
guest passes, a few historical tow-log entries exist, and there's one
pending tow-approval request waiting on the Board dashboard.

- **Board "Reset demo data" button** (`/board`, `POST /board/reset-demo-data`):
  wipes every table and reseeds fresh demo data. Disabled (403) outside
  `DEMO_MODE`.
- **Nightly automatic reset**: a background thread (`app/scheduler.py`, no
  extra dependency) checks once a minute and resets once per day the first
  time local time (`TZ`) reaches 3am, only while `DEMO_MODE=true`.
- Seeding is reproducible: `app/seed.py` uses a fixed random seed, so a
  reset always produces the same-shaped (though re-numbered) demo dataset.

## How to run locally

Docker was not available on the Mac this was built on (`docker` was not
on `PATH`), so this was built and verified with a plain Python venv +
Uvicorn instead of a container. `docker compose config` was still checked
by hand-parsing the YAML (see "Deviations from spec"). If Docker is
available on your machine, the compose path below should work as-is.

### Option A - Docker Compose (once Docker is available)

```
cp .env.example .env      # edit as needed
docker compose config     # validate
docker compose up -d --build
curl http://localhost:8000/healthz   # from inside the compose network / after adding a port for local testing
```

Note `docker-compose.yml` intentionally has **no `ports:` stanza** (see the
file's own comment) - it's designed to be reached over the Docker network
only, e.g. by a Cloudflare tunnel container joining this network at
deployment time (a later, separate step). For a quick local look via a
browser, temporarily add a `ports: ["8000:8000"]` line, or just use Option B.

### Option B - Python venv + Uvicorn (what was actually used here)

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
export $(grep -v '^#' .env | xargs)   # or use a tool like `direnv`/`honcho`
DATA_DIR=./data uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Then open `http://127.0.0.1:8000/`.

## Demo login codes / PINs (from `.env.example` defaults)

- **Resident**: pick any of the 67 addresses, PIN `123456`.
- **Tow operator**: company code `AWC-2024`.
- **Board / PMG**: username `board`, password `changeme`.

All three are also shown directly on their respective login screens
whenever `DEMO_MODE=true`, and the landing page's "Try the demo as..."
links log straight in without typing anything.

## Tests

```
source .venv/bin/activate
python -m pytest tests/ -q
```

30 tests, all passing locally (Python 3.9 venv - see "Deviations from
spec"). Covers: plate normalization/matching (including O/0, I/1 folding),
the 2-permit cap, vehicle replacement deactivating the old permit, guest
pass active/monthly caps and expiry, tow outcomes for all 3 zones under
both `TOW_APPROVAL_REQUIRED` settings, the full approval-request ->
Board-decision -> tow-operator-poll round trip over real HTTP, the lookup
audit log being written on every plate check, `/docs`/`/redoc`/`/openapi.json`
returning 404, the `X-Robots-Tag: noindex` header, and a no-PII check that
reads only the *Name*/*Email* columns of the real roster CSV at test time
(never anywhere else) to assert none of those strings appear in seeded data.

## Project layout

```
hoa-parking/
  app/
    main.py           FastAPI app & all routes (resident/tow/board)
    config.py          env var loading
    database.py         SQLAlchemy engine/session
    models.py            Unit, Vehicle, GuestPass, ApprovalRequest, TowLogEntry, LookupAuditLog
    auth.py                session auth for the 3 roles (PIN / company code / admin login)
    plate_utils.py          normalize_plate() / plate_match_key() (O/0, I/1 folding)
    tow_policy.py             the zone/no-permit -> outcome decision table
    tow_lookup.py              plate lookup + audit-log write
    permits.py                  vehicle add/replace/remove + guest-pass issue (all the caps live here)
    addresses.py                 the 67 seeded unit addresses (see below)
    seed.py                       creates tables + seeds/resets demo data
    scheduler.py                   nightly 3am reset thread (DEMO_MODE only)
    security.py                     security-headers middleware (noindex, CSP, etc.)
    timeutil.py                      single "now()" - naive local time in TZ
    templates/                        Jinja2 templates, one folder per role
    static/
      style.css                       big-text/high-contrast accessible styling
      tow-map/                          COPIED (not linked) from hoaAssistant's public
                                         site assets: vendor/leaflet/, tow-map.js/css,
                                         tow-zones.geojson, img/ (paths adapted to /static)
  data/               SQLite DB + uploads/ live here (gitignored)
  tests/              pytest suite (see above)
  Dockerfile
  docker-compose.yml
  requirements.txt
  .env.example
```

## Privacy

No file under `/Users/omar/Downloads/hoaAssistant/docs/units_residents_emails.csv`
was read except by `tests/test_no_pii.py`, and only its `Name`/`Email`
columns, purely to diff against seeded data (nothing from it is ever
written anywhere). The app's schema has **no resident-name field at all**
on `Unit` or `GuestPass` - residents are identified only by unit address +
PIN, and every other screen (Board units table, tow log, audit log)
references units by address only. All plates/vehicle colors/makes/models
are fabricated by `app/seed.py` using a fixed random seed.

## Deviations from spec

- **Unit count is 67, not 66.** The spec's literal, explicitly-enumerated
  address list (61 on Ann St + 6 on Runnels St) totals 67 addresses, but
  the spec also said "(Verify the count = 66)". Counted twice by script
  (see `app/addresses.py`) and consistently got 67 from the literal list.
  Went with the literal list rather than guessing which single address to
  drop to force 66 - flagging this rather than silently reconciling it.
- **No resident-name field anywhere in the schema.** The spec's privacy
  section illustrated fabricated names like "Demo Resident 2214" as an
  example of what a fake name *could* look like, but this app's login is
  address + PIN (no name needed for auth), and no other screen needed a
  resident name either. Rather than add a name field just to fill it with
  fabricated values, the schema simply has none - stricter than required,
  and simpler to verify has no PII.
- **Docker was not available on this Mac** (`docker`/`docker compose` not on
  `PATH`), so per the task's fallback instruction, the app was built,
  tested, and manually smoke-tested (every role's full flow, including the
  approval round-trip, photo upload, and demo reset) with a Python 3.9 venv
  + Uvicorn instead of a container. `docker compose config`-equivalent
  validation was done by parsing `docker-compose.yml` with PyYAML instead of
  the Docker CLI. The `Dockerfile`/`docker-compose.yml` mirror
  `wholesale-crm`'s proven pattern closely enough that they should build
  cleanly once Docker is available, but that step itself is unverified here.
- **Local test venv uses Python 3.9** (the newest available on this Mac
  without Docker), not 3.11 like the Dockerfile's base image. One resulting
  compatibility fix: `UploadFile | None` (PEP 604 syntax) doesn't evaluate
  under FastAPI/Pydantic on Python 3.9, so `app/main.py` uses
  `typing.Optional[UploadFile]` there instead - this is also valid on 3.11,
  so it doesn't need to change again for the eventual container build.
