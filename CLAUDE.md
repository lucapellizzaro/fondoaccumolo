# CLAUDE.md — contesto del progetto

## Cos'è
Dashboard Streamlit (multipagina) che analizza le crypto nel contesto del ciclo di
halving: score 0-100 trasparente (🟢 accumula / 🟡 neutro / 🔴 cautela) da 4 segnali
pesati — ciclo halving (35), trend SMA50/200 (25), RSI (20), Fear & Greed contrarian (20).
Vedi README.md per struttura e uso. Lingua del progetto e dell'utente: **italiano**.

## Stato (luglio 2026)
- Progetto completo e verificato a fondo (revisione del 2026-07-02): calcoli corretti
  (RSI Wilder, score, giorni dall'halving), date halving BTC/LTC esatte, backtest senza
  look-ahead bias, serie storica BTC continua dal 2010-08-18 senza buchi (CSV statico
  `data/static/bitcoin_pre2017.csv` + Binance da ago 2017). Nessun bug noto.
- Versioni: Python 3.9 nel venv locale (codice compatibile con versioni recenti grazie a
  `from __future__ import annotations`), Streamlit 1.50, pandas 2.x.

## Deploy (in corso)
- Decisione: pubblicare la repo su GitHub (pubblica) e fare il deploy su
  **share.streamlit.io** (Streamlit Community Cloud). Vercel scartato: non supporta
  server Python persistenti/WebSocket.
- L'utente sposta la cartella e crea lui la repo su GitHub; poi restano da fare:
  `git init`, commit, push, e deploy su share.streamlit.io (repo → main file `app.py`).
- Al primo avvio in cloud la cache `data/*.parquet` è vuota: il primo caricamento
  scarica tutto da Binance/alternative.me (~1 min), poi cache TTL 6h.
- `.gitignore` già corretto: esclude `.venv/` e `data/*.parquet`, versiona `data/static/`.

## Limiti noti / migliorie possibili (non bug)
- Nel backtest le medie a +180g sono dominate dagli outlier 2010-2013 (la zona gialla
  può battere la verde in media); mediana e win rate raccontano la storia giusta.
  Miglioria suggerita: selettore di data di inizio nella pagina Backtest.
- Lump sum su "tutto lo storico BTC" parte da $0.07 (2010) → ROI astronomico, confronto
  poco significativo senza filtro periodo.
- L'ultima candela Binance è quella odierna incompleta: score del giorno può variare.
- `NEXT_HALVING_ESTIMATE` in `src/config.py` va aggiornato dopo il 2027 (LTC) / 2028 (BTC),
  altrimenti il countdown diventa negativo.
- Finestre dei forward returns sovrapposte → statistiche descrittive, non test rigorosi.
