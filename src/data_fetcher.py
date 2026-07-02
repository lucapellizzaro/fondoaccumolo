"""Scarica i prezzi storici giornalieri da Binance (API pubblica) con cache locale.

Si usa l'endpoint pubblico `data-api.binance.vision` (market data, nessuna API key,
nessuna restrizione geografica). Rispetto a CoinGecko gratuito permette di scaricare
TUTTO lo storico disponibile (da ~2017 per BTC), indispensabile per vedere piu' cicli
di halving. La cache evita di ribattere le API a ogni refresh e consente l'uso offline.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

from . import config

CACHE_DIR = Path(__file__).resolve().parent.parent / "data"
CACHE_DIR.mkdir(exist_ok=True)

BINANCE_URL = "https://data-api.binance.vision/api/v3/klines"
START_MS = int(datetime(2017, 1, 1).timestamp() * 1000)  # prima dei dati disponibili
MAX_LIMIT = 1000                                          # candele per richiesta (max Binance)
CACHE_TTL = timedelta(hours=6)                            # i dati giornalieri cambiano poco


def _cache_path(coin_id: str) -> Path:
    return CACHE_DIR / f"{coin_id}.parquet"


def _cache_is_fresh(path: Path) -> bool:
    if not path.exists():
        return False
    age = datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)
    return age < CACHE_TTL


def _download_klines(symbol: str) -> pd.DataFrame:
    """Scarica tutte le candele giornaliere paginando a blocchi da 1000."""
    rows: list[list] = []
    start = START_MS
    while True:
        params = {"symbol": symbol, "interval": "1d", "limit": MAX_LIMIT, "startTime": start}
        resp = requests.get(BINANCE_URL, params=params, timeout=30)
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < MAX_LIMIT:
            break
        # La prossima pagina parte dalla candela successiva all'ultima ricevuta.
        start = batch[-1][0] + 1
        time.sleep(0.2)  # gentile col rate-limit

    if not rows:
        raise RuntimeError(f"Nessun dato restituito da Binance per {symbol}")

    # Colonne klines Binance: openTime, open, high, low, close, volume, ...
    df = pd.DataFrame(rows, columns=[
        "openTime", "open", "high", "low", "close", "volume",
        "closeTime", "qv", "trades", "tbb", "tbq", "ignore",
    ])
    df["date"] = pd.to_datetime(df["openTime"], unit="ms").dt.normalize()
    df["price"] = df["close"].astype(float)
    df["volume"] = df["volume"].astype(float)
    df = df[["date", "price", "volume"]].drop_duplicates(subset="date", keep="last")
    return df.set_index("date").sort_index()


STATIC_DIR = Path(__file__).resolve().parent.parent / "data" / "static"


def _load_static_prefix(coin_id: str) -> pd.DataFrame | None:
    """Carica lo storico statico pre-2017 (se presente) per estendere indietro la serie.

    I prezzi vecchi sono storia immutabile: li teniamo come CSV versionato nel repo
    (es. BTC da blockchain.info) per coprire gli halving precedenti all'inizio di Binance.
    """
    path = STATIC_DIR / f"{coin_id}_pre2017.csv"
    if not path.exists():
        return None
    sp = pd.read_csv(path, parse_dates=["date"])
    sp["date"] = sp["date"].dt.normalize()
    sp["volume"] = float("nan")  # le fonti storiche non forniscono volume comparabile
    return sp.set_index("date")[["price", "volume"]].sort_index()


def _splice_static(coin_id: str, df: pd.DataFrame) -> pd.DataFrame:
    """Antepone il prefisso statico (solo le date precedenti all'inizio della serie scaricata)."""
    prefix = _load_static_prefix(coin_id)
    if prefix is None:
        return df
    prefix = prefix[prefix.index < df.index.min()]
    if prefix.empty:
        return df
    return pd.concat([prefix, df]).sort_index()


def fetch_prices(coin_id: str, force: bool = False) -> pd.DataFrame:
    """Restituisce un DataFrame indicizzato per data con colonne: price, volume.

    Usa la cache locale se valida (TTL 6h); altrimenti scarica e aggiorna la cache.
    In caso di errore di rete ripiega sulla cache esistente, se presente. Se esiste uno
    storico statico pre-2017 per l'asset, viene anteposto (estende indietro la serie).
    """
    path = _cache_path(coin_id)
    if not force and _cache_is_fresh(path):
        return _splice_static(coin_id, pd.read_parquet(path))

    symbol = config.binance_symbol(coin_id)
    try:
        df = _download_klines(symbol)
    except requests.RequestException as exc:
        if path.exists():
            return _splice_static(coin_id, pd.read_parquet(path))
        raise RuntimeError(f"Impossibile scaricare {coin_id} ({symbol}): {exc}") from exc

    df.to_parquet(path)  # in cache salviamo solo la parte scaricata (Binance)
    return _splice_static(coin_id, df)


def fetch_many(coin_ids: list[str], force: bool = False) -> dict[str, pd.DataFrame]:
    return {cid: fetch_prices(cid, force=force) for cid in coin_ids}
