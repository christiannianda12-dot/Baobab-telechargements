"""Déclencheurs SQL « append-only » : une prédiction (et son résultat) ne peut plus être modifiée ni supprimée,
même par du SQL brut. Même définition pour SQLite et PostgreSQL ; installés par create_all (tests) et par la
migration 0003 (copie figée de ces instructions)."""

from sqlalchemy import DDL, event

STATEMENTS = {
    "sqlite": [
        "CREATE TRIGGER IF NOT EXISTS trg_predictions_no_update BEFORE UPDATE ON predictions BEGIN SELECT RAISE(ABORT, 'predictions is append-only'); END",
        "CREATE TRIGGER IF NOT EXISTS trg_predictions_no_delete BEFORE DELETE ON predictions BEGIN SELECT RAISE(ABORT, 'predictions is append-only'); END",
        "CREATE TRIGGER IF NOT EXISTS trg_prediction_results_no_update BEFORE UPDATE ON prediction_results BEGIN SELECT RAISE(ABORT, 'prediction_results is append-only'); END",
        "CREATE TRIGGER IF NOT EXISTS trg_prediction_results_no_delete BEFORE DELETE ON prediction_results BEGIN SELECT RAISE(ABORT, 'prediction_results is append-only'); END",
    ],
    "postgresql": [
        "CREATE OR REPLACE FUNCTION predix_forbid_change() RETURNS trigger AS $body$ BEGIN RAISE EXCEPTION 'append-only table: % is immutable', TG_TABLE_NAME; END; $body$ LANGUAGE plpgsql",
        "CREATE TRIGGER trg_predictions_append_only BEFORE UPDATE OR DELETE ON predictions FOR EACH ROW EXECUTE FUNCTION predix_forbid_change()",
        "CREATE TRIGGER trg_prediction_results_append_only BEFORE UPDATE OR DELETE ON prediction_results FOR EACH ROW EXECUTE FUNCTION predix_forbid_change()",
    ],
}


def install(table) -> None:
    for dialect, stmts in STATEMENTS.items():
        for sql in stmts:
            if "CREATE TRIGGER" in sql and f" ON {table.name} " not in sql:
                continue  # déclencheur d'une autre table
            event.listen(
                table, "after_create", DDL(sql.replace("%", "%%")).execute_if(dialect=dialect)
            )
