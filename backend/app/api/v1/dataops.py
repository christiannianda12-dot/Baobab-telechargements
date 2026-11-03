import threading
import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import AdminUser, CurrentUser, DbDep
from app.db.session import SessionLocal
from app.models import Competition, FollowedLeague, ImportBatch
from app.services import dataops, explorer, sources

router = APIRouter(tags=["données : sources, qualité, explorateur"])
JOBS: dict[str, dict] = {}  # suivi en mémoire (instance unique)
_lock = threading.Lock()


# ---------- Catalogue et téléchargement ----------
@router.get("/sources/catalog")
def catalog(db: DbDep):
    followed = {f.code: f for f in db.scalars(select(FollowedLeague))}
    return [
        {
            **c,
            "followed": c["code"] in followed,
            "last_update_at": followed[c["code"]].last_update_at.isoformat()
            if c["code"] in followed and followed[c["code"]].last_update_at
            else None,
            "last_status": followed[c["code"]].last_status if c["code"] in followed else None,
        }
        for c in sources.catalog()
    ]


class AddLeague(BaseModel):
    code: str = Field(min_length=1, max_length=10)
    seasons: int = Field(default=3, ge=1, le=10)


def _run(job_id: str, fn):
    with SessionLocal() as db:
        try:
            res = fn(db, lambda i, n, msg: JOBS[job_id].update(progress=f"{i}/{n} — {msg}"))
            JOBS[job_id].update(status="done", results=res)
        except Exception as e:  # noqa: BLE001 - toute erreur est remontée à l'utilisateur
            JOBS[job_id].update(status="error", message=str(e)[:300])


def _start(bg: BackgroundTasks, fn) -> dict:
    with _lock:
        if any(j["status"] == "running" for j in JOBS.values()):
            raise HTTPException(409, "Un téléchargement est déjà en cours : attendez sa fin.")
        job_id = uuid.uuid4().hex[:12]
        JOBS[job_id] = {"status": "running", "progress": "démarrage", "results": []}
    bg.add_task(_run, job_id, fn)
    return {"job_id": job_id}


@router.post("/sources/leagues", status_code=202)
def add_league(payload: AddLeague, bg: BackgroundTasks, admin: AdminUser):
    code = (
        payload.code.strip().upper()
        if payload.code.strip().upper() in {c["code"] for c in sources.catalog()}
        else payload.code.strip()
    )
    if code not in {c["code"] for c in sources.catalog()}:
        raise HTTPException(404, "Championnat inconnu.")
    return _start(bg, lambda db, prog: sources.add_league(db, code, payload.seasons, admin.id))


@router.post("/sources/update", status_code=202)
def update_all(bg: BackgroundTasks, admin: AdminUser):
    return _start(bg, lambda db, prog: sources.update_all(db, admin.id, progress=prog))


@router.get("/sources/jobs/{job_id}")
def job(job_id: str, _: CurrentUser):
    if job_id not in JOBS:
        raise HTTPException(404, "Tâche introuvable.")
    return JOBS[job_id]


@router.delete("/sources/leagues/{code}", status_code=204)
def unfollow(code: str, db: DbDep, _: AdminUser):
    f = db.scalar(select(FollowedLeague).where(FollowedLeague.code == code))
    if f:
        db.delete(f)
        db.commit()


# ---------- Imports (traçabilité) ----------
@router.get("/imports")
def imports(db: DbDep, _: CurrentUser, limit: Annotated[int, Query(ge=1, le=200)] = 50):
    q = (
        select(ImportBatch)
        .order_by(ImportBatch.created_at.desc(), ImportBatch.id.desc())
        .limit(limit)
    )
    return [
        {
            "id": b.id,
            "created_at": b.created_at.isoformat(),
            "source": b.source,
            "label": b.label,
            "rows": b.rows,
            "created_matches": b.created_matches,
            "updated_matches": b.updated_matches,
            "skipped": b.skipped,
            "created_teams": b.created_teams,
            "status": b.status,
        }
        for b in db.scalars(q)
    ]


@router.post("/imports/{batch_id}/rollback")
def rollback(batch_id: int, db: DbDep, _: AdminUser):
    try:
        return dataops.rollback_batch(db, batch_id)
    except dataops.OpsError as e:
        raise HTTPException(e.status, e.message) from None


# ---------- Équipes : doublons, fusion, nettoyage ----------
@router.get("/teams/duplicates")
def duplicates(db: DbDep, _: AdminUser):
    return dataops.duplicate_suggestions(db)


class Merge(BaseModel):
    keep_id: int
    remove_id: int


@router.post("/teams/merge")
def merge(payload: Merge, db: DbDep, _: AdminUser):
    try:
        return dataops.merge_teams(db, payload.keep_id, payload.remove_id)
    except dataops.OpsError as e:
        raise HTTPException(e.status, e.message) from None


@router.post("/admin/cleanup")
def cleanup(db: DbDep, _: AdminUser):
    return dataops.cleanup_orphans(db)


# ---------- Qualité ----------
@router.get("/quality/{competition_id}")
def quality(competition_id: int, db: DbDep, _: CurrentUser):
    if not db.get(Competition, competition_id):
        raise HTTPException(404, "Compétition introuvable.")
    return dataops.quality_report(db, competition_id)


# ---------- Explorateur ----------
@router.get("/leagues")
def leagues(db: DbDep):
    return explorer.leagues(db)


@router.get("/leagues/{competition_id}/standings")
def standings(competition_id: int, db: DbDep):
    res = explorer.standings(db, competition_id)
    if res is None:
        raise HTTPException(404, "Compétition introuvable.")
    return res


@router.get("/teams/{team_id}/profile")
def team_profile(team_id: int, db: DbDep):
    res = explorer.team_profile(db, team_id)
    if res is None:
        raise HTTPException(404, "Équipe introuvable.")
    return res


@router.get("/matches-search")
def matches_search(
    db: DbDep,
    league_id: int | None = None,
    competition_id: int | None = None,
    team: str | None = Query(default=None, max_length=80),
    status: Literal["scheduled", "live", "finished", "postponed", "cancelled"] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    order: Literal["asc", "desc"] = "desc",
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    from datetime import datetime

    def _d(v):
        try:
            return datetime.fromisoformat(v.replace("Z", "+00:00")) if v else None
        except ValueError:
            raise HTTPException(422, "Date invalide.") from None

    return explorer.search_matches(
        db,
        league_id=league_id,
        competition_id=competition_id,
        team_q=team,
        status=status,
        date_from=_d(date_from),
        date_to=_d(date_to),
        order=order,
        limit=limit,
        offset=offset,
    )


@router.get("/search")
def search(q: Annotated[str, Query(max_length=60)], db: DbDep):
    return explorer.global_search(db, q)
