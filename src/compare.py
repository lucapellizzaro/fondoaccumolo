"""Vista comparativa multi-asset: lo stato attuale di tutti gli asset in un colpo d'occhio.

Costruisce una tabella con verdetto, score e metriche chiave per ogni asset, cosi'
si individua subito dove c'e' il contesto piu' favorevole oggi.
"""
from __future__ import annotations

from datetime import date

import pandas as pd

from . import config, indicators, onchain, scoring
from .data_fetcher import fetch_prices
from .halving import get_cycle_info


def build_overview(coin_ids: list[str] | None = None, today: date | None = None) -> pd.DataFrame:
    """Restituisce un DataFrame (una riga per asset) ordinato per score decrescente.

    Colonne: name, symbol, score, label, emoji, zone, price, rsi, dist_sma200_%,
    days_since_halving, phase.
    """
    today = today or date.today()
    assets = config.ASSETS if coin_ids is None else [
        a for a in config.ASSETS if a["id"] in coin_ids
    ]

    rows = []
    for asset in assets:
        df = onchain.attach_fear_greed(indicators.enrich(fetch_prices(asset["id"])))
        latest = df.iloc[-1]
        cycle = get_cycle_info(asset["id"], asset["has_own_halving"], today=today)
        v = scoring.evaluate(latest, cycle)

        sma200 = latest.get(f"sma{config.SMA_LONG}")
        dist = (latest["price"] / sma200 - 1) * 100 if pd.notna(sma200) else float("nan")
        zone = "verde" if v.total >= config.SCORE_BUY else (
            "giallo" if v.total >= config.SCORE_WAIT else "rosso")

        rows.append({
            "name": asset["name"],
            "symbol": asset["symbol"],
            "score": v.total,
            "label": v.label,
            "emoji": v.emoji,
            "zone": zone,
            "price": latest["price"],
            "rsi": latest.get("rsi"),
            "dist_sma200_%": dist,
            "days_since_halving": cycle.days_since_last,
            "phase": cycle.phase,
        })

    out = pd.DataFrame(rows).sort_values("score", ascending=False, ignore_index=True)
    return out
