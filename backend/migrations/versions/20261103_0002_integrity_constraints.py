"""contraintes d'intégrité (cotes > 1, scores >= 0, probabilités dans [0,1], ...)

Alembic ne détecte pas les CHECK : migration écrite à la main (mode batch pour SQLite).

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

# (table, nom court, condition). On passe le NOM COURT : la convention de nommage
# ajoute le préfixe ck_<table>_ (le nom final en base est ck_<table>_<nom>).
CHECKS = [
    ("odds", "price_gt_1", "price > 1"),
    ("matches", "distinct_teams", "home_team_id <> away_team_id"),
    ("matches", "home_score_pos", "home_score IS NULL OR home_score >= 0"),
    ("matches", "away_score_pos", "away_score IS NULL OR away_score >= 0"),
    (
        "match_statistics",
        "possession_range",
        "possession_pct IS NULL OR (possession_pct BETWEEN 0 AND 100)",
    ),
    ("predictions", "probability_range", "probability BETWEEN 0 AND 1"),
    ("predictions", "observed_odds_gt_1", "observed_odds IS NULL OR observed_odds > 1"),
]


def upgrade() -> None:
    for table in sorted({t for t, _, _ in CHECKS}):
        with op.batch_alter_table(table) as batch:
            for t, name, cond in CHECKS:
                if t == table:
                    batch.create_check_constraint(name, sa.text(cond))


def downgrade() -> None:
    for table in sorted({t for t, _, _ in CHECKS}):
        with op.batch_alter_table(table) as batch:
            for t, name, _ in CHECKS:
                if t == table:
                    batch.drop_constraint(name, type_="check")
