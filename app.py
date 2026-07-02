"""Dashboard Streamlit: analisi del ciclo di halving e indicatore accumula/attendi/cautela.

Avvio:  streamlit run app.py
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from src import config, indicators, onchain, scoring
from src.data_fetcher import fetch_prices
from src.halving import get_cycle_info

st.set_page_config(page_title="Fondo Accumulo · Analisi Halving", page_icon="📊", layout="wide")


@st.cache_data(ttl=60 * 60 * 6, show_spinner=False)
def load_asset(coin_id: str) -> pd.DataFrame:
    """Scarica i prezzi e calcola gli indicatori (cache 6h)."""
    df = fetch_prices(coin_id)
    return onchain.attach_fear_greed(indicators.enrich(df))


@st.cache_data(ttl=60 * 60, show_spinner=False)
def load_global() -> dict:
    return onchain.fetch_global()


def asset_by_id(coin_id: str) -> dict:
    return next(a for a in config.ASSETS if a["id"] == coin_id)


# --------------------------------------------------------------------------- UI
st.title("📊 Fondo Accumulo — Analisi del ciclo di Halving")
st.caption(
    "Strumento **educativo** che combina la posizione nel ciclo di halving con indicatori "
    "tecnici (medie mobili, RSI) per dare un punteggio di contesto. **Non è consulenza "
    "finanziaria.**"
)

with st.sidebar:
    st.header("Impostazioni")
    names = {a["id"]: f'{a["name"]} ({a["symbol"]})' for a in config.ASSETS}
    coin_id = st.selectbox("Asset", options=list(names), format_func=lambda i: names[i])
    st.divider()
    st.markdown(
        "**Come leggere lo score**\n\n"
        "🟢 **ACCUMULA** — contesto storicamente favorevole\n\n"
        "🟡 **NEUTRO** — segnali misti, attendere conferme\n\n"
        "🔴 **CAUTELA** — contesto sfavorevole di breve"
    )

asset = asset_by_id(coin_id)

try:
    df = load_asset(coin_id)
except Exception as exc:  # noqa: BLE001
    st.error(f"Errore nel caricamento dati per {asset['name']}: {exc}")
    st.stop()

latest = df.iloc[-1]
cycle = get_cycle_info(coin_id, asset["has_own_halving"], today=date.today())
verdict = scoring.evaluate(latest, cycle)

# --------------------------------------------------------------- Riepilogo top
c1, c2, c3, c4 = st.columns([1.4, 1, 1, 1])
c1.metric("Verdetto", f'{verdict.emoji} {verdict.label}', help="Sintesi dei tre segnali")
c2.metric("Score", f"{verdict.total:.0f}/100")
c3.metric("Prezzo", f"${latest['price']:,.2f}")
rsi_val = latest.get("rsi")
c4.metric("RSI", f"{rsi_val:.0f}" if pd.notna(rsi_val) else "—")

# Conto alla rovescia halving
hc1, hc2, hc3 = st.columns(3)
hc1.metric("Riferimento ciclo", cycle.reference_coin.capitalize())
hc2.metric("Giorni dall'ultimo halving",
           f"{cycle.days_since_last}" if cycle.days_since_last is not None else "—")
hc3.metric("Giorni al prossimo (stima)",
           f"{cycle.days_to_next}" if cycle.days_to_next is not None else "—")
st.info(f"**Fase di ciclo:** {cycle.phase}")

# --------------------------------------------------------- Contesto on-chain
glob = load_global()
fng_val = latest.get("fng")
oc1, oc2, oc3 = st.columns(3)
oc1.metric("Fear & Greed", f"{fng_val:.0f}/100" if pd.notna(fng_val) else "—",
           help="Sentiment di mercato. Basso = paura (contrarian: occasione), alto = avidità (cautela)")
oc2.metric("Dominance BTC",
           f"{glob['btc_dominance']:.1f}%" if glob.get("btc_dominance") else "—",
           help="Quota di Bitcoin sul mercato cripto totale")
oc3.metric("Market cap totale",
           f"${glob['total_mcap_usd']/1e12:.2f}T" if glob.get("total_mcap_usd") else "—")

# --------------------------------------------------------- Dettaglio segnali
st.subheader("Perché questo punteggio")
for s in verdict.signals:
    pct = s.score / s.max_score if s.max_score else 0
    st.markdown(f"**{s.name}** — {s.score:.0f}/{s.max_score:.0f} punti")
    st.progress(min(max(pct, 0.0), 1.0))
    st.caption(s.reason)

# ----------------------------------------------------------------- Grafici
st.subheader("Prezzo, medie mobili e halving")
fig = make_subplots(
    rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05,
    subplot_titles=("Prezzo (USD, scala log) + SMA", "RSI"),
)
fig.add_trace(go.Scatter(x=df.index, y=df["price"], name="Prezzo", line=dict(color="#2962FF")), row=1, col=1)
fig.add_trace(go.Scatter(x=df.index, y=df[f"sma{config.SMA_SHORT}"], name=f"SMA{config.SMA_SHORT}",
                         line=dict(color="#FF9800", width=1)), row=1, col=1)
fig.add_trace(go.Scatter(x=df.index, y=df[f"sma{config.SMA_LONG}"], name=f"SMA{config.SMA_LONG}",
                         line=dict(color="#E53935", width=1)), row=1, col=1)

# Linee verticali sugli halving del riferimento
for d in config.HALVING_DATES.get(cycle.reference_coin, []):
    ts = pd.Timestamp(d)
    if ts >= df.index.min():
        fig.add_vline(x=ts, line=dict(color="gray", dash="dash"), row=1, col=1)

fig.add_trace(go.Scatter(x=df.index, y=df["rsi"], name="RSI", line=dict(color="#7B1FA2")), row=2, col=1)
fig.add_hline(y=config.RSI_OVERBOUGHT, line=dict(color="red", dash="dot"), row=2, col=1)
fig.add_hline(y=config.RSI_OVERSOLD, line=dict(color="green", dash="dot"), row=2, col=1)

fig.update_yaxes(type="log", row=1, col=1)
fig.update_layout(height=650, hovermode="x unified", legend=dict(orientation="h"))
st.plotly_chart(fig, width="stretch")

st.divider()
st.caption(
    "⚠️ I cicli di halving sono basati su pochissimi casi storici (3-4) e non garantiscono "
    "andamenti futuri. Questo strumento serve a studiare il contesto, non a prendere decisioni "
    "di investimento al posto tuo. Fai sempre le tue verifiche (DYOR)."
)
