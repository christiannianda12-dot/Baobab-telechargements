"""Assistant en mode « règles » : détecte l'intention, interroge les données et les modèles, rédige la réponse
à partir des seuls résultats calculés. Il ne produit aucun chiffre qui ne vienne pas du moteur."""

import re
import unicodedata
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import AnalysisHistory, Competition, Match, Team
from app.models.mixins import utcnow
from app.models.sports import MatchStatus
from app.services import combos
from app.services.form import head_to_head, match_analysis, team_form
from app.services.predict import build_prediction

NUMBERS = {"deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6}
HELP = (
    "Je peux : (1) analyser un match — « Analyse Équipe A contre Équipe B » ; (2) comparer deux équipes — « Compare A et B » ; "
    "(3) lister les marchés statistiquement les plus probables ou à valeur — « Quels sont les marchés les plus intéressants ? » ; "
    "(4) proposer un combiné — « Construis un combiné de trois rencontres en privilégiant les probabilités élevées »."
)


def norm(s: str) -> str:
    return re.sub(
        r"\s+",
        " ",
        "".join(
            c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn"
        ),
    ).strip()


def pct(p: float) -> str:
    return f"{p * 100:.1f} %".replace(".", ",")


def when(dt: datetime) -> str:
    return dt.strftime("%d/%m/%Y %H:%M UTC")


def find_teams(db: Session, message: str) -> list[Team]:
    text = f" {norm(message)} "
    spans = []
    for t in db.scalars(select(Team).limit(5000)):
        n = norm(t.name)
        if not n:
            continue
        m = re.search(rf"(?<![a-z0-9]){re.escape(n)}(?![a-z0-9])", text)
        if m:
            spans.append((m.start(), m.end(), t))
    spans.sort(key=lambda s: (s[0], -(s[1] - s[0])))
    kept, last_end = [], -1
    for st, en, t in spans:  # écarte les noms inclus dans un nom plus long
        if st >= last_end:
            kept.append(t)
            last_end = en
    return kept


def detect_intent(message: str, teams: list[Team]) -> str:
    n = norm(message)
    if "combin" in n or "ticket" in n:
        return "combo"
    if "compar" in n and len(teams) >= 2:
        return "compare"
    if "march" in n and (
        "interess" in n or "meilleur" in n or "value" in n or "valeur" in n or "probable" in n
    ):
        return "best_markets"
    if "analys" in n or " contre " in f" {n} " or " vs " in f" {n} " or len(teams) >= 1:
        return "analyze"
    return "help"


def pick_match(db: Session, teams: list[Team]) -> Match | None:
    now = utcnow()
    if len(teams) >= 2:
        a, b = teams[0].id, teams[1].id
        cond = or_(
            (Match.home_team_id == a) & (Match.away_team_id == b),
            (Match.home_team_id == b) & (Match.away_team_id == a),
        )
    elif len(teams) == 1:
        cond = or_(Match.home_team_id == teams[0].id, Match.away_team_id == teams[0].id)
    else:
        return None
    up = db.scalar(
        select(Match)
        .where(cond, Match.status == MatchStatus.SCHEDULED, Match.kickoff_at > now)
        .order_by(Match.kickoff_at)
        .limit(1)
    )
    return up or db.scalar(select(Match).where(cond).order_by(Match.kickoff_at.desc()).limit(1))


def _names(db: Session, m: Match) -> tuple[str, str, str]:
    return (
        db.get(Team, m.home_team_id).name,
        db.get(Team, m.away_team_id).name,
        db.get(Competition, m.competition_id).name,
    )


def _form_line(name: str, f: dict) -> str:
    if f["played"] == 0:
        return f"- {name} : aucun match terminé enregistré."
    return (
        f"- {name} : {f['played']} match(s), {f['wins']}V-{f['draws']}N-{f['losses']}D, buts {f['goals_for']}:{f['goals_against']} "
        f"(moy. {f['avg_goals_for']} marqués / {f['avg_goals_against']} encaissés), série récente {''.join(f['results'])}"
        + ("" if f["reliable"] else " — échantillon court, interprétation prudente")
        + "."
    )


def answer_analyze(db: Session, teams: list[Team]) -> dict:
    if not teams:
        known = [t.name for t in db.scalars(select(Team).order_by(Team.name).limit(15))]
        hint = (
            f" Équipes enregistrées (extrait) : {', '.join(known)}."
            if known
            else " Aucune équipe n'est enregistrée pour l'instant."
        )
        return {
            "answer": "Je n'ai pas identifié d'équipe connue dans votre message." + hint,
            "data": {},
            "sources": [],
        }
    m = pick_match(db, teams)
    if m is None:
        names = " et ".join(t.name for t in teams[:2])
        return {
            "answer": f"Aucun match enregistré pour {names}. Je ne peux pas produire d'analyse de match ; vous pouvez en saisir un dans Administration, "
            "ou me demander de comparer les deux équipes.",
            "data": {},
            "sources": [],
        }
    home, away, comp = _names(db, m)
    pred, ana = build_prediction(db, m), match_analysis(db, m)
    pred.pop("lambdas", None)
    lines = [f"**{home} – {away}** ({comp}, {when(m.kickoff_at)}, statut : {m.status.value})."]
    if pred["available"]:
        p = pred["probabilities"]
        lines += [
            f"Modèle {pred['model']['name']} v{pred['model']['version']}, {pred['training']['matches']} match(s) d'historique dans la compétition.",
            f"- 1X2 : {home} {pct(p['1X2']['home'])} · nul {pct(p['1X2']['draw'])} · {away} {pct(p['1X2']['away'])}.",
            f"- Plus de 2,5 buts {pct(p['OU']['2.5']['over'])} · moins de 2,5 buts {pct(p['OU']['2.5']['under'])} · les deux équipes marquent {pct(p['BTTS']['yes'])}.",
            f"- Buts attendus : {pred['expected_goals']['home']:.2f} – {pred['expected_goals']['away']:.2f}.",
        ]
        pos = [v for v in pred["value"] if v["expected_value"] > 0]
        if pred["value"]:
            lines.append(
                "Cotes saisies : "
                + (
                    ", ".join(
                        f"{v['market']} {v['selection']} à {v['price']} (valeur espérée {v['expected_value'] * 100:+.1f} %)"
                        for v in pos
                    )
                    if pos
                    else "aucun écart positif entre le modèle et les cotes saisies."
                )
            )
        else:
            lines.append("Aucune cote saisie : pas d'analyse de valeur.")
    else:
        lines.append(f"Je ne produis pas de probabilité : {pred['reason']}")
    lines.append("Forme (matchs antérieurs au coup d'envoi) :")
    lines += [
        _form_line(f"{home} (tous)", ana["home"]["overall"]),
        _form_line(f"{away} (tous)", ana["away"]["overall"]),
    ]
    h2h = ana["head_to_head"]
    lines.append(
        f"Confrontations directes : {h2h['played']} match(s)"
        + (
            f" — {home} {h2h['team_a_wins']}V, {h2h['draws']}N, {away} {h2h['team_b_wins']}V."
            if h2h["played"]
            else " enregistré."
        )
    )
    lines += [f"⚠ {w}" for w in ana["warnings"]]
    if pred["available"]:
        lines.append("Limites : " + " ".join(pred["limitations"]))
    return {
        "answer": "\n".join(lines),
        "data": {"match_id": m.id, "prediction": pred, "analysis": ana},
        "sources": [f"GET /matches/{m.id}/prediction", f"GET /matches/{m.id}/analysis"],
    }


def answer_compare(db: Session, teams: list[Team]) -> dict:
    a, b = teams[0], teams[1]
    now = utcnow()
    fa, fb = team_form(db, a.id, now), team_form(db, b.id, now)
    h2h = head_to_head(db, a.id, b.id, now)
    lines = [
        f"Comparaison **{a.name}** / **{b.name}** (10 derniers matchs terminés enregistrés) :",
        _form_line(a.name, fa),
        _form_line(b.name, fb),
    ]
    for k, label in (("corners", "corners"), ("shots", "tirs"), ("possession_pct", "possession %")):
        va, vb = fa["averages"][k], fb["averages"][k]
        if va["average"] is not None or vb["average"] is not None:
            lines.append(
                f"- Moyenne {label} : {a.name} {va['average'] if va['average'] is not None else 'n/d'} ({va['samples']} match(s) avec donnée) · "
                f"{b.name} {vb['average'] if vb['average'] is not None else 'n/d'} ({vb['samples']} match(s) avec donnée)."
            )
    lines.append(
        f"Confrontations directes : {h2h['played']} match(s)"
        + (
            f" — {a.name} {h2h['team_a_wins']}V, {h2h['draws']}N, {b.name} {h2h['team_b_wins']}V."
            if h2h["played"]
            else " enregistré."
        )
    )
    return {
        "answer": "\n".join(lines),
        "data": {"form": {a.name: fa, b.name: fb}, "head_to_head": h2h},
        "sources": ["services.form.team_form", "services.form.head_to_head"],
    }


def _upcoming_ids(db: Session, limit: int = 20) -> list[int]:
    q = (
        select(Match.id)
        .where(Match.status == MatchStatus.SCHEDULED, Match.kickoff_at > utcnow())
        .order_by(Match.kickoff_at)
        .limit(limit)
    )
    return list(db.scalars(q))


def answer_best_markets(db: Session, teams: list[Team]) -> dict:
    m = pick_match(db, teams) if teams else None
    ids = [m.id] if m else _upcoming_ids(db)
    rows, refused = [], []
    for mid in ids:
        mm = db.get(Match, mid)
        pred = build_prediction(db, mm)
        home, away, _ = _names(db, mm)
        if not pred["available"]:
            refused.append(f"{home} – {away} : {pred['reason']}")
            continue
        est = pred["probabilities"]
        for market, sel, line in combos.CANDIDATES:
            p = est["OU"][str(line)][sel] if market == "OU" else est[market][sel]
            ev = next(
                (
                    v["expected_value"]
                    for v in pred["value"]
                    if (v["market"], v["selection"], v["line"]) == (market, sel, line)
                ),
                None,
            )
            rows.append(
                {
                    "match_id": mid,
                    "match": f"{home} – {away}",
                    "label": f"{combos.describe(market, sel, line)} ({market})",
                    "probability": p,
                    "ev": ev,
                }
            )
    if not rows:
        why = "; ".join(refused) if refused else "Aucun match à venir enregistré."
        return {
            "answer": f"Je n'ai aucun marché à classer. {why}",
            "data": {"refused": refused},
            "sources": [],
        }
    top = sorted(rows, key=lambda r: -r["probability"])[:5]
    value = sorted(
        (r for r in rows if r["ev"] is not None and r["ev"] > 0), key=lambda r: -r["ev"]
    )[:5]
    lines = ["Marchés les plus **probables** selon le modèle :"] + [
        f"- {r['match']} : {r['label']} — {pct(r['probability'])}" for r in top
    ]
    lines.append(
        "Écarts positifs sur **cotes saisies** (valeur espérée) :"
        if value
        else "Aucune cote saisie ne présente d'écart positif avec le modèle."
    )
    lines += [
        f"- {r['match']} : {r['label']} — valeur espérée {r['ev'] * 100:+.1f} % (probabilité {pct(r['probability'])})"
        for r in value
    ]
    lines.append(
        "Une probabilité élevée n'est pas une valeur : sans cote, aucune rentabilité ne peut être évaluée. Voir le backtest pour la fiabilité du modèle."
    )
    lines += [f"Non évalué — {r}" for r in refused[:3]]
    return {
        "answer": "\n".join(lines),
        "data": {"top_probability": top, "value": value, "refused": refused},
        "sources": ["GET /matches/{id}/prediction"],
    }


def answer_combo(db: Session, message: str) -> dict:
    n = next((NUMBERS[w] for w in re.findall(r"[a-z0-9]+", norm(message)) if w in NUMBERS), 3)
    ids = _upcoming_ids(db, 30)
    if not ids:
        return {
            "answer": "Aucun match à venir n'est enregistré : je ne peux pas construire de combiné.",
            "data": {},
            "sources": [],
        }
    res = combos.suggest(db, ids, n)
    if not res["valid"]:
        sk = "; ".join(f"match {s['match_id']} : {s['reason']}" for s in res.get("skipped", [])[:3])
        return {
            "answer": f"Je ne peux pas construire un combiné de {n} rencontres. "
            + " ".join(res["problems"])
            + (f" Écartés : {sk}" if sk else ""),
            "data": res,
            "sources": [],
        }
    names = {
        leg["match_id"]: " – ".join(_names(db, db.get(Match, leg["match_id"]))[:2])
        for leg in res["legs"]
    }
    lines = [
        f"Combiné de {n} sélections (les plus probables du modèle, un seul marché par match) :"
    ]
    lines += [
        f"- {names[leg['match_id']]} : {leg['label']} — {pct(leg['probability'])}"
        + (f", cote saisie {leg['odds']}" if leg["odds"] else ", pas de cote saisie")
        for leg in res["legs"]
    ]
    lines.append(
        f"Probabilité conjointe estimée : {pct(res['joint_probability'])}"
        + (
            f" · cote totale {res['total_odds']:.2f} · valeur espérée {res['expected_value'] * 100:+.1f} %."
            if res["total_odds"]
            else "."
        )
    )
    lines += [f"⚠ {w}" for w in res["warnings"]]
    return {"answer": "\n".join(lines), "data": res, "sources": ["POST /combos/suggest"]}


def respond(db: Session, message: str, user_id: int | None) -> dict:
    teams = find_teams(db, message)
    intent = detect_intent(message, teams)
    if intent == "compare":
        out = answer_compare(db, teams)
    elif intent == "analyze":
        out = answer_analyze(db, teams)
    elif intent == "best_markets":
        out = answer_best_markets(db, teams)
    elif intent == "combo":
        out = answer_combo(db, message)
    else:
        out = {"answer": HELP, "data": {}, "sources": []}
    out.update(intent=intent, engine="rules", llm_enabled=False, teams=[t.name for t in teams])
    db.add(
        AnalysisHistory(
            user_id=user_id,
            kind="chat",
            query=message[:2000],
            payload={"intent": intent, "teams": out["teams"]},
        )
    )
    db.commit()
    return out
