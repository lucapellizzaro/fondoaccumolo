"""Backtest dello score e simulazione di strategie di accumulo (DCA).

Due domande a cui rispondiamo con i dati storici:

1. **Lo score funziona?**  -> `forward_returns`: quando l'indicatore diceva 🟢/🟡/🔴,
   cosa e' successo davvero al prezzo nei 30/90/180 giorni successivi?

2. **Conviene accumulare cosi'?**  -> `simulate_strategies`: confronta lump sum,
   DCA classico e "DCA smart" (deploya la liquidita' accumulata solo in zona verde),
   a parita' di budget totale.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from . import config, scoring
from .halving import get_cycle_info


# ---------------------------------------------------------------------------
# 1. Serie storica dello score
# ---------------------------------------------------------------------------
def compute_score_series(coin_id: str, has_own_halving: bool, df: pd.DataFrame) -> pd.DataFrame:
    """Calcola score, label e zona per OGNI giorno dello storico.

    Per ogni data ricalcola la fase di ciclo *a quella data* (i giorni dall'halving
    cambiano nel tempo) e rivaluta il motore a regole. Restituisce il df arricchito
    con le colonne: score, label, zone.
    """
    scores, labels, zones = [], [], []
    for ts, row in df.iterrows():
        cycle = get_cycle_info(coin_id, has_own_halving, today=ts.date())
        v = scoring.evaluate(row, cycle)
        scores.append(v.total)
        labels.append(v.label)
        zones.append(_zone(v.total))

    out = df.copy()
    out["score"] = scores
    out["label"] = labels
    out["zone"] = zones
    return out


def _zone(score: float) -> str:
    if score >= config.SCORE_BUY:
        return "verde"
    if score >= config.SCORE_WAIT:
        return "giallo"
    return "rosso"


# ---------------------------------------------------------------------------
# 2. Rendimenti futuri condizionati alla zona
# ---------------------------------------------------------------------------
def forward_returns(df_scored: pd.DataFrame, horizons: list[int] | None = None) -> pd.DataFrame:
    """Per ogni zona e orizzonte, statistiche del rendimento successivo.

    Colonne risultanti: zone, horizon_days, n, mean_%, median_%, win_rate_%
    (win_rate = quota di casi con rendimento positivo).
    """
    horizons = horizons or [30, 90, 180]
    price = df_scored["price"]
    records = []
    for h in horizons:
        fwd = price.shift(-h) / price - 1.0  # rendimento a +h giorni
        tmp = pd.DataFrame({"zone": df_scored["zone"], "ret": fwd}).dropna()
        for zone, grp in tmp.groupby("zone"):
            records.append({
                "zone": zone,
                "horizon_days": h,
                "n": len(grp),
                "mean_%": round(grp["ret"].mean() * 100, 1),
                "median_%": round(grp["ret"].median() * 100, 1),
                "win_rate_%": round((grp["ret"] > 0).mean() * 100, 1),
            })
    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# 3. Simulazione strategie di accumulo
# ---------------------------------------------------------------------------
@dataclass
class StrategyResult:
    name: str
    invested: float          # capitale effettivamente investito
    cash_left: float         # liquidita' non ancora deployata (solo DCA smart)
    units: float             # quantita' di crypto accumulata
    final_value: float       # valore finale (units * prezzo finale + cash_left)
    roi_pct: float           # (final_value - invested) / invested
    equity: pd.Series        # valore del portafoglio nel tempo


def _equity_curve(df: pd.DataFrame, units_series: pd.Series, cash_series: pd.Series) -> pd.Series:
    return units_series * df["price"] + cash_series


def simulate_strategies(
    df_scored: pd.DataFrame,
    weekly_amount: float = 100.0,
) -> list[StrategyResult]:
    """Confronta tre strategie a PARITA' di budget totale.

    - **Lump sum**: tutto il budget investito il primo giorno.
    - **DCA classico**: `weekly_amount` investito ogni settimana, sempre.
    - **DCA smart (zona verde)**: ogni settimana accantona `weekly_amount`; deploya
      TUTTA la liquidita' accumulata solo quando la zona e' verde. Stesso budget,
      timing diverso.
    """
    df = df_scored
    # Punti di contribuzione settimanali (ogni 7 giorni di calendario disponibili).
    weekly = df.iloc[::7]
    n_weeks = len(weekly)
    total_budget = weekly_amount * n_weeks

    results = [
        _sim_lump_sum(df, total_budget),
        _sim_dca_classic(df, weekly, weekly_amount),
        _sim_dca_smart(df, weekly, weekly_amount),
    ]
    return results


def _sim_lump_sum(df: pd.DataFrame, budget: float) -> StrategyResult:
    entry_price = df["price"].iloc[0]
    units = budget / entry_price
    units_series = pd.Series(units, index=df.index)
    cash_series = pd.Series(0.0, index=df.index)
    equity = _equity_curve(df, units_series, cash_series)
    final = equity.iloc[-1]
    return StrategyResult("Lump sum (tutto subito)", budget, 0.0, units, final,
                          (final - budget) / budget * 100, equity)


def _sim_dca_classic(df: pd.DataFrame, weekly: pd.DataFrame, amount: float) -> StrategyResult:
    units = 0.0
    invested = 0.0
    units_by_date = {}
    for ts, row in weekly.iterrows():
        units += amount / row["price"]
        invested += amount
        units_by_date[ts] = units
    units_series = pd.Series(units_by_date).reindex(df.index, method="ffill").fillna(0.0)
    cash_series = pd.Series(0.0, index=df.index)
    equity = _equity_curve(df, units_series, cash_series)
    final = equity.iloc[-1]
    return StrategyResult("DCA classico (ogni settimana)", invested, 0.0, units, final,
                          (final - invested) / invested * 100, equity)


def _sim_dca_smart(df: pd.DataFrame, weekly: pd.DataFrame, amount: float) -> StrategyResult:
    units = 0.0
    cash = 0.0
    invested_target = 0.0  # quanto budget e' stato "stanziato" (per ROI a parita' di budget)
    units_by_date, cash_by_date = {}, {}
    for ts, row in weekly.iterrows():
        cash += amount               # accantona la rata settimanale
        invested_target += amount
        if row["zone"] == "verde" and cash > 0:
            units += cash / row["price"]   # deploya tutta la liquidita' accumulata
            cash = 0.0
        units_by_date[ts] = units
        cash_by_date[ts] = cash
    units_series = pd.Series(units_by_date).reindex(df.index, method="ffill").fillna(0.0)
    cash_series = pd.Series(cash_by_date).reindex(df.index, method="ffill").fillna(0.0)
    equity = _equity_curve(df, units_series, cash_series)
    final = equity.iloc[-1]
    # ROI calcolato sul budget stanziato (comprende la cash non ancora investita).
    roi = (final - invested_target) / invested_target * 100
    return StrategyResult("DCA smart (deploya in zona verde)", invested_target, cash, units,
                          final, roi, equity)
