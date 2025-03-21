import os
import pandas as pd
import numpy as np
import zmq
import json
import logging
import time
import threading
import sqlite3
from collections import deque
from stable_baselines3 import PPO
import sys

class StrategyAgent:
    """Receives market data and predicts trade signals using PPO model."""

    def __init__(self, port_pub=5564, port_sub=5555, lookback=50):
        """Initialize StrategyAgent with logging, ZeroMQ, PPO model loading, and database setup."""
        self.logger = self.setup_logger()
        self.lookback = lookback  # Tamaño del historial para alinearlo con PPO (50 períodos)
        self.db_path = "data/trades.db"  # Ruta correcta para almacenamiento unificado

        # Buffer (cola) para almacenar datos históricos de cada ticker
        self.data_buffer = {ticker: deque(maxlen=lookback) for ticker in ["SPY", "QQQ", "SOXX", "VGT", "ARKK"]}

        # Cargar modelos PPO solo una vez al inicio
        self.models = self.load_all_ppo_models()

        # Configurar conexión ZeroMQ para RECIBIR datos de MarketDataAgent
        self.context = zmq.Context()
        self.socket_sub = self.context.socket(zmq.SUB)
        self.socket_sub.connect(f"tcp://localhost:{port_sub}")  # Suscribirse a MarketDataAgent
        self.socket_sub.setsockopt_string(zmq.SUBSCRIBE, "")  # Recibir todos los mensajes

        # Configurar conexión ZeroMQ para ENVIAR señales de trading a ExecutionAgent
        self.trade_pub = self.context.socket(zmq.PUB)
        self.trade_pub.bind(f"tcp://*:{port_pub}")  # Publicar en 5564 para ExecutionAgent

        # Configurar base de datos
        self.setup_database()

        # Iniciar hilos para procesar cada ticker en paralelo
        self.threads = {}
        for ticker in self.data_buffer.keys():
            thread = threading.Thread(target=self.process_ticker_data, args=(ticker,))
            thread.daemon = True
            thread.start()
            self.threads[ticker] = thread

    def setup_logger(self):
        """Set up logging for strategy agent."""
        logger = logging.getLogger("StrategyAgent")
        logger.setLevel(logging.INFO)
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logger.addHandler(console_handler)
        return logger

    def setup_database(self):
        """Setup SQLite database if not exists."""
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS trade_signals (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT,
                        ticker TEXT,
                        signal TEXT,
                        price REAL
                    )
                """)
                conn.commit()
            self.logger.info("✅ SQLite Database `trade_signals` initialized successfully.")
        except Exception as e:
            self.logger.error(f"❌ Database Setup Error: {e}")

    def save_trade_signal(self, signal_data):
        """Save trade signals into the database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO trade_signals (timestamp, ticker, signal, price)
                    VALUES (?, ?, ?, ?)
                """, (signal_data["timestamp"], signal_data["ticker"], signal_data["signal"], signal_data["price"]))
                conn.commit()
            self.logger.info(f"📌 Trade signal saved to database: {signal_data}")
        except Exception as e:
            self.logger.error(f"❌ Error saving trade signal to database: {e}")

    def load_ppo_model(self, ticker):
        """Load PPO model for a specific ticker."""
        model_path = f"models/{ticker}_ppo.zip"
        if not os.path.exists(model_path):
            self.logger.error(f"❌ Model not found: {model_path}")
            return None
        try:
            model = PPO.load(model_path)
            self.logger.info(f"✅ Modelo cargado: {model_path}")
            return model
        except Exception as e:
            self.logger.error(f"❌ Error cargando modelo {ticker}: {e}")
            return None

    def load_all_ppo_models(self):
        """Carga todos los modelos PPO una vez al inicio."""
        models = {}
        for ticker in self.data_buffer.keys():
            models[ticker] = self.load_ppo_model(ticker)
        return models

    def process_market_data(self, message):
        """Process incoming market data and update buffer."""
        try:
            data = json.loads(message)
            ticker = data["ticker"]

            new_data = [
                data["last_price"], data["SMA_50"], data["SMA_200"],
                data["RSI"], data["MACD"], data["ATR"]
            ]

            self.data_buffer[ticker].append(new_data)

        except Exception as e:
            self.logger.error(f"❌ Error procesando datos de mercado: {e}")

    def process_ticker_data(self, ticker):
        """Process data for a specific ticker in a separate thread."""
        while True:
            if len(self.data_buffer[ticker]) == self.lookback:
                observation = np.array(self.data_buffer[ticker])

                # Ejecutar predicción de señal en paralelo
                signal = self.predict_trade_signal(ticker, observation)

                # Enviar señal de trading a ExecutionAgent
                self.send_trade_signal(ticker, signal)

            time.sleep(0.01)  # Pequeño delay para no saturar la CPU

    def predict_trade_signal(self, ticker, observation):
        """Generate a trade signal using the trained PPO model."""
        model = self.models.get(ticker)

        if model is None:
            return "HOLD"

        observation = np.expand_dims(observation, axis=0)  # Asegurar forma (1,50,6)

        try:
            action, _ = model.predict(observation)

            if action is None:
                return "HOLD"

            return "BUY" if action == 1 else "SELL" if action == 2 else "HOLD"
        except Exception as e:
            self.logger.error(f"❌ Error en la predicción para {ticker}: {e}")
            return "HOLD"

    def send_trade_signal(self, ticker, signal):
        """Send trade signal to ExecutionAgent via ZeroMQ and save to database."""
        trade_signal = {
            "ticker": ticker,
            "signal": signal,
            "price": self.data_buffer[ticker][-1][0],  # Último precio
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

        try:
            self.trade_pub.send_json(trade_signal)
            self.logger.info(f"📤 Trade signal sent: {trade_signal}")
            self.save_trade_signal(trade_signal)  # Guardar en la base de datos
        except Exception as e:
            self.logger.error(f"❌ Failed to send trade signal: {e}")

    def run(self):
        """Receive market data and process it continuously."""
        self.logger.info("🚀 StrategyAgent is running and waiting for market data...")

        poller = zmq.Poller()
        poller.register(self.socket_sub, zmq.POLLIN)

        while True:
            socks = dict(poller.poll(timeout=10))

            if self.socket_sub in socks and socks[self.socket_sub] == zmq.POLLIN:
                message = self.socket_sub.recv_string()
                self.process_market_data(message)

            time.sleep(0.001)

if __name__ == "__main__":
    agent = StrategyAgent()
    agent.run()
