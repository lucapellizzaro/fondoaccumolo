"""Pagina dashboard: backtest dello score + simulazione strategie di accumulo (DCA)."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src import backtest, config, indicators, onchain
from src.data_fetcher import fetch_prices

st.set_page_config(page_title="Backtest & DCA", page_icon="📈", layout="wide")

ZONE_COLORS = {"verde": "#2E7D32", "giallo": "#F9A825", "rosso": "#C62828"}


@st.cache_data(ttl=60 * 60 * 6, show_spinner="Calcolo score storico…")
def load_scored(coin_id: str, has_own: bool) -> pd.DataFrame:
    df = onchain.attach_fear_greed(indicators.enrich(fetch_prices(coin_id)))
    return backtest.compute_score_series(coin_id, has_own, df)


st.title("📈 Backtest dello score & simulazione DCA")
st.caption(
    "Due verifiche sui dati storici: **(1)** lo score ha valore predittivo? "
    "**(2)** come si comporterebbero diverse strategie di accumulo? "
    "**Risultati storici, non garanzia di rendimenti futuri.**"
)

with st.sidebar:
    names = {a["id"]: f'{a["name"]} ({a["symbol"]})' for a in config.ASSETS}
    coin_id = st.selectbox("Asset", options=list(names), format_func=lambda i: names[i])
    weekly = st.number_input("Rata settimanale (€)", min_value=10, max_value=5000, value=100, step=10)

asset = next(a for a in config.ASSETS if a["id"] == coin_id)
scored = load_scored(coin_id, asset["has_own_halving"])

# =====================================================================
# 1. Lo score funziona? — rendimenti futuri per zona
# =====================================================================
st.header("1 · Lo score ha funzionato?")
st.markdown(
    "Per ogni giorno storico classifichiamo la zona (🟢/🟡/🔴) e misuriamo il "
    "**rendimento del prezzo nei giorni successivi**. Se lo score ha valore, la zona "
    "verde dovrebbe mostrare rendimenti migliori della rossa."
)

fr = backtest.forward_returns(scored)
horizons = sorted(fr["horizon_days"].unique())
cols = st.columns(len(horizons))
for col, h in zip(cols, horizons):
    sub = fr[fr["horizon_days"] == h].set_index("zone")
    with col:
        st.markdown(f"**Orizzonte +{h} giorni**")
        for zone in ["verde", "giallo", "rosso"]:
            if zone in sub.index:
                r = sub.loc[zone]
                st.markdown(
                    f"<span style='color:{ZONE_COLORS[zone]}'>● **{zone.capitalize()}**</span> — "
                    f"medio **{r['mean_%']:+.1f}%**, mediano {r['median_%']:+.1f}%, "
                    f"win rate {r['win_rate_%']:.0f}% (n={int(r['n'])})",
                    unsafe_allow_html=True,
                )

# Grafico prezzo colorato per zona
st.subheader("Prezzo storico colorato per zona")
fig = go.Figure()
fig.add_trace(go.Scatter(x=scored.index, y=scored["price"], name="Prezzo",
                         line=dict(color="lightgray", width=1)))
for zone, color in ZONE_COLORS.items():
    mask = scored["zone"] == zone
    fig.add_trace(go.Scatter(
        x=scored.index[mask], y=scored["price"][mask], name=zone.capitalize(),
        mode="markers", marker=dict(color=color, size=3),
    ))
fig.update_yaxes(type="log")
fig.update_layout(height=420, hovermode="x unified", legend=dict(orientation="h"))
st.plotly_chart(fig, width="stretch")

# =====================================================================
# 2. Simulazione strategie DCA
# =====================================================================
st.header("2 · Simulazione strategie di accumulo")
st.markdown(
    f"A **parità di budget totale**, confrontiamo tre modi di investire "
    f"{weekly:.0f}€/settimana su {asset['name']} per tutto lo storico disponibile."
)

results = backtest.simulate_strategies(scored, float(weekly))

# Tabella riassuntiva
summary = pd.DataFrame([{
    "Strategia": r.name,
    "Investito €": f"{r.invested:,.0f}",
    "Valore finale €": f"{r.final_value:,.0f}",
    "ROI %": f"{r.roi_pct:+.1f}%",
    "Liquidità ferma €": f"{r.cash_left:,.0f}",
} for r in results])
st.dataframe(summary, width="stretch", hide_index=True)

# Curve di equity
fig2 = go.Figure()
for r in results:
    fig2.add_trace(go.Scatter(x=r.equity.index, y=r.equity.values, name=r.name))
fig2.update_layout(height=420, hovermode="x unified", legend=dict(orientation="h"),
                   yaxis_title="Valore portafoglio (€)")
st.plotly_chart(fig2, width="stretch")

best = max(results, key=lambda r: r.roi_pct)
st.success(f"📌 Su questo storico la strategia migliore per ROI è **{best.name}** "
           f"({best.roi_pct:+.1f}%). Nota: dipende fortemente dal periodo scelto.")

st.caption(
    "⚠️ Backtest su dati passati: un periodo diverso può ribaltare i risultati. "
    "Il DCA 'smart' aspetta le zone verdi, quindi può lasciare liquidità ferma e, in un "
    "mercato che sale presto, accumulare meno. Strumento educativo, non consulenza. DYOR."
)
