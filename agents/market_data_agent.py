import pandas as pd
import yfinance as yf
import zmq
import time
import numpy as np
import json
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.logger import setup_logger

logger = setup_logger("MarketDataAgent", "logs/market_data_agent.log")

class MarketDataAgent:
    """Fetches historical market data from Yahoo Finance and sends it to other agents via ZeroMQ."""

    def __init__(self, tickers, port=5555, request_delay=0.05):
        self.tickers = tickers
        self.port = port
        self.request_delay = request_delay  # ✅ Enviar datos rápidamente (cada 0.05s)
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PUB)
        self.socket.bind(f"tcp://*:{port}")

    def fetch_historical_data(self, ticker):
        """Fetch historical market data from Yahoo Finance."""
        try:
            df = yf.download(ticker, period="60d", interval="1d", progress=False)  # ✅ Cargar 60 días de datos
            if df.empty:
                logger.warning(f"⚠️ No data returned for {ticker}.")
                return None

            # ✅ Calcular indicadores técnicos correctamente
            df["SMA_50"] = df["Close"].rolling(window=50, min_periods=1).mean()
            df["SMA_200"] = df["Close"].rolling(window=200, min_periods=1).mean()

            # ✅ Corrección de RSI para evitar errores ambiguos
            delta = df["Close"].diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = -delta.where(delta < 0, 0).rolling(14).mean()
            df["RSI"] = 100 - (100 / (1 + (gain / loss)))
            df["RSI"] = df["RSI"].fillna(50)

            df["MACD"] = df["Close"].ewm(span=12, adjust=False).mean() - df["Close"].ewm(span=26, adjust=False).mean()
            df["ATR"] = df["High"].rolling(14).max() - df["Low"].rolling(14).min()

            df.dropna(inplace=True)  # ✅ Eliminar filas con valores NaN

            return df
        except Exception as e:
            logger.error(f"❌ Error fetching data for {ticker}: {e}")
            return None

    def send_data(self, data):
        """Send processed market data to other agents via ZeroMQ."""
        try:
            if not data or not isinstance(data, dict) or "ticker" not in data:
                logger.warning("⚠️ No valid data to send. Skipping.")
                return

            # ✅ Convertir valores numéricos a `float` si son `Series`
            for key in ["last_price", "SMA_50", "SMA_200", "RSI", "MACD", "ATR"]:
                if key in data and isinstance(data[key], (pd.Series, np.ndarray, list)):
                    data[key] = float(data[key].iloc[-1])
                elif key in data:
                    data[key] = float(data[key])  # ✅ Asegurar que todos los valores sean `float`

            message = json.dumps(data)  # ✅ Convertir a JSON correctamente
            self.socket.send_string(message)
            logger.info(f"📡 Enviado datos de mercado: {data['ticker']} - Precio: {data['last_price']:.2f}")
        except Exception as e:
            logger.error(f"❌ Error enviando datos: {e}")

    def run(self):
        """Fetch historical data and simulate real-time trading faster."""
        historical_data = {ticker: self.fetch_historical_data(ticker) for ticker in self.tickers}

        while True:
            for ticker, df in historical_data.items():
                if df is None or df.empty:
                    continue  # ✅ Si no hay datos, saltar este ticker

                for i in range(len(df)):
                    row = df.iloc[i]
                    data = {
                        "ticker": ticker,
                        "last_price": row["Close"],
                        "SMA_50": row["SMA_50"],
                        "SMA_200": row["SMA_200"],
                        "RSI": row["RSI"],
                        "MACD": row["MACD"],
                        "ATR": row["ATR"]
                    }

                    self.send_data(data)

                    # ✅ Reducimos `time.sleep()` para acelerar la simulación
                    if i % 5 == 0:  # ✅ Enviar 5 datos seguidos antes de dormir
                        time.sleep(0.02)  # ✅ Antes 0.05s, ahora 0.02s para llenar el buffer más rápido


if __name__ == "__main__":
    tickers = ["SPY", "QQQ", "SOXX", "VGT", "ARKK"]  # ✅ ETFs de los índices
    market_agent = MarketDataAgent(tickers)
    market_agent.run()
