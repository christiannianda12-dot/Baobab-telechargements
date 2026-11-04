"""Outils d'exploitation des données : annulation d'import, fusion d'équipes, nettoyage, rapport de qualité."""

import difflib
from collections import defaultdict
from datetime import timedelta

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import Session

from app.models import (
    Competition,
    ImportBatch,
    Match,
    MatchStatistics,
    Odds,
    Prediction,
    Team,
    TeamAlias,
    TeamForm,
)
from app.models.mixins import utcnow
from app.models.sports import MatchStatus
from app.services.csv_import import CLOSING_BOOKMAKER
from app.services.names import abbreviation, norm_key


class OpsError(Exception):
    def __init__(self, status: int, message: str):
        self.status, self.message = status, message


def rollback_batch(db: Session, batch_id: int) -> dict:
    """Supprime les matchs CRÉÉS par un import (avec statistiques et cotes). Refusé si des prédictions les concernent."""
    b = db.get(ImportBatch, batch_id)
    if b is None:
        raise OpsError(404, "Import introuvable.")
    if b.status != "active":
        raise OpsError(409, "Cet import est déjà annulé.")
    ids = list(db.scalars(select(Match.id).where(Match.import_batch_id == batch_id)))
    if ids and (
        n := db.scalar(
            select(func.count()).select_from(Prediction).where(Prediction.match_id.in_(ids))
        )
    ):
        raise OpsError(
            409,
            f"Annulation impossible : {n} prédiction(s) enregistrée(s) concernent ces matchs (l'historique est immuable).",
        )
    if ids:
        db.execute(delete(Odds).where(Odds.match_id.in_(ids)))
        db.execute(delete(MatchStatistics).where(MatchStatistics.match_id.in_(ids)))
        db.execute(delete(Match).where(Match.id.in_(ids)))
    b.status, b.rolled_back_at = "rolled_back", utcnow()
    db.commit()
    return {
        "deleted_matches": len(ids),
        "note": "Les résultats ajoutés à des matchs déjà existants ne sont pas annulés.",
    }


def cleanup_orphans(db: Session) -> dict:
    used = set(db.scalars(select(Match.home_team_id))) | set(db.scalars(select(Match.away_team_id)))
    orphan_t = [t for t in db.scalars(select(Team.id)) if t not in used]
    comp_used = set(db.scalars(select(Match.competition_id)))
    orphan_c = [c for c in db.scalars(select(Competition.id)) if c not in comp_used]
    if orphan_t:
        db.execute(delete(TeamAlias).where(TeamAlias.team_id.in_(orphan_t)))
        db.execute(delete(Team).where(Team.id.in_(orphan_t)))
    if orphan_c:
        db.execute(delete(Competition).where(Competition.id.in_(orphan_c)))
    db.commit()
    return {"teams": len(orphan_t), "competitions": len(orphan_c)}


def duplicate_suggestions(db: Session, cutoff: float = 0.8) -> list[dict]:
    """Paires d'équipes probablement identiques. Deux équipes qui jouent dans la même compétition sont forcément distinctes."""
    teams = list(db.scalars(select(Team)))
    comps: dict[int, set[int]] = defaultdict(set)
    counts: dict[int, int] = defaultdict(int)
    for hid, aid, cid in db.execute(
        select(Match.home_team_id, Match.away_team_id, Match.competition_id)
    ):
        comps[hid].add(cid)
        comps[aid].add(cid)
        counts[hid] += 1
        counts[aid] += 1
    keys = {t.id: norm_key(t.name) for t in teams}
    out = []
    for i, a in enumerate(teams):
        for b in teams[i + 1 :]:
            if comps[a.id] & comps[b.id]:
                continue
            ka, kb = keys[a.id], keys[b.id]
            if ka == kb:
                score = 1.0
            elif abbreviation(ka, kb):
                score = 0.9
            else:
                sm = difflib.SequenceMatcher(None, ka, kb)
                if sm.real_quick_ratio() < cutoff or sm.quick_ratio() < cutoff:
                    continue
                score = sm.ratio()
                if score < cutoff and not (min(len(ka), len(kb)) >= 5 and (ka in kb or kb in ka)):
                    continue
            out.append(
                {
                    "a": {"id": a.id, "name": a.name, "matches": counts[a.id]},
                    "b": {"id": b.id, "name": b.name, "matches": counts[b.id]},
                    "score": round(score, 2),
                }
            )
    return sorted(out, key=lambda x: -x["score"])[:100]


