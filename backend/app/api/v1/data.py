from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status

from app.api.deps import CurrentUser, DbDep
from app.models import Match
from app.services.csv_import import import_csv
from app.services.form import match_analysis

router = APIRouter(tags=["import et analyse des données"])
MAX_BYTES = 2_000_000


@router.post("/import/matches")
async def import_matches(
    db: DbDep, user: CurrentUser, file: Annotated[UploadFile, File()], dry_run: bool = False
):
    """Import CSV de matchs terminés (tout-ou-rien). `dry_run=true` valide sans rien écrire."""
    raw = await file.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE, "Fichier trop volumineux (2 Mo max)."
        )
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(422, "Le fichier doit être encodé en UTF-8.") from None
    rep = import_csv(
        db,
        text,
        dry_run=dry_run,
        user_id=user.id,
        source="upload",
        label=file.filename or "fichier.csv",
    )
    body = rep.__dict__
    if rep.errors:
        raise HTTPException(422, detail={"message": "Import refusé : aucune ligne écrite.", **body})
    return body


@router.get("/matches/{match_id}/analysis")
def analysis(db: DbDep, match_id: int, window: Annotated[int, Query(ge=3, le=20)] = 10):
    """Forme, domicile/extérieur, confrontations directes — matchs antérieurs au coup d'envoi uniquement."""
    match = db.get(Match, match_id)
    if not match:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Match introuvable.")
    return match_analysis(db, match, window)
