"""
Bayou Landing HOA - Digital Parking Permits (DEMO app, fabricated data only).

Routes:
  GET  /healthz                          unauthenticated liveness check
  GET  /                                  landing page (3 role buttons + demo logins)
  GET  /demo/resident|tow|board           DEMO_MODE one-tap logins
  GET  /help/print                        printable how-to sheet

  Resident  (unit address + PIN):
    GET/POST /resident/login, POST /resident/logout
    GET      /resident                              my cars
    GET/POST /resident/vehicles/new                  add a car
    GET/POST /resident/vehicles/{id}/replace         replace a car
    GET/POST /resident/vehicles/{id}/remove          remove a car
    GET/POST /resident/guest-pass                    guest pass (proposed)
    GET      /resident/rules                         plain-English rules + zone map

  Tow operator (shared company code):
    GET/POST /tow/login, POST /tow/logout
    GET/POST /tow, /tow/lookup                       plate lookup
    POST     /tow/outcome                            zone -> outcome
    POST     /tow/approval-requests                  create approval request
    GET      /tow/approval-requests/{id}              poll decision
    GET/POST /tow/record-tow                          record a completed tow

  Board / PMG (shared admin login):
    GET/POST /board/login, POST /board/logout
    GET      /board                                  dashboard
    GET      /board/units, /board/units/{id}          units + on-behalf-of edits
    POST     /board/units/{id}/vehicles/new|{vid}/remove
    GET      /board/approvals, POST .../approve|deny
    GET      /board/tow-log, /board/audit-log
    POST     /board/reset-demo-data                   DEMO_MODE only
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from app import scheduler
from app.addresses import ADDRESSES
from app.auth import (
    authenticate_board,
    get_current_board_user,
    is_tow_operator,
    require_board,
    require_resident,
    require_tow_operator,
    verify_pin,
)
from app.config import Config
from app.database import get_db
from app.models import ApprovalRequest, LookupAuditLog, TowLogEntry, Unit, Vehicle
from app.permits import (
    PermitError,
    active_guest_passes,
    active_vehicles,
    add_vehicle,
    issue_guest_pass,
    remove_vehicle,
    replace_vehicle,
)
from app.plate_utils import normalize_plate, plate_match_key
from app.security import SecurityHeadersMiddleware
from app.seed import init_db, reset_demo_data
from app.timeutil import now
from app.tow_lookup import lookup_plate
from app.tow_policy import (
    OUTCOME_MAY_BE_TOWED,
    OUTCOME_NEVER_TOW,
    OUTCOME_ONLY_IF_REQUESTED,
    outcome_for_no_permit,
)

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.globals["demo_mode"] = Config.DEMO_MODE

_ALLOWED_PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

app = FastAPI(
    title="Bayou Landing HOA - Parking Permits (Demo)",
    docs_url=None, redoc_url=None, openapi_url=None,
)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(SessionMiddleware, secret_key=Config.SECRET_KEY, session_cookie="hoa_parking_session")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.mount("/uploads", StaticFiles(directory=str(Config.UPLOADS_DIR)), name="uploads")


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    scheduler.start()


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


# ------------------------------------------------------------- landing ----

@app.get("/", response_class=HTMLResponse)
def landing(request: Request, db: Session = Depends(get_db)):
    demo_unit = db.query(Unit).order_by(Unit.id.asc()).first()
    return templates.TemplateResponse("landing.html", {
        "request": request,
        "demo_unit_address": demo_unit.address if demo_unit else "",
    })


@app.get("/help/print", response_class=HTMLResponse)
def help_print(request: Request):
    return templates.TemplateResponse("help_print.html", {"request": request})


# --------------------------------------------------------- demo logins ----
# One-tap logins shown only when DEMO_MODE=true (also hidden behind a 404
# if someone hits these URLs directly on a non-demo deployment).

def _require_demo_mode() -> None:
    if not Config.DEMO_MODE:
        raise HTTPException(status_code=404)


@app.get("/demo/resident")
def demo_resident_login(request: Request, db: Session = Depends(get_db)):
    _require_demo_mode()
    # Prefer a unit that already has a vehicle seeded, so the demo has
    # something to show right away.
    unit = (
        db.query(Unit).join(Vehicle).filter(Vehicle.active.is_(True)).first()
        or db.query(Unit).order_by(Unit.id.asc()).first()
    )
    if not unit:
        raise HTTPException(status_code=404, detail="No demo units seeded yet")
    request.session["resident_unit_id"] = unit.id
    return RedirectResponse("/resident", status_code=303)


@app.get("/demo/tow")
def demo_tow_login(request: Request):
    _require_demo_mode()
    request.session["tow_operator"] = True
    return RedirectResponse("/tow", status_code=303)


@app.get("/demo/board")
def demo_board_login(request: Request):
    _require_demo_mode()
    request.session["board_user"] = Config.ADMIN_USERNAME
    return RedirectResponse("/board", status_code=303)


# =============================================================== resident =

@app.get("/resident/login", response_class=HTMLResponse)
def resident_login_form(request: Request, db: Session = Depends(get_db)):
    if request.session.get("resident_unit_id"):
        return RedirectResponse("/resident", status_code=303)
    return templates.TemplateResponse("resident/login.html", {
        "request": request, "addresses": ADDRESSES, "error": None,
        "selected_address": None, "demo_pin": Config.DEMO_RESIDENT_PIN,
    })


@app.post("/resident/login", response_class=HTMLResponse)
def resident_login_submit(
    request: Request, address: str = Form(...), pin: str = Form(...), db: Session = Depends(get_db),
):
    unit = db.query(Unit).filter(Unit.address == address).first()
    if not unit or not verify_pin(pin, unit.pin_hash):
        return templates.TemplateResponse("resident/login.html", {
            "request": request, "addresses": ADDRESSES,
            "error": "That address and PIN don't match. Please try again.",
            "selected_address": address, "demo_pin": Config.DEMO_RESIDENT_PIN,
        }, status_code=401)
    request.session["resident_unit_id"] = unit.id
    return RedirectResponse("/resident", status_code=303)


@app.post("/resident/logout")
def resident_logout(request: Request):
    request.session.pop("resident_unit_id", None)
    return RedirectResponse("/resident/login", status_code=303)


@app.get("/resident", response_class=HTMLResponse)
def resident_home(request: Request, unit: Unit = Depends(require_resident), db: Session = Depends(get_db)):
    return templates.TemplateResponse("resident/home.html", {
        "request": request, "unit": unit, "vehicles": active_vehicles(db, unit),
        "cap": Config.RESIDENT_PERMIT_CAP,
    })


@app.get("/resident/vehicles/new", response_class=HTMLResponse)
def resident_vehicle_new_form(
    request: Request, unit: Unit = Depends(require_resident), db: Session = Depends(get_db),
):
    if len(active_vehicles(db, unit)) >= Config.RESIDENT_PERMIT_CAP:
        return RedirectResponse("/resident", status_code=303)
    return templates.TemplateResponse("resident/vehicle_form.html", {
        "request": request, "unit": unit, "old_vehicle": None, "error": None,
        "form": None, "action_url": "/resident/vehicles/new",
    })


@app.post("/resident/vehicles/new", response_class=HTMLResponse)
def resident_vehicle_new_submit(
    request: Request,
    plate: str = Form(...), color: str = Form(...), make: str = Form(...), model: str = Form(...),
    unit: Unit = Depends(require_resident), db: Session = Depends(get_db),
):
    try:
        add_vehicle(db, unit, plate, color, make, model)
    except PermitError as e:
        return templates.TemplateResponse("resident/vehicle_form.html", {
            "request": request, "unit": unit, "old_vehicle": None, "error": str(e),
            "form": {"plate": plate, "color": color, "make": make, "model": model},
            "action_url": "/resident/vehicles/new",
        }, status_code=400)
    return templates.TemplateResponse("resident/confirm.html", {
        "request": request, "unit": unit,
        "heading": "Car saved", "message": f"{normalize_plate(plate)} is now on file for {unit.address}.",
    })


@app.get("/resident/vehicles/{vehicle_id}/replace", response_class=HTMLResponse)
def resident_vehicle_replace_form(
    request: Request, vehicle_id: int, unit: Unit = Depends(require_resident), db: Session = Depends(get_db),
):
    old_vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id, Vehicle.unit_id == unit.id, Vehicle.active.is_(True)).first()
    if not old_vehicle:
        raise HTTPException(status_code=404, detail="Car not found")
    return templates.TemplateResponse("resident/vehicle_form.html", {
        "request": request, "unit": unit, "old_vehicle": old_vehicle, "error": None,
        "form": None, "action_url": f"/resident/vehicles/{vehicle_id}/replace",
    })


@app.post("/resident/vehicles/{vehicle_id}/replace", response_class=HTMLResponse)
def resident_vehicle_replace_submit(
    request: Request, vehicle_id: int,
    plate: str = Form(...), color: str = Form(...), make: str = Form(...), model: str = Form(...),
    unit: Unit = Depends(require_resident), db: Session = Depends(get_db),
):
    old_vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id, Vehicle.unit_id == unit.id).first()
    try:
        replace_vehicle(db, unit, vehicle_id, plate, color, make, model)
    except PermitError as e:
        return templates.TemplateResponse("resident/vehicle_form.html", {
            "request": request, "unit": unit, "old_vehicle": old_vehicle, "error": str(e),
            "form": {"plate": plate, "color": color, "make": make, "model": model},
            "action_url": f"/resident/vehicles/{vehicle_id}/replace",
        }, status_code=400)
    return templates.TemplateResponse("resident/confirm.html", {
        "request": request, "unit": unit,
        "heading": "Car replaced", "message": f"The old permit is turned off. {normalize_plate(plate)} is now on file.",
    })


@app.get("/resident/vehicles/{vehicle_id}/remove", response_class=HTMLResponse)
def resident_vehicle_remove_confirm(
    request: Request, vehicle_id: int, unit: Unit = Depends(require_resident), db: Session = Depends(get_db),
):
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id, Vehicle.unit_id == unit.id, Vehicle.active.is_(True)).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Car not found")
    return templates.TemplateResponse("resident/remove_confirm.html", {
        "request": request, "unit": unit, "vehicle": vehicle,
    })


@app.post("/resident/vehicles/{vehicle_id}/remove", response_class=HTMLResponse)
def resident_vehicle_remove_submit(
    request: Request, vehicle_id: int, unit: Unit = Depends(require_resident), db: Session = Depends(get_db),
):
    try:
        vehicle = remove_vehicle(db, unit, vehicle_id)
    except PermitError:
        raise HTTPException(status_code=404, detail="Car not found")
    return templates.TemplateResponse("resident/confirm.html", {
        "request": request, "unit": unit,
        "heading": "Car removed", "message": f"{vehicle.plate} is no longer on file.",
    })


@app.get("/resident/guest-pass", response_class=HTMLResponse)
def resident_guest_pass_form(
    request: Request, unit: Unit = Depends(require_resident), db: Session = Depends(get_db),
):
    return templates.TemplateResponse("resident/guest_pass.html", {
        "request": request, "unit": unit, "active_passes": active_guest_passes(db, unit),
        "max_active": Config.GUEST_PASS_MAX_ACTIVE,
        "max_hours": Config.GUEST_PASS_MAX_HOURS, "error": None,
    })


@app.post("/resident/guest-pass", response_class=HTMLResponse)
def resident_guest_pass_submit(
    request: Request, plate: str = Form(...), hours: int = Form(...), guest_note: str = Form(""),
    unit: Unit = Depends(require_resident), db: Session = Depends(get_db),
):
    try:
        guest_pass = issue_guest_pass(db, unit, plate, hours, guest_note)
    except PermitError as e:
        return templates.TemplateResponse("resident/guest_pass.html", {
            "request": request, "unit": unit, "active_passes": active_guest_passes(db, unit),
            "max_active": Config.GUEST_PASS_MAX_ACTIVE,
            "max_hours": Config.GUEST_PASS_MAX_HOURS, "error": str(e),
        }, status_code=400)
    return templates.TemplateResponse("resident/guest_pass_confirm.html", {
        "request": request, "unit": unit, "guest_pass": guest_pass,
    })


@app.get("/resident/rules", response_class=HTMLResponse)
def resident_rules(request: Request, db: Session = Depends(get_db)):
    unit = db.query(Unit).filter(Unit.id == request.session.get("resident_unit_id")).first()
    return templates.TemplateResponse("resident/rules.html", {
        "request": request, "unit": unit, "cap": Config.RESIDENT_PERMIT_CAP,
        "tow_approval_required": Config.TOW_APPROVAL_REQUIRED,
    })


# ==================================================================== tow =

@app.get("/tow/login", response_class=HTMLResponse)
def tow_login_form(request: Request):
    if is_tow_operator(request):
        return RedirectResponse("/tow", status_code=303)
    return templates.TemplateResponse("tow/login.html", {
        "request": request, "error": None, "demo_code": Config.TOW_COMPANY_CODE,
    })


@app.post("/tow/login", response_class=HTMLResponse)
def tow_login_submit(request: Request, code: str = Form(...)):
    if code.strip() != Config.TOW_COMPANY_CODE:
        return templates.TemplateResponse("tow/login.html", {
            "request": request, "error": "That code isn't recognized.",
            "demo_code": Config.TOW_COMPANY_CODE,
        }, status_code=401)
    request.session["tow_operator"] = True
    return RedirectResponse("/tow", status_code=303)


@app.post("/tow/logout")
def tow_logout(request: Request):
    request.session.pop("tow_operator", None)
    return RedirectResponse("/tow/login", status_code=303)


@app.get("/tow", response_class=HTMLResponse)
def tow_lookup_form(request: Request, _=Depends(require_tow_operator)):
    return templates.TemplateResponse("tow/lookup.html", {"request": request})


@app.post("/tow/lookup", response_class=HTMLResponse)
def tow_lookup_submit(request: Request, plate: str = Form(...), db: Session = Depends(get_db), _=Depends(require_tow_operator)):
    result = lookup_plate(db, plate)
    if result.valid:
        return templates.TemplateResponse("tow/result_valid.html", {"request": request, "result": result})
    return templates.TemplateResponse("tow/result_invalid.html", {"request": request, "plate": result.plate_display})


@app.post("/tow/outcome", response_class=HTMLResponse)
def tow_outcome(
    request: Request, plate: str = Form(...), zone: str = Form(...),
    db: Session = Depends(get_db), _=Depends(require_tow_operator),
):
    plate_display = normalize_plate(plate)
    outcome = outcome_for_no_permit(zone)
    if outcome == OUTCOME_NEVER_TOW:
        return templates.TemplateResponse("tow/outcome_never_tow.html", {"request": request, "plate": plate_display})
    if outcome == OUTCOME_ONLY_IF_REQUESTED:
        return templates.TemplateResponse("tow/outcome_green.html", {"request": request, "plate": plate_display})
    if outcome == OUTCOME_MAY_BE_TOWED:
        return templates.TemplateResponse("tow/outcome_may_be_towed.html", {"request": request, "plate": plate_display})

    # OUTCOME_APPROVAL_REQUIRED
    existing = (
        db.query(ApprovalRequest)
        .filter(ApprovalRequest.plate_key == plate_match_key(plate))
        .order_by(ApprovalRequest.requested_at.desc())
        .first()
    )
    return templates.TemplateResponse("tow/outcome_approval_required.html", {
        "request": request, "plate": plate_display, "existing_request": existing,
    })


@app.post("/tow/approval-requests", response_class=HTMLResponse)
def tow_create_approval_request(
    request: Request, plate: str = Form(...), location_note: str = Form(""),
    db: Session = Depends(get_db), _=Depends(require_tow_operator),
):
    req = ApprovalRequest(
        plate=normalize_plate(plate), plate_key=plate_match_key(plate),
        zone="orange", location_note=location_note.strip() or None,
        status="pending", requested_at=now(),
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return RedirectResponse(f"/tow/approval-requests/{req.id}", status_code=303)


@app.get("/tow/approval-requests/{request_id}", response_class=HTMLResponse)
def tow_approval_status(
    request: Request, request_id: int, db: Session = Depends(get_db), _=Depends(require_tow_operator),
):
    req = db.query(ApprovalRequest).filter(ApprovalRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    return templates.TemplateResponse("tow/approval_status.html", {"request": request, "request_row": req})


@app.get("/tow/record-tow", response_class=HTMLResponse)
def tow_record_form(
    request: Request, plate: str = Query(""), zone: str = Query(""), approval_reference: str = Query(""),
    _=Depends(require_tow_operator),
):
    return templates.TemplateResponse("tow/record_tow.html", {
        "request": request, "plate": normalize_plate(plate) if plate else "", "zone": zone,
        "approval_reference": approval_reference, "error": None,
    })


@app.post("/tow/record-tow", response_class=HTMLResponse)
async def tow_record_submit(
    request: Request,
    plate: str = Form(...), zone: str = Form(...), location_note: str = Form(""),
    approval_reference: str = Form(""), photo: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db), _=Depends(require_tow_operator),
):
    if zone not in ("orange", "green", "driveway"):
        raise HTTPException(status_code=400, detail="Invalid zone")

    photo_path = None
    if photo is not None and photo.filename:
        ext = Path(photo.filename).suffix.lower()
        if ext not in _ALLOWED_PHOTO_EXTENSIONS:
            return templates.TemplateResponse("tow/record_tow.html", {
                "request": request, "plate": plate, "zone": zone,
                "approval_reference": approval_reference,
                "error": "Photo must be a jpg, png, webp, or gif file.",
            }, status_code=400)
        filename = f"{uuid.uuid4().hex}{ext}"
        contents = await photo.read()
        (Config.UPLOADS_DIR / filename).write_bytes(contents)
        photo_path = filename

    entry = TowLogEntry(
        plate=normalize_plate(plate), plate_key=plate_match_key(plate), zone=zone,
        location_note=location_note.strip() or None,
        approval_reference=approval_reference.strip() or None,
        photo_path=photo_path, towed_at=now(),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return templates.TemplateResponse("tow/record_tow_confirm.html", {"request": request, "entry": entry})


# ================================================================== board =

@app.get("/board/login", response_class=HTMLResponse)
def board_login_form(request: Request):
    if get_current_board_user(request):
        return RedirectResponse("/board", status_code=303)
    return templates.TemplateResponse("board/login.html", {
        "request": request, "error": None,
        "demo_username": Config.ADMIN_USERNAME, "demo_password": Config.ADMIN_PASSWORD,
    })


@app.post("/board/login", response_class=HTMLResponse)
def board_login_submit(request: Request, username: str = Form(...), password: str = Form(...)):
    if not authenticate_board(username, password):
        return templates.TemplateResponse("board/login.html", {
            "request": request, "error": "Invalid username or password.",
            "demo_username": Config.ADMIN_USERNAME, "demo_password": Config.ADMIN_PASSWORD,
        }, status_code=401)
    request.session["board_user"] = username
    return RedirectResponse("/board", status_code=303)


@app.post("/board/logout")
def board_logout(request: Request):
    request.session.pop("board_user", None)
    return RedirectResponse("/board/login", status_code=303)


@app.get("/board", response_class=HTMLResponse)
def board_dashboard(request: Request, user: str = Depends(require_board), db: Session = Depends(get_db)):
    return templates.TemplateResponse("board/dashboard.html", {
        "request": request,
        "unit_count": db.query(Unit).count(),
        "vehicle_count": db.query(Vehicle).filter(Vehicle.active.is_(True)).count(),
        "pending_count": db.query(ApprovalRequest).filter(ApprovalRequest.status == "pending").count(),
    })


@app.get("/board/units", response_class=HTMLResponse)
def board_units_list(
    request: Request, q: str = Query(""), user: str = Depends(require_board), db: Session = Depends(get_db),
):
    query = db.query(Unit)
    if q:
        query = query.filter(Unit.address.ilike(f"%{q}%"))
    units = query.order_by(Unit.address.asc()).all()
    rows = [{
        "unit": unit,
        "vehicle_count": len(active_vehicles(db, unit)),
        "guest_pass_count": len(active_guest_passes(db, unit)),
    } for unit in units]
    return templates.TemplateResponse("board/units_list.html", {"request": request, "units": rows, "q": q})


@app.get("/board/units/{unit_id}", response_class=HTMLResponse)
def board_unit_detail(
    request: Request, unit_id: int, user: str = Depends(require_board), db: Session = Depends(get_db),
):
    unit = db.query(Unit).filter(Unit.id == unit_id).first()
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")
    return templates.TemplateResponse("board/unit_detail.html", {
        "request": request, "unit": unit, "vehicles": active_vehicles(db, unit),
        "guest_passes": active_guest_passes(db, unit), "cap": Config.RESIDENT_PERMIT_CAP,
        "error": None, "message": None,
    })


@app.post("/board/units/{unit_id}/vehicles/new", response_class=HTMLResponse)
def board_unit_add_vehicle(
    request: Request, unit_id: int,
    plate: str = Form(...), color: str = Form(...), make: str = Form(...), model: str = Form(...),
    user: str = Depends(require_board), db: Session = Depends(get_db),
):
    unit = db.query(Unit).filter(Unit.id == unit_id).first()
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")
    error = None
    try:
        add_vehicle(db, unit, plate, color, make, model)
    except PermitError as e:
        error = str(e)
    return templates.TemplateResponse("board/unit_detail.html", {
        "request": request, "unit": unit, "vehicles": active_vehicles(db, unit),
        "guest_passes": active_guest_passes(db, unit), "cap": Config.RESIDENT_PERMIT_CAP,
        "error": error, "message": None if error else "Car added.",
    }, status_code=400 if error else 200)


@app.post("/board/units/{unit_id}/vehicles/{vehicle_id}/remove", response_class=HTMLResponse)
def board_unit_remove_vehicle(
    request: Request, unit_id: int, vehicle_id: int,
    user: str = Depends(require_board), db: Session = Depends(get_db),
):
    unit = db.query(Unit).filter(Unit.id == unit_id).first()
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")
    error = None
    try:
        remove_vehicle(db, unit, vehicle_id)
    except PermitError as e:
        error = str(e)
    return templates.TemplateResponse("board/unit_detail.html", {
        "request": request, "unit": unit, "vehicles": active_vehicles(db, unit),
        "guest_passes": active_guest_passes(db, unit), "cap": Config.RESIDENT_PERMIT_CAP,
        "error": error, "message": None if error else "Car removed.",
    })


@app.get("/board/approvals", response_class=HTMLResponse)
def board_approvals(request: Request, user: str = Depends(require_board), db: Session = Depends(get_db)):
    pending = (
        db.query(ApprovalRequest).filter(ApprovalRequest.status == "pending")
        .order_by(ApprovalRequest.requested_at.asc()).all()
    )
    decided = (
        db.query(ApprovalRequest).filter(ApprovalRequest.status != "pending")
        .order_by(ApprovalRequest.decided_at.desc()).all()
    )
    return templates.TemplateResponse("board/approvals.html", {"request": request, "pending": pending, "decided": decided})


def _decide_approval(db: Session, request_id: int, decided_by: str, status: str) -> ApprovalRequest:
    req = db.query(ApprovalRequest).filter(ApprovalRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    req.status = status
    req.decided_by = decided_by.strip()
    req.decided_at = now()
    db.commit()
    return req


@app.post("/board/approvals/{request_id}/approve")
def board_approve(request_id: int, decided_by: str = Form(...), user: str = Depends(require_board), db: Session = Depends(get_db)):
    _decide_approval(db, request_id, decided_by, "approved")
    return RedirectResponse("/board/approvals", status_code=303)


@app.post("/board/approvals/{request_id}/deny")
def board_deny(request_id: int, decided_by: str = Form(...), user: str = Depends(require_board), db: Session = Depends(get_db)):
    _decide_approval(db, request_id, decided_by, "denied")
    return RedirectResponse("/board/approvals", status_code=303)


@app.get("/board/tow-log", response_class=HTMLResponse)
def board_tow_log(request: Request, user: str = Depends(require_board), db: Session = Depends(get_db)):
    entries = db.query(TowLogEntry).order_by(TowLogEntry.towed_at.desc()).all()
    return templates.TemplateResponse("board/tow_log.html", {"request": request, "entries": entries})


@app.get("/board/audit-log", response_class=HTMLResponse)
def board_audit_log(request: Request, user: str = Depends(require_board), db: Session = Depends(get_db)):
    entries = db.query(LookupAuditLog).order_by(LookupAuditLog.looked_up_at.desc()).limit(500).all()
    return templates.TemplateResponse("board/audit_log.html", {"request": request, "entries": entries})


@app.post("/board/reset-demo-data")
def board_reset_demo_data(user: str = Depends(require_board), db: Session = Depends(get_db)):
    if not Config.DEMO_MODE:
        raise HTTPException(status_code=403, detail="Demo reset is disabled outside demo mode")
    reset_demo_data(db)
    return RedirectResponse("/board", status_code=303)
