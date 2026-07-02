"""Logica legata agli halving: ultimo evento, prossimo, giorni trascorsi, fase di ciclo.

Per le crypto senza halving proprio (es. ETH, SOL) si usa come riferimento
l'halving di Bitcoin, perche' storicamente il ciclo di mercato e' trainato da BTC.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

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
    if days_to_next is not None and days_to_next <= config.PRE_HALVING_WINDOW_DAYS:
        return "pre-halving (accumulo, halving vicino)"
    return "fuori finestra (mercato maturo / correzione)"


@dataclass
class CycleWindow:
    start: date
    end: date
    label: str
    cycle_points: float   # punti del segnale ciclo in questa finestra (su WEIGHTS["cycle"])
    estimated: bool       # True se la finestra dipende dalla data stimata del prossimo halving


def cycle_calendar(reference_coin: str, today: date | None = None) -> list[CycleWindow]:
    """Calendario delle finestre del segnale ciclo, dall'ultimo halving noto in avanti.

    Solo il segnale ciclo e' prevedibile in anticipo (dipende dal calendario);
    trend, RSI e sentiment si sapranno solo il giorno stesso.
    """
    today = today or date.today()
    last, nxt = _last_and_next(reference_coin, today)
    if last is None:
        return []

    w = config.WEIGHTS["cycle"]
    mult = config.CYCLE_PHASE_MULT
    delta = timedelta

    windows = [
        CycleWindow(last, last + delta(days=config.EUPHORIA_WINDOW_DAYS),
                    "post-halving: espansione iniziale", w * mult["euphoria"], False),
        CycleWindow(last + delta(days=config.EUPHORIA_WINDOW_DAYS + 1),
                    last + delta(days=config.BULL_WINDOW_DAYS),
                    "post-halving: espansione tardiva", w * mult["late_bull"], False),
    ]
    if nxt is not None:
        pre_start = nxt - delta(days=config.PRE_HALVING_WINDOW_DAYS)
        estimated = nxt not in config.HALVING_DATES.get(reference_coin, [])
        out_start = last + delta(days=config.BULL_WINDOW_DAYS + 1)
        if pre_start > out_start:
            windows.append(CycleWindow(out_start, pre_start - delta(days=1),
                                       "fuori finestra: mercato maturo / correzione",
                                       w * mult["out"], estimated))
        windows.append(CycleWindow(pre_start, nxt - delta(days=1),
                                   "pre-halving: accumulo graduale", w * mult["pre_halving"], estimated))
        windows.append(CycleWindow(nxt, nxt + delta(days=config.EUPHORIA_WINDOW_DAYS),
                                   "post-halving: espansione iniziale (ciclo successivo)",
                                   w * mult["euphoria"], estimated))
    return windows
