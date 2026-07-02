"""Motore a regole: combina ciclo di halving + trend + momentum in uno score 0-100.

Principio guida: NIENTE scatola nera. Ogni segnale contribuisce con un punteggio
e una spiegazione testuale, cosi' l'utente capisce *perche'* lo strumento suggerisce
accumulo, attesa o cautela. E' uno strumento di supporto, non un ordine di trading.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from . import config
from .halving import CycleInfo


@dataclass
class Signal:
    name: str
    score: float          # contributo 0..peso del segnale
    max_score: float
    reason: str           # spiegazione leggibile


@dataclass
class Verdict:
    total: float                      # 0-100
    label: str                        # ACCUMULA / NEUTRO / CAUTELA
    emoji: str
    signals: list[Signal] = field(default_factory=list)


def _cycle_signal(cycle: CycleInfo) -> Signal:
    w = config.WEIGHTS["cycle"]
    d = cycle.days_since_last
    if d is None:
        return Signal("Ciclo halving", w * 0.5, w, "Fase di ciclo sconosciuta: punteggio neutro.")

    if d <= config.EUPHORIA_WINDOW_DAYS:
        return Signal("Ciclo halving", w, w,
                      f"Siamo a {d} giorni dall'halving di {cycle.reference_coin}: "
                      f"fase storicamente piu' rialzista (primi ~12 mesi).")
    if d <= config.BULL_WINDOW_DAYS:
        return Signal("Ciclo halving", w * 0.7, w,
                      f"{d} giorni dall'halving: espansione tardiva, storicamente ancora "
                      f"favorevole ma piu' avanti nel ciclo.")
    if cycle.days_to_next is not None and cycle.days_to_next <= 6 * 30:
        return Signal("Ciclo halving", w * 0.6, w,
                      f"Prossimo halving tra {cycle.days_to_next} giorni: fase di accumulo "
                      f"pre-halving, storicamente interessante per entrare gradualmente.")
    return Signal("Ciclo halving", w * 0.25, w,
                  f"{d} giorni dall'ultimo halving: fuori dalla finestra rialzista tipica, "
                  f"mercato piu' maturo/correttivo.")


def _trend_signal(row: pd.Series) -> Signal:
    w = config.WEIGHTS["trend"]
    price = row["price"]
    sma_long = row.get(f"sma{config.SMA_LONG}")
    sma_short = row.get(f"sma{config.SMA_SHORT}")

    if pd.isna(sma_long) or pd.isna(sma_short):
        return Signal("Trend (medie mobili)", w * 0.5, w,
                      "Storico insufficiente per le medie mobili: punteggio neutro.")

    above_long = price > sma_long
    above_short = price > sma_short
    if above_long and above_short:
        return Signal("Trend (medie mobili)", w, w,
                      f"Prezzo sopra SMA{config.SMA_SHORT} e SMA{config.SMA_LONG}: trend rialzista consolidato.")
    if above_long and not above_short:
        return Signal("Trend (medie mobili)", w * 0.65, w,
                      f"Prezzo sopra SMA{config.SMA_LONG} ma sotto SMA{config.SMA_SHORT}: "
                      f"trend di fondo positivo, debolezza di breve (possibile rientro).")
    if not above_long and above_short:
        return Signal("Trend (medie mobili)", w * 0.4, w,
                      f"Prezzo sotto SMA{config.SMA_LONG} ma sopra SMA{config.SMA_SHORT}: "
                      f"possibile inversione in corso, ancora da confermare.")
    return Signal("Trend (medie mobili)", w * 0.15, w,
                  f"Prezzo sotto entrambe le medie: trend ribassista, cautela.")


def _momentum_signal(row: pd.Series) -> Signal:
    w = config.WEIGHTS["momentum"]
    r = row.get("rsi")
    if pd.isna(r):
        return Signal("Momentum (RSI)", w * 0.5, w, "RSI non disponibile: punteggio neutro.")

    if r < config.RSI_OVERSOLD:
        return Signal("Momentum (RSI)", w, w,
                      f"RSI {r:.0f} (<{config.RSI_OVERSOLD}): ipervenduto, storicamente "
                      f"occasione di accumulo per chi ha orizzonte lungo.")
    if r > config.RSI_OVERBOUGHT:
        return Signal("Momentum (RSI)", w * 0.2, w,
                      f"RSI {r:.0f} (>{config.RSI_OVERBOUGHT}): ipercomprato, rischio di "
                      f"correzione di breve, meglio non inseguire il prezzo.")
    # Zona neutra: piu' vicini all'ipervenduto = leggermente meglio per accumulare.
    norm = 1 - (r - config.RSI_OVERSOLD) / (config.RSI_OVERBOUGHT - config.RSI_OVERSOLD)
    return Signal("Momentum (RSI)", w * (0.4 + 0.4 * norm), w,
                  f"RSI {r:.0f}: zona neutra, nessun eccesso evidente.")


def _sentiment_signal(row: pd.Series) -> Signal:
    w = config.WEIGHTS["sentiment"]
    f = row.get("fng")
    if f is None or pd.isna(f):
        return Signal("Sentiment (Fear & Greed)", w * 0.5, w,
                      "Fear & Greed non disponibile per questa data: punteggio neutro.")

    if f <= config.FNG_EXTREME_FEAR:
        return Signal("Sentiment (Fear & Greed)", w, w,
                      f"Fear & Greed {f:.0f}: paura estrema. Storicamente, quando tutti "
                      f"hanno paura e' un buon momento per accumulare (contrarian).")
    if f >= config.FNG_EXTREME_GREED:
        return Signal("Sentiment (Fear & Greed)", w * 0.15, w,
                      f"Fear & Greed {f:.0f}: avidita' estrema. Il mercato e' euforico, "
                      f"storicamente fase di maggior rischio di correzione.")
    # Zona intermedia: piu' vicini alla paura = leggermente meglio per accumulare.
    norm = 1 - (f - config.FNG_EXTREME_FEAR) / (config.FNG_EXTREME_GREED - config.FNG_EXTREME_FEAR)
    return Signal("Sentiment (Fear & Greed)", w * (0.35 + 0.45 * norm), w,
                  f"Fear & Greed {f:.0f}: sentiment neutro, nessun eccesso evidente.")


def evaluate(latest_row: pd.Series, cycle: CycleInfo) -> Verdict:
    """Calcola il verdetto finale combinando i quattro segnali."""
    signals = [
        _cycle_signal(cycle),
        _trend_signal(latest_row),
        _momentum_signal(latest_row),
        _sentiment_signal(latest_row),
    ]
    total = sum(s.score for s in signals)

    if total >= config.SCORE_BUY:
        label, emoji = "ACCUMULA", "🟢"
    elif total >= config.SCORE_WAIT:
        label, emoji = "NEUTRO / ATTENDI", "🟡"
    else:
        label, emoji = "CAUTELA", "🔴"

    return Verdict(total=round(total, 1), label=label, emoji=emoji, signals=signals)
