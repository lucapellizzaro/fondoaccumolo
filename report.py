"""Report da riga di comando: stampa il verdetto per tutti gli asset (senza dashboard).

Uso:  python report.py            # tutti gli asset
      python report.py bitcoin    # un asset specifico
"""
from __future__ import annotations

import sys
from datetime import date

from src import config, indicators, onchain, scoring
from src.data_fetcher import fetch_prices
from src.halving import get_cycle_info


def run(coin_ids: list[str]) -> None:
    for cid in coin_ids:
        asset = next(a for a in config.ASSETS if a["id"] == cid)
        df = onchain.attach_fear_greed(indicators.enrich(fetch_prices(cid)))
        latest = df.iloc[-1]
        cycle = get_cycle_info(cid, asset["has_own_halving"], today=date.today())
        v = scoring.evaluate(latest, cycle)

        print(f"\n{'='*60}")
        print(f"{asset['name']} ({asset['symbol']})  —  {df.index.max().date()}")
        print(f"{'='*60}")
        print(f"  Prezzo: ${latest['price']:,.2f}   RSI: {latest['rsi']:.0f}")
        print(f"  Fase ciclo: {cycle.phase}")
        print(f"  VERDETTO: {v.emoji} {v.label}  ({v.total:.0f}/100)")
        for s in v.signals:
            print(f"    • {s.name}: {s.score:.0f}/{s.max_score:.0f} — {s.reason}")
    print(f"\n{'='*60}")
    print("Strumento educativo, non consulenza finanziaria. DYOR.")


if __name__ == "__main__":
    ids = sys.argv[1:] or [a["id"] for a in config.ASSETS]
    run(ids)
