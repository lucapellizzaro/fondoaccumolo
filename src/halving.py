"""Logica legata agli halving: ultimo evento, prossimo, giorni trascorsi, fase di ciclo.

Per le crypto senza halving proprio (es. ETH, SOL) si usa come riferimento
l'halving di Bitcoin, perche' storicamente il ciclo di mercato e' trainato da BTC.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from . import config


@dataclass
class CycleInfo:
    reference_coin: str           # da quale halving deriva la fase ("bitcoin"/"litecoin")
    last_halving: date | None
    next_halving: date | None
    days_since_last: int | None
    days_to_next: int | None
    phase: str                    # etichetta leggibile della fase di ciclo


def _last_and_next(coin_id: str, today: date) -> tuple[date | None, date | None]:
    dates = sorted(config.HALVING_DATES.get(coin_id, []))
    last = None
    for d in dates:
        if d <= today:
            last = d
    future = [d for d in dates if d > today]
    nxt = future[0] if future else config.NEXT_HALVING_ESTIMATE.get(coin_id)
    return last, nxt


def get_cycle_info(coin_id: str, has_own_halving: bool, today: date | None = None) -> CycleInfo:
    """Calcola la posizione nel ciclo di halving per un asset a una certa data."""
    today = today or date.today()
    reference = coin_id if has_own_halving else "bitcoin"

    last, nxt = _last_and_next(reference, today)
    days_since = (today - last).days if last else None
    days_to_next = (nxt - today).days if nxt else None

    phase = _phase_label(days_since, days_to_next)
    return CycleInfo(
        reference_coin=reference,
        last_halving=last,
        next_halving=nxt,
        days_since_last=days_since,
        days_to_next=days_to_next,
        phase=phase,
    )


def _phase_label(days_since: int | None, days_to_next: int | None) -> str:
    if days_since is None:
        return "sconosciuta"
    if days_since <= config.EUPHORIA_WINDOW_DAYS:
        return "post-halving (espansione iniziale)"
    if days_since <= config.BULL_WINDOW_DAYS:
        return "post-halving (espansione tardiva)"
    # Oltre la finestra rialzista: tipicamente fase di correzione / accumulo pre-halving.
    if days_to_next is not None and days_to_next <= 6 * 30:
        return "pre-halving (accumulo, halving vicino)"
    return "fuori finestra (mercato maturo / correzione)"
