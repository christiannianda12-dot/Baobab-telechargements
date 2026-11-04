"""Planificateur interne : vérifie toutes les 5 minutes si un cycle d'automatisation est dû (instance unique)."""

import asyncio
import logging

from app.services import automation

log = logging.getLogger("predix.scheduler")


async def loop(factory, first_delay: float = 45.0, tick: float = 300.0):
    await asyncio.sleep(first_delay)
    while True:
        try:
            with factory() as db:
                due = automation.is_due(db)
            if due:
                await asyncio.to_thread(automation.run_cycle, factory, "auto")
        except Exception:  # noqa: BLE001 - le planificateur ne doit jamais s'arrêter
            log.exception("échec du planificateur")
        await asyncio.sleep(tick)
