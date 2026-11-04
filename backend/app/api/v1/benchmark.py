from fastapi import APIRouter, HTTPException, status

from app.api.deps import DbDep
from app.models import Competition
from app.services import benchmark

router = APIRouter(tags=["fiabilité"])


@router.get("/benchmark/{competition_id}")
def get_benchmark(competition_id: int, db: DbDep):
    """Modèle contre marché (cotes de clôture) sur l'historique du championnat (toutes saisons regroupées)."""
    if not db.get(Competition, competition_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Compétition introuvable.")
    return benchmark.compute(db, competition_id)
