import pytest

from app.models import Competition, Match, ModelVersion, Prediction, Team
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
