"""Configurazione centrale: asset monitorati, date di halving e soglie del motore a regole.

Tutti i parametri "magici" del progetto vivono qui, cosi' la logica resta pulita
e le soglie si possono tarare senza toccare il codice.
"""
from __future__ import annotations

from datetime import date

# ---------------------------------------------------------------------------
# Asset monitorati
# ---------------------------------------------------------------------------
# `id` deve corrispondere all'id CoinGecko (es. https://www.coingecko.com/en/coins/bitcoin).
# `has_own_halving`: True solo per le crypto che hanno un proprio evento di halving.
# Le altre ereditano la fase di ciclo dall'halving di Bitcoin (BTC fa da traino).
ASSETS: list[dict] = [
    {"id": "bitcoin", "symbol": "BTC", "name": "Bitcoin", "binance": "BTCUSDT", "has_own_halving": True},
    {"id": "litecoin", "symbol": "LTC", "name": "Litecoin", "binance": "LTCUSDT", "has_own_halving": True},
    {"id": "ethereum", "symbol": "ETH", "name": "Ethereum", "binance": "ETHUSDT", "has_own_halving": False},
    {"id": "solana", "symbol": "SOL", "name": "Solana", "binance": "SOLUSDT", "has_own_halving": False},
    {"id": "cardano", "symbol": "ADA", "name": "Cardano", "binance": "ADAUSDT", "has_own_halving": False},
    {"id": "binancecoin", "symbol": "BNB", "name": "BNB", "binance": "BNBUSDT", "has_own_halving": False},
    {"id": "ripple", "symbol": "XRP", "name": "XRP", "binance": "XRPUSDT", "has_own_halving": False},
]


def binance_symbol(coin_id: str) -> str:
    return next(a["binance"] for a in ASSETS if a["id"] == coin_id)

# ---------------------------------------------------------------------------
# Date di halving note (storiche + ultima certa). Fonte: dati on-chain pubblici.
# ---------------------------------------------------------------------------
HALVING_DATES: dict[str, list[date]] = {
    "bitcoin": [
        date(2012, 11, 28),
        date(2016, 7, 9),
        date(2020, 5, 11),
        date(2024, 4, 20),
    ],
    "litecoin": [
        date(2015, 8, 25),
        date(2019, 8, 5),
        date(2023, 8, 2),
    ],
}

# Stima del prossimo halving (BTC ~ ogni 4 anni). Usata solo per il conto alla rovescia.
NEXT_HALVING_ESTIMATE: dict[str, date] = {
    "bitcoin": date(2028, 4, 1),
    "litecoin": date(2027, 8, 1),
}

# ---------------------------------------------------------------------------
# Soglie del motore a regole (scoring.py)
# ---------------------------------------------------------------------------
# Finestra storicamente rialzista dopo l'halving, espressa in giorni.
BULL_WINDOW_DAYS = 18 * 30          # ~18 mesi: fase di tipica espansione post-halving
EUPHORIA_WINDOW_DAYS = 12 * 30      # primi ~12 mesi: parte piu' forte del ciclo
PRE_HALVING_WINDOW_DAYS = 6 * 30    # ultimi ~6 mesi prima del prossimo halving

# Moltiplicatori del peso "cycle" per ciascuna fase (usati da scoring e calendario).
CYCLE_PHASE_MULT = {
    "euphoria": 1.0,      # primi ~12 mesi post-halving
    "late_bull": 0.7,     # 12-18 mesi post-halving
    "pre_halving": 0.6,   # ultimi ~6 mesi prima del prossimo halving
    "out": 0.25,          # fuori dalle finestre tipiche
}

RSI_OVERSOLD = 30                   # sotto = ipervenduto (possibile occasione)
RSI_OVERBOUGHT = 70                 # sopra = ipercomprato (cautela)

SMA_LONG = 200                      # media mobile di lungo periodo (giorni)
SMA_SHORT = 50

# Pesi dei singoli segnali nello score finale (somma teorica = 100).
WEIGHTS = {
    "cycle": 35,       # posizione nel ciclo di halving
    "trend": 25,       # prezzo sopra/sotto le medie mobili
    "momentum": 20,    # RSI
    "sentiment": 20,   # Fear & Greed Index (contrarian)
}

# Soglie del Fear & Greed Index (0-100). Contrarian: paura = occasione, avidita' = cautela.
FNG_EXTREME_FEAR = 25     # <= => paura estrema (storicamente buon momento per accumulare)
FNG_EXTREME_GREED = 75    # >= => avidita' estrema (cautela)

# Soglie del semaforo finale (score 0-100).
SCORE_BUY = 65        # >= => 🟢 fase di accumulo
SCORE_WAIT = 40       # tra WAIT e BUY => 🟡 attendi/neutro ; sotto => 🔴 cautela
