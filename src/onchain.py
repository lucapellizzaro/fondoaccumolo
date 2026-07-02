"""Segnali on-chain / di sentiment da API gratuite.

- **Fear & Greed Index** (alternative.me): storico giornaliero dal 2018, 0-100.
  E' contrarian -> paura estrema = possibile occasione, avidita' = cautela.
  Avendo storico, entra sia nello score sia nel backtest.
- **Dati globali** (CoinGecko /global): dominance BTC e market cap totale.
  Solo valore attuale sul piano gratuito -> usato come contesto a display.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

CACHE_DIR = Path(__file__).resolve().parent.parent / "data"
CACHE_DIR.mkdir(exist_ok=True)

FNG_URL = "https://api.alternative.me/fng/"
GLOBAL_URL = "https://api.coingecko.com/api/v3/global"
FNG_CACHE = CACHE_DIR / "fear_greed.parquet"
CACHE_TTL = timedelta(hours=6)


def _cache_fresh(path: Path) -> bool:
    if not path.exists():
        return False
    return datetime.now() - datetime.fromtimestamp(path.stat().st_mtime) < CACHE_TTL


def fetch_fear_greed(force: bool = False) -> pd.DataFrame:
    """Storico completo del Fear & Greed Index, indicizzato per data.

    Colonne: fng (int 0-100), fng_class (etichetta testuale).
    """
    if not force and _cache_fresh(FNG_CACHE):
        return pd.read_parquet(FNG_CACHE)

    try:
        resp = requests.get(FNG_URL, params={"limit": 0, "format": "json"}, timeout=30)
        resp.raise_for_status()
        data = resp.json()["data"]
    except (requests.RequestException, KeyError, ValueError) as exc:
        if FNG_CACHE.exists():
            return pd.read_parquet(FNG_CACHE)
        raise RuntimeError(f"Impossibile scaricare Fear & Greed: {exc}") from exc

    df = pd.DataFrame(data)
    df["date"] = pd.to_datetime(df["timestamp"].astype(int), unit="s").dt.normalize()
    df["fng"] = df["value"].astype(int)
    df["fng_class"] = df["value_classification"]
    df = df[["date", "fng", "fng_class"]].drop_duplicates("date").set_index("date").sort_index()

    df.to_parquet(FNG_CACHE)
    return df


def attach_fear_greed(price_df: pd.DataFrame) -> pd.DataFrame:
    """Aggiunge la colonna `fng` al DataFrame dei prezzi (join per data).

    Le date prima dell'inizio del F&G (feb 2018) restano NaN: il motore di scoring
    le tratta come neutro.
    """
    try:
        fng = fetch_fear_greed()
    except RuntimeError:
        out = price_df.copy()
        out["fng"] = float("nan")
        return out
    out = price_df.join(fng[["fng"]], how="left")
    return out


def fetch_global() -> dict:
    """Dati globali attuali: dominance BTC/ETH e market cap totale (USD)."""
    try:
        resp = requests.get(GLOBAL_URL, timeout=20)
        resp.raise_for_status()
        d = resp.json()["data"]
        return {
            "btc_dominance": d["market_cap_percentage"].get("btc"),
            "eth_dominance": d["market_cap_percentage"].get("eth"),
            "total_mcap_usd": d["total_market_cap"].get("usd"),
        }
    except (requests.RequestException, KeyError, ValueError):
        return {"btc_dominance": None, "eth_dominance": None, "total_mcap_usd": None}
