# 📊 Fondo Accumulo — Analisi del ciclo di Halving

MVP per studiare le criptovalute nel contesto del **ciclo di halving**, combinando la
posizione nel ciclo con indicatori tecnici (medie mobili, RSI, MACD) per produrre un
punteggio trasparente **🟢 Accumula / 🟡 Neutro / 🔴 Cautela**.

> ⚠️ **Strumento educativo, NON consulenza finanziaria.** I cicli di halving si basano su
> pochissimi casi storici (2-4) e non garantiscono andamenti futuri. Fai sempre le tue
> verifiche (DYOR).

## Cosa fa

- Scarica lo storico prezzi giornaliero tramite l'API pubblica di **Binance** (da ~2017,
  nessuna chiave). Per Bitcoin antepone uno **storico statico pre-2017** (da blockchain.info,
  versionato in `data/static/`) così la serie BTC copre **tutti e 4 i cicli di halving** dal 2010.
- Calcola la **fase del ciclo di halving**: giorni dall'ultimo halving, conto alla rovescia
  al prossimo. Le crypto senza halving proprio (ETH, SOL, ADA…) ereditano la fase da Bitcoin.
- Calcola gli **indicatori tecnici** (SMA50/200, RSI, MACD) direttamente in pandas.
- Combina tutto in un **motore a regole** che spiega *perché* di ogni punteggio.
- Mostra il tutto in una **dashboard Streamlit** con grafici interattivi (Plotly).

## Struttura

```
app.py              # dashboard Streamlit — pagina principale (analisi live)
pages/
  1_📈_Backtest_e_DCA.py   # pagina: backtest score + simulazione strategie DCA
  2_🔭_Confronto_Asset.py  # pagina: vista comparativa multi-asset
report.py           # report da riga di comando (no UI)
src/
  config.py         # asset, date halving, soglie e pesi del motore
  data_fetcher.py   # download prezzi da Binance + cache locale (parquet)
  halving.py        # logica fase di ciclo
  indicators.py     # SMA, RSI, MACD in pandas
  scoring.py        # motore a regole -> score + spiegazioni
  backtest.py       # rendimenti futuri per zona + simulazione DCA
  compare.py        # tabella comparativa multi-asset
  onchain.py        # Fear & Greed Index + dati globali (dominance BTC)
data/               # cache prezzi (auto-generata, in .gitignore)
  static/           # storico pre-2017 VERSIONATO (es. bitcoin_pre2017.csv)
```

## Installazione

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Uso

Dashboard web:
```bash
streamlit run app.py
```
poi apri http://localhost:8501

Report da terminale:
```bash
python report.py            # tutti gli asset
python report.py bitcoin    # solo Bitcoin
```

## Come funziona lo score (0-100)

| Segnale | Peso | Logica |
|---|---|---|
| **Ciclo halving** | 35 | Massimo nei primi ~12 mesi post-halving; buono in accumulo pre-halving; basso "fuori finestra" |
| **Trend** | 25 | Prezzo sopra SMA50 e SMA200 = rialzista |
| **Momentum (RSI)** | 20 | RSI < 30 ipervenduto (occasione); RSI > 70 ipercomprato (cautela) |
| **Sentiment (Fear & Greed)** | 20 | Contrarian: paura estrema (≤25) = occasione; avidità estrema (≥75) = cautela |

Soglie semaforo: `>= 65` 🟢, `40–64` 🟡, `< 40` 🔴 (modificabili in `src/config.py`).

## Backtest & DCA (pagina "📈 Backtest e DCA")

- **Validazione dello score**: per ogni giorno storico misura il rendimento del prezzo a
  +30/90/180 giorni, raggruppato per zona 🟢/🟡/🔴. Mostra se la zona verde ha davvero
  reso più della rossa (win rate, media, mediana).
- **Simulazione strategie** a parità di budget: *lump sum*, *DCA classico*,
  *DCA smart* (deploya la liquidità accumulata solo in zona verde). Con curve di equity e ROI.

## Segnali on-chain / sentiment

- **Fear & Greed Index** (alternative.me, storico dal 2018): integrato nello score come
  segnale contrarian e mostrato in dashboard. Entra anche nel backtest.
- **Dominance BTC** e **market cap totale** (CoinGecko `/global`): contesto a display.

## Deploy online (Streamlit Community Cloud)

L'app è pensata per [share.streamlit.io](https://share.streamlit.io):

1. Pubblica la repo su GitHub (pubblica).
2. Su share.streamlit.io: **New app** → scegli la repo, branch `main`, main file `app.py`.
3. Nessun secret o configurazione richiesta (tutte le API usate sono pubbliche e senza chiave).

Al primo avvio la cache prezzi è vuota: il primo caricamento scarica tutto lo storico
(~1 minuto), poi la cache (TTL 6h) rende l'app veloce. Sul piano gratuito l'app va in
sleep dopo qualche giorno di inattività e si risveglia in ~30 secondi.

## Idee per estensioni future

- Altri segnali on-chain (MVRV, funding rate, flussi exchange).
- Alert via email/Telegram quando un asset entra in zona 🟢.
- Supporto a una API key CoinGecko Pro per storico completo (BTC dal 2013).
```
