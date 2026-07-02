"""Indicatori tecnici implementati direttamente in pandas (niente dipendenze esterne).

Sono i classici usati dagli analisti: medie mobili, RSI e MACD. Implementarli a
mano (poche righe ciascuno) ci rende indipendenti da librerie fragili e rende
trasparente il calcolo dietro lo score.
"""
from __future__ import annotations

import pandas as pd

from . import config


def sma(series: pd.Series, window: int) -> pd.Series:
    """Media mobile semplice."""
    return series.rolling(window=window, min_periods=window).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index (metodo di Wilder con media esponenziale).

    Valori: 0-100. <30 ipervenduto, >70 ipercomprato.
    """
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """MACD, linea di segnale e istogramma."""
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return pd.DataFrame(
        {"macd": macd_line, "signal": signal_line, "hist": macd_line - signal_line}
    )


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    """Aggiunge al DataFrame dei prezzi tutte le colonne degli indicatori."""
    out = df.copy()
    out[f"sma{config.SMA_SHORT}"] = sma(out["price"], config.SMA_SHORT)
    out[f"sma{config.SMA_LONG}"] = sma(out["price"], config.SMA_LONG)
    out["rsi"] = rsi(out["price"])
    macd_df = macd(out["price"])
    out = out.join(macd_df)
    return out
