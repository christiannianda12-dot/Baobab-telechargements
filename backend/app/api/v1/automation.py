import json
from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import AdminUser, CurrentUser, DbDep
from app.db.session import SessionLocal
from app.models import AutomationRun
from app.services import appsettings, automation, oddsapi, proposals

router = APIRouter(tags=["automatisation et combinés proposés"])


@router.get("/automation/status")
def status(db: DbDep, _: CurrentUser):
    runs = db.scalars(select(AutomationRun).order_by(AutomationRun.id.desc()).limit(10))
    nxt = automation.next_run_at(db)
    return {
        "settings": appsettings.public(db),
        "running": automation.RUN_LOCK.locked(),
        "next_run_at": nxt.isoformat() if nxt else None,
        "runs": [
            {
                "id": r.id,
                "started_at": r.created_at.isoformat(),
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                "trigger": r.trigger,
                "status": r.status,
                "summary": json.loads(r.summary) if r.summary else None,
            }
            for r in runs
        ],
    }


class SettingsIn(BaseModel):
    auto_enabled: bool | None = None
    auto_interval_hours: Literal[1, 3, 6, 12, 24] | None = None
    auto_record: bool | None = None
    auto_record_hours: int | None = Field(default=None, ge=6, le=168)
    odds_api_key: str | None = Field(default=None, max_length=120)  # "" = effacer
    odds_api_every_hours: Literal[6, 12, 24, 48] | None = None


@router.put("/automation/settings")
def update_settings(payload: SettingsIn, db: DbDep, _: AdminUser):
    for k, v in payload.model_dump(exclude_none=True).items():
        appsettings.put(db, k, ("1" if v else "0") if isinstance(v, bool) else str(v).strip())
    return appsettings.public(db)


@router.post("/automation/run", status_code=202)
def run_now(bg: BackgroundTasks, _: AdminUser):
    if automation.RUN_LOCK.locked():
        raise HTTPException(409, "Une mise à jour est déjà en cours.")
    bg.add_task(automation.run_cycle, SessionLocal, "manual")
    return {"started": True}


@router.post("/automation/odds-key/test")
def test_odds_key(db: DbDep, _: AdminUser):
    key = appsettings.get(db, "odds_api_key").strip()
    if not key:
        raise HTTPException(422, "Aucune clé enregistrée.")
    try:
        res = oddsapi.test_key(key)
    except oddsapi.OddsApiError as e:
        raise HTTPException(422, str(e)) from None
    if res.get("remaining") is not None:
        appsettings.put(db, "odds_api_remaining", str(res["remaining"]))
    return res


@router.get("/today")
def today(
    db: DbDep,
    days: Annotated[int, Query(ge=1, le=14)] = 3,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
):
    return proposals.today(db, days, limit)


@router.get("/combos/proposals")
def combo_proposals(
    db: DbDep,
    _: CurrentUser,
    profile: Literal["prudent", "equilibre", "ambitieux"] = "prudent",
    days: Annotated[int, Query(ge=1, le=14)] = 3,
):
    return proposals.build(db, profile, days)
