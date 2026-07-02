"""Pagina dashboard: vista comparativa di tutti gli asset, ordinati per score."""
from __future__ import annotations

from datetime import date

import plotly.graph_objects as go
import streamlit as st

from src import config
from src.compare import build_overview

st.set_page_config(page_title="Confronto Asset", page_icon="🔭", layout="wide")

ZONE_COLORS = {"verde": "#2E7D32", "giallo": "#F9A825", "rosso": "#C62828"}


@st.cache_data(ttl=60 * 60 * 6, show_spinner="Carico tutti gli asset…")
def load_overview() -> "pd.DataFrame":  # noqa: F821
    return build_overview(today=date.today())


st.title("🔭 Confronto multi-asset")
st.caption(
    "Stato attuale di tutti gli asset monitorati, ordinati per score. "
    "Colpo d'occhio su dove il contesto è oggi più favorevole. "
    "**Strumento educativo, non consulenza finanziaria.**"
)

df = load_overview()

# --- Riepilogo a colpo d'occhio -------------------------------------------
counts = df["zone"].value_counts()
c1, c2, c3 = st.columns(3)
c1.metric("🟢 In accumulo", int(counts.get("verde", 0)))
c2.metric("🟡 Neutri", int(counts.get("giallo", 0)))
c3.metric("🔴 In cautela", int(counts.get("rosso", 0)))

# --- Grafico a barre score per asset --------------------------------------
st.subheader("Score per asset")
fig = go.Figure(go.Bar(
    x=df["score"],
    y=[f'{r.emoji} {r["name"]} ({r["symbol"]})' for _, r in df.iterrows()],
    orientation="h",
    marker_color=[ZONE_COLORS[z] for z in df["zone"]],
    text=[f'{s:.0f}' for s in df["score"]],
    textposition="outside",
))
fig.add_vline(x=config.SCORE_BUY, line=dict(color="green", dash="dot"),
              annotation_text="🟢 accumula")
fig.add_vline(x=config.SCORE_WAIT, line=dict(color="orange", dash="dot"),
              annotation_text="🟡 attendi")
fig.update_layout(height=80 + 55 * len(df), xaxis_title="Score (0-100)",
                  yaxis=dict(autorange="reversed"), xaxis_range=[0, 100])
st.plotly_chart(fig, width="stretch")

# --- Tabella dettagliata ---------------------------------------------------
st.subheader("Dettaglio")
table = df.copy()
table["Verdetto"] = table["emoji"] + " " + table["label"]
table["Prezzo"] = table["price"].map(lambda p: f"${p:,.2f}")
table["Score"] = table["score"].map(lambda s: f"{s:.0f}")
table["RSI"] = table["rsi"].map(lambda r: f"{r:.0f}" if r == r else "—")
table["vs SMA200"] = table["dist_sma200_%"].map(
    lambda d: f"{d:+.0f}%" if d == d else "—")
table["Giorni da halving"] = table["days_since_halving"].map(
    lambda d: f"{int(d)}" if d == d and d is not None else "—")
table = table.rename(columns={"name": "Asset", "symbol": "Sigla", "phase": "Fase ciclo"})

st.dataframe(
    table[["Asset", "Sigla", "Verdetto", "Score", "Prezzo", "RSI",
           "vs SMA200", "Giorni da halving", "Fase ciclo"]],
    width="stretch", hide_index=True,
)

st.caption(
    "ℹ️ *vs SMA200* = scostamento % del prezzo dalla media mobile a 200 giorni "
    "(negativo = sotto la media, possibile sconto rispetto al trend di lungo periodo). "
    "Le crypto senza halving proprio ereditano la fase di ciclo da Bitcoin."
)