def merge_teams(db: Session, keep_id: int, remove_id: int) -> dict:
    if keep_id == remove_id:
        raise OpsError(422, "Choisissez deux équipes différentes.")
    keep, rem = db.get(Team, keep_id), db.get(Team, remove_id)
    if keep is None or rem is None:
        raise OpsError(404, "Équipe introuvable.")
    clash = db.scalar(
        select(func.count())
        .select_from(Match)
        .where(
            or_(
                (Match.home_team_id == keep_id) & (Match.away_team_id == remove_id),
                (Match.home_team_id == remove_id) & (Match.away_team_id == keep_id),
            )
        )
    )
    if clash:
        raise OpsError(
            409,
            "Ces deux équipes se sont affrontées : ce sont des équipes distinctes, la fusion est refusée.",
        )
    n_home = db.execute(
        update(Match).where(Match.home_team_id == remove_id).values(home_team_id=keep_id)
    ).rowcount
    n_away = db.execute(
        update(Match).where(Match.away_team_id == remove_id).values(away_team_id=keep_id)
    ).rowcount
    db.execute(
        update(MatchStatistics).where(MatchStatistics.team_id == remove_id).values(team_id=keep_id)
    )
    db.execute(delete(TeamForm).where(TeamForm.team_id == remove_id))
    db.execute(update(TeamAlias).where(TeamAlias.team_id == remove_id).values(team_id=keep_id))
    key = norm_key(rem.name)
    if (
        key != norm_key(keep.name)
        and db.scalar(select(TeamAlias.id).where(TeamAlias.alias_key == key)) is None
    ):
        db.add(
            TeamAlias(alias_key=key, team_id=keep_id)
        )  # les prochains imports utiliseront ce nom
    removed_name = rem.name
    db.delete(rem)
    db.commit()
    return {"kept": keep.name, "removed": removed_name, "matches_reassigned": n_home + n_away}


