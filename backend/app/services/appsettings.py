"""Réglages persistants. Les secrets (clé d'API) ne sont jamais renvoyés : seulement « défini / non défini »."""

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import AppSetting

DEFAULTS = {
    "auto_enabled": "1",
    "auto_interval_hours": "6",
    "auto_record": "1",
    "auto_record_hours": "48",
    "odds_api_key": "",
    "odds_api_every_hours": "24",
    "odds_api_last_run": "",
    "odds_api_remaining": "",
}
SECRET = {"odds_api_key"}
INTERVALS = {1, 3, 6, 12, 24}


def get(db: Session, key: str) -> str:
    row = db.get(AppSetting, key)
    if row is not None:
        return row.value
    if key == "odds_api_key":
        return get_settings().odds_api_key  # variable d'environnement en repli
    return DEFAULTS.get(key, "")


def put(db: Session, key: str, value: str) -> None:
    row = db.get(AppSetting, key)
    if row is None:
        db.add(AppSetting(key=key, value=value))
    else:
        row.value = value
    db.commit()


def as_bool(db: Session, key: str) -> bool:
    return get(db, key) in ("1", "true", "True")


def as_int(db: Session, key: str, default: int) -> int:
    try:
        return int(get(db, key))
    except ValueError:
        return default


def public(db: Session) -> dict:
    return {
        "auto_enabled": as_bool(db, "auto_enabled"),
        "auto_interval_hours": as_int(db, "auto_interval_hours", 6),
        "auto_record": as_bool(db, "auto_record"),
        "auto_record_hours": as_int(db, "auto_record_hours", 48),
        "odds_api_key_set": bool(get(db, "odds_api_key").strip()),
        "odds_api_every_hours": as_int(db, "odds_api_every_hours", 24),
        "odds_api_remaining": get(db, "odds_api_remaining") or None,
    }
