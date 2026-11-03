"""historique vérifiable : unicité des prédictions et tables append-only

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

# Copie FIGÉE (ne pas importer le code applicatif : une migration ne doit jamais changer de sens).
SQLITE = [
    "CREATE TRIGGER IF NOT EXISTS trg_predictions_no_update BEFORE UPDATE ON predictions BEGIN SELECT RAISE(ABORT, 'predictions is append-only'); END",
    "CREATE TRIGGER IF NOT EXISTS trg_predictions_no_delete BEFORE DELETE ON predictions BEGIN SELECT RAISE(ABORT, 'predictions is append-only'); END",
    "CREATE TRIGGER IF NOT EXISTS trg_prediction_results_no_update BEFORE UPDATE ON prediction_results BEGIN SELECT RAISE(ABORT, 'prediction_results is append-only'); END",
    "CREATE TRIGGER IF NOT EXISTS trg_prediction_results_no_delete BEFORE DELETE ON prediction_results BEGIN SELECT RAISE(ABORT, 'prediction_results is append-only'); END",
]
PG = [
    "CREATE OR REPLACE FUNCTION predix_forbid_change() RETURNS trigger AS $body$ BEGIN RAISE EXCEPTION 'append-only table: % is immutable', TG_TABLE_NAME; END; $body$ LANGUAGE plpgsql",
    "CREATE TRIGGER trg_predictions_append_only BEFORE UPDATE OR DELETE ON predictions FOR EACH ROW EXECUTE FUNCTION predix_forbid_change()",
    "CREATE TRIGGER trg_prediction_results_append_only BEFORE UPDATE OR DELETE ON prediction_results FOR EACH ROW EXECUTE FUNCTION predix_forbid_change()",
]


def upgrade() -> None:
    with op.batch_alter_table("model_versions") as b:
        b.create_unique_constraint("uq_model_versions_name_version", ["name", "version"])
    op.execute(
        sa.text(
            "CREATE UNIQUE INDEX uq_predictions_slot ON predictions "
            "(match_id, model_version_id, market, selection, COALESCE(line, -1))"
        )
    )
    stmts = SQLITE if op.get_bind().dialect.name == "sqlite" else PG
    for s in stmts:
        op.execute(sa.text(s))


def downgrade() -> None:
    d = op.get_bind().dialect.name
    for t in ("predictions", "prediction_results"):
        if d == "sqlite":
            for ev in ("update", "delete"):
                op.execute(sa.text(f"DROP TRIGGER IF EXISTS trg_{t}_no_{ev}"))
        else:
            op.execute(sa.text(f"DROP TRIGGER IF EXISTS trg_{t}_append_only ON {t}"))
    if d != "sqlite":
        op.execute(sa.text("DROP FUNCTION IF EXISTS predix_forbid_change()"))
    op.execute(sa.text("DROP INDEX uq_predictions_slot"))
    with op.batch_alter_table("model_versions") as b:
        b.drop_constraint("uq_model_versions_name_version", type_="unique")
