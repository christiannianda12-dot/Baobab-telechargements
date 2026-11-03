import pytest

from app.models import Competition, Match, ModelVersion, Odds, Prediction, Team
from app.models.mixins import utcnow


def test_prediction_is_immutable(db_session):
    c = Competition(name="C")
    a = Team(name="A")
    b = Team(name="B")
    mv = ModelVersion(name="poisson", version="0")
    db_session.add_all([c, a, b, mv])
    db_session.flush()
    m = Match(competition_id=c.id, home_team_id=a.id, away_team_id=b.id, kickoff_at=utcnow())
    db_session.add(m)
    db_session.flush()
    p = Prediction(
        match_id=m.id, model_version_id=mv.id, market="1X2", selection="home", probability=0.5
    )
    db_session.add(p)
    db_session.commit()
    p.probability = 0.9
    with pytest.raises(ValueError, match="ne peut pas être modifiée"):
        db_session.commit()
    db_session.rollback()


def test_foreign_keys_enforced(db_session):
    from sqlalchemy.exc import IntegrityError

    db_session.add(Match(competition_id=1, home_team_id=1, away_team_id=2, kickoff_at=utcnow()))
    with pytest.raises(IntegrityError):
        db_session.commit()


@pytest.mark.parametrize(
    "build",
    [
        lambda: Odds(match_id=1, bookmaker="b", market="1X2", selection="home", price=1.0),
        lambda: Prediction(
            match_id=1, model_version_id=1, market="1X2", selection="home", probability=1.5
        ),
    ],
)
def test_check_constraints_enforced_by_database(db_session, build):
    from sqlalchemy.exc import IntegrityError

    c = Competition(name="C")
    a, b = Team(name="A"), Team(name="B")
    mv = ModelVersion(name="m", version="0")
    db_session.add_all([c, a, b, mv])
    db_session.flush()
    db_session.add(
        Match(competition_id=c.id, home_team_id=a.id, away_team_id=b.id, kickoff_at=utcnow())
    )
    db_session.flush()
    db_session.add(build())
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_same_team_match_rejected_by_database(db_session):
    from sqlalchemy.exc import IntegrityError

    c, a = Competition(name="C"), Team(name="A")
    db_session.add_all([c, a])
    db_session.flush()
    db_session.add(
        Match(competition_id=c.id, home_team_id=a.id, away_team_id=a.id, kickoff_at=utcnow())
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