def quality_report(db: Session, competition_id: int) -> dict:
    """Contrôles de qualité sur toutes les saisons d'un championnat. Chaque anomalie a un niveau et une piste d'action."""
    from app.ml.data import sibling_ids

    ids = sibling_ids(db, competition_id)
    comps = {c.id: c for c in db.scalars(select(Competition).where(Competition.id.in_(ids)))}
    matches = list(db.scalars(select(Match).where(Match.competition_id.in_(ids))))
    now = utcnow()
    issues: list[dict] = []
    seasons = []
    by_season: dict[int, list[Match]] = defaultdict(list)
    for m in matches:
        by_season[m.competition_id].append(m)
    match_ids = [m.id for m in matches]
    closing = (
        set(
            db.scalars(
                select(Odds.match_id).where(
                    Odds.match_id.in_(match_ids), Odds.bookmaker == CLOSING_BOOKMAKER
                )
            )
        )
        if match_ids
        else set()
    )
    pre = (
        set(
            db.scalars(
                select(Odds.match_id).where(
                    Odds.match_id.in_(match_ids), Odds.bookmaker != CLOSING_BOOKMAKER
                )
            )
        )
        if match_ids
        else set()
    )
    with_shots = (
        set(
            db.scalars(
                select(MatchStatistics.match_id).where(
                    MatchStatistics.match_id.in_(match_ids), MatchStatistics.shots.is_not(None)
                )
            )
        )
        if match_ids
        else set()
    )

    def add(level, msg, hint=""):
        issues.append({"level": level, "message": msg, "hint": hint})

    for cid in sorted(by_season, key=lambda i: comps[i].season or "", reverse=True):
        ms = by_season[cid]
        fin = [m for m in ms if m.status == MatchStatus.FINISHED]
        sched = [m for m in ms if m.status == MatchStatus.SCHEDULED]
        teams = {t for m in ms for t in (m.home_team_id, m.away_team_id)}
        expected = len(teams) * (len(teams) - 1)
        label = comps[cid].season or "sans saison"
        stale = [m for m in sched if m.kickoff_at < now - timedelta(days=2)]
        seasons.append(
            {
                "competition_id": cid,
                "season": label,
                "matches": len(ms),
                "finished": len(fin),
                "scheduled": len(sched),
                "teams": len(teams),
                "expected_if_complete": expected,
                "closing_odds_pct": round(100 * sum(m.id in closing for m in fin) / len(fin), 1)
                if fin
                else None,
                "shots_pct": round(100 * sum(m.id in with_shots for m in fin) / len(fin), 1)
                if fin
                else None,
            }
        )
        if stale:
            add(
                "warning",
                f"{label} : {len(stale)} match(s) programmé(s) dans le passé sans résultat.",
                "Mettez à jour les données ou saisissez les résultats : ils bloquent le règlement des prédictions.",
            )
        if (
            fin
            and len(fin) + len(sched) < expected * 0.97
            and not any(m.kickoff_at > now for m in ms)
            and len(teams) >= 8
        ):
            add(
                "warning",
                f"{label} : {len(ms)} match(s) pour {len(teams)} équipes (attendu {expected} pour une saison complète).",
                "Un fichier est peut-être incomplet ; réimportez-le.",
            )
        if fin and (closing_pct := 100 * sum(m.id in closing for m in fin) / len(fin)) < 80:
            add(
                "info",
                f"{label} : cotes de clôture présentes pour {closing_pct:.0f} % des matchs.",
                "La comparaison au marché ne portera que sur ces matchs.",
            )
        extreme = [m for m in fin if (m.home_score or 0) + (m.away_score or 0) >= 10]
        if extreme:
            add(
                "warning",
                f"{label} : {len(extreme)} score(s) très élevé(s) (≥ 10 buts au total).",
                "Vérifiez ces matchs : faute de frappe possible.",
            )
    future_done = [
        m
        for m in matches
        if m.status == MatchStatus.FINISHED and m.kickoff_at > now + timedelta(days=1)
    ]
    if future_done:
        add(
            "error",
            f"{len(future_done)} match(s) « terminé(s) » avec une date dans le futur.",
            "Corrigez la date ou le statut.",
        )
    last = max((m.kickoff_at for m in matches if m.status == MatchStatus.FINISHED), default=None)
    fresh_days = (now - last).days if last else None
    if fresh_days is not None and fresh_days > 14:
        add(
            "info",
            f"Dernier résultat enregistré il y a {fresh_days} jours.",
            "Utilisez « Mettre à jour » ou vérifiez si la saison est terminée.",
        )
    upcoming = [m for m in matches if m.status == MatchStatus.SCHEDULED and m.kickoff_at > now]
    if upcoming and sum(m.id in pre for m in upcoming) < len(upcoming) * 0.5:
        add(
            "info",
            f"{len(upcoming)} match(s) à venir, dont {sum(m.id in pre for m in upcoming)} avec cotes.",
            "Sans cotes, aucune valeur espérée n'est calculée ; saisissez-les ou mettez à jour.",
        )
    dups = duplicate_suggestions(db)
    inside = {t for m in matches for t in (m.home_team_id, m.away_team_id)}
    mine = [d for d in dups if d["a"]["id"] in inside or d["b"]["id"] in inside]
    if mine:
        add(
            "warning",
            f"{len(mine)} paire(s) d'équipes qui se ressemblent (doublons possibles).",
            "Centre de données > Équipes : fusionnez-les si c'est la même équipe.",
        )
    teams_low = defaultdict(int)
    for m in matches:
        teams_low[m.home_team_id] += 1
        teams_low[m.away_team_id] += 1
    if matches and (low := [t for t, n in teams_low.items() if n < 5]):
        add(
            "info",
            f"{len(low)} équipe(s) avec moins de 5 matchs : pas de prédiction pour elles.",
            "Normal pour une équipe promue en début de saison.",
        )
    return {
        "competition": next(iter(comps.values())).name if comps else None,
        "seasons": seasons,
        "issues": issues,
        "counts": {
            lvl: sum(i["level"] == lvl for i in issues) for lvl in ("error", "warning", "info")
        },
        "last_result_days": fresh_days,
        "upcoming": len(upcoming),
    }
