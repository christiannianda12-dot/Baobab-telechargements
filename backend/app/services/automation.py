"""Cycle d'automatisation : mise à jour des données, cotes, enregistrement des prédictions, règlement."""

import json
import logging
import threading
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AutomationRun, FollowedLeague, Match, Prediction
from app.models.mixins import utcnow
from app.models.sports import MatchStatus
from app.services import appsettings, oddsapi, sources, tracking

log = logging.getLogger("predix.automation")
RUN_LOCK = threading.Lock()


def record_upcoming(db: Session, hours: int) -> dict:
    """Enregistre (une seule fois, de façon immuable) la prédiction des matchs qui commencent dans les `hours` prochaines heures."""
    now = utcnow()
    q = select(Match).where(
        Match.status == MatchStatus.SCHEDULED,
        Match.kickoff_at > now,
        Match.kickoff_at <= now + timedelta(hours=hours),
    )
    already = set(db.scalars(select(Prediction.match_id).distinct()))
    out = {"recorded": 0, "no_model": 0, "already": 0}
    for m in db.scalars(q):
        if m.id in already:
            out["already"] += 1
            continue
        try:
            tracking.record(db, m, None)
            out["recorded"] += 1
        except tracking.RecordError:
            out["no_model"] += 1  # historique insuffisant : jamais de prédiction inventée
    return out


def run_cycle(factory, trigger: str = "auto", client=None) -> dict | None:
    """Exécute un cycle complet. Retourne None si un cycle est déjà en cours. Chaque étape est isolée : une panne n'arrête pas les autres."""
    if not RUN_LOCK.acquire(blocking=False):
        return None
    try:
        with factory() as db:
            run = AutomationRun(trigger=trigger, status="running")
            db.add(run)
            db.commit()
            summary: dict = {}
            errors = 0

            def step(name, fn):
                nonlocal errors
                try:
                    summary[name] = fn()
                except Exception as e:  # noqa: BLE001
                    errors += 1
                    summary[name] = {"error": str(e)[:300]}
                    log.exception("étape %s en échec", name)

            if db.scalar(select(FollowedLeague.id).limit(1)) is not None:

                def _upd():
                    res = sources.update_all(db, client=client, pause=1.0)
                    bad = [r for r in res if r["status"] == "erreur"]
                    nonlocal errors
                    errors += len(bad)
                    return {
                        "files": len(res),
                        "created": sum(r.get("created", 0) for r in res),
                        "updated": sum(r.get("updated", 0) for r in res),
                        "ignored": sum(r.get("ignored", 0) for r in res),
                        "errors": [f"{r['label']}: {r.get('message', '')}"[:200] for r in bad][:10],
                    }

                step("update", _upd)
            if appsettings.get(db, "odds_api_key").strip():
                last = appsettings.get(db, "odds_api_last_run")
                every = appsettings.as_int(db, "odds_api_every_hours", 24)
                from datetime import datetime

                due = not last or utcnow() - datetime.fromisoformat(last) >= timedelta(hours=every)
                if due or trigger == "manual":
                    step("odds", lambda: oddsapi.refresh_odds(db))
            if appsettings.as_bool(db, "auto_record"):
                step(
                    "predictions",
                    lambda: record_upcoming(db, appsettings.as_int(db, "auto_record_hours", 48)),
                )
            step("settled", lambda: {"count": tracking.settle_pending(db)})
            run.finished_at, run.summary = utcnow(), json.dumps(summary, ensure_ascii=False)
            run.status = "ok" if not errors else "partial"
            db.commit()
            return {"run_id": run.id, "status": run.status, "summary": summary}
    finally:
        RUN_LOCK.release()


def last_run(db: Session) -> AutomationRun | None:
    return db.scalar(
        select(AutomationRun)
        .where(AutomationRun.finished_at.is_not(None))
        .order_by(AutomationRun.id.desc())
        .limit(1)
    )


def next_run_at(db: Session):
    if not appsettings.as_bool(db, "auto_enabled"):
        return None
    last = last_run(db)
    interval = timedelta(hours=appsettings.as_int(db, "auto_interval_hours", 6))
    return (last.finished_at + interval) if last else utcnow()


def is_due(db: Session) -> bool:
    nxt = next_run_at(db)
    return nxt is not None and nxt <= utcnow()
