import zmq
import json
import time
import logging
import sys
import os
import sqlite3
import queue
import threading
from collections import deque

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.comm_framework import CommFramework  
from utils.logger import setup_logger

class ExecutionAgent:
    def __init__(self, comm_framework, initial_balance=100000):
        self.comm = comm_framework
        self.logger = setup_logger("ExecutionAgent", "logs/execution_agent.log")
        self.running = True  
        self.queue = queue.Queue()

        self.comm.free_ports(exclude_ports=[5555])

        try:
            self.trade_sub = self.comm.create_subscriber("ExecutionAgent")
            self.execution_pub = self.comm.create_publisher("ExecutionAgent")
        except Exception as e:
            self.logger.error(f"❌ ExecutionAgent Init Error: {e}")
            self.trade_sub = None
            self.execution_pub = None

        if not self.trade_sub or not self.execution_pub:
            self.logger.error("❌ ExecutionAgent failed to initialize communication sockets.")
            return

        self.balance = initial_balance  
        self.positions = {}  
        self.last_trade_times = {}  # Control de frecuencia de operaciones por activo
        self.trade_limit = 3  # Máximo de operaciones permitidas en 10 minutos por ticker
        self.trade_interval = 600  # 10 minutos en segundos
        self.last_prices = {}  # Últimos precios de compra por ticker
        self.db_path = "data/trades.db"
        self.setup_database()
        
        self.lock = threading.Lock()
        self.batch_size = 5  
        self.batch_orders = []  
        self.last_save_time = time.time()

    def setup_database(self):
        """Setup SQLite database if not exists."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS executed_trades (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        ticker TEXT NOT NULL,
                        action TEXT NOT NULL,
                        price REAL NOT NULL,
                        shares INTEGER NOT NULL,
                        balance REAL NOT NULL
                    )
                """)
                conn.commit()
            self.logger.info("✅ SQLite Database `executed_trades` initialized successfully.")
        except Exception as e:
            self.logger.error(f"❌ Database Setup Error: {e}")

    def save_order(self, order):
        """Save orders in batch to SQLite for efficiency."""
        with self.lock:
            self.batch_orders.append(order)
            if len(self.batch_orders) >= self.batch_size or time.time() - self.last_save_time >= 5:
                try:
                    with sqlite3.connect(self.db_path) as conn:
                        cursor = conn.cursor()
                        cursor.executemany("""
                            INSERT INTO executed_trades (timestamp, ticker, action, price, shares, balance)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, [(o["timestamp"], o["ticker"], o["action"], o["price"], o["shares"], o["balance"]) for o in self.batch_orders])
                        conn.commit()
                    self.logger.info(f"✅ {len(self.batch_orders)} orders saved to database.")
                    self.batch_orders = []
                    self.last_save_time = time.time()
                except Exception as e:
                    self.logger.error(f"❌ Error saving orders to database: {e}")

    def can_execute_trade(self, ticker):
        """Check if a trade can be executed based on frequency limits."""
        current_time = time.time()
        if ticker not in self.last_trade_times:
            self.last_trade_times[ticker] = deque(maxlen=self.trade_limit)

        recent_trades = self.last_trade_times[ticker]
        if len(recent_trades) >= self.trade_limit and (current_time - recent_trades[0]) < self.trade_interval:
            self.logger.warning(f"⚠️ Trade limit reached for {ticker}. Skipping trade.")
            return False
        
        recent_trades.append(current_time)
        return True

    def execute_trade(self, signal):
        """Process trade execution based on received signals."""
        ticker = signal.get("ticker", "Unknown")
        action = signal.get("signal", "Unknown")
        price = signal.get("price", 0.0)

        if action not in ["BUY", "SELL"]:
            self.logger.warning(f"⚠️ Invalid trade signal received: {action}")
            return
        
        if not self.can_execute_trade(ticker):
            return

        self.logger.info(f"💼 Executing trade: {action} on {ticker} at ${price:.2f}")

        with self.lock:
            shares = 0
            if action == "BUY":
                if self.balance * 0.90 < price:  # Mantener al menos 10% del balance disponible
                    self.logger.warning(f"⚠️ Not enough balance to buy {ticker}.")
                    return

                max_shares = int(self.balance // price)
                if max_shares > 0:
                    shares = max_shares
                    self.positions[ticker] = self.positions.get(ticker, 0) + shares
                    self.balance -= shares * price
                    self.last_prices[ticker] = price  # Guardar último precio de compra
                    self.logger.info(f"🟢 BUY {shares} {ticker} at ${price:.2f} | Balance: ${self.balance:.2f}")
                else:
                    self.logger.warning(f"⚠️ Not enough capital to buy {ticker}.")
                    return

            elif action == "SELL":
                available_shares = self.positions.get(ticker, 0)
                if available_shares > 0:
                    if ticker in self.last_prices and price < self.last_prices[ticker] * 1.01:
                        self.logger.warning(f"⚠️ Selling {ticker} below 1% profit margin. Skipping trade.")
                        return

                    shares = available_shares
                    self.balance += shares * price
                    self.positions[ticker] = 0  
                    self.logger.info(f"🔴 SELL {shares} {ticker} at ${price:.2f} | Balance: ${self.balance:.2f}")
                else:
                    self.logger.warning(f"⚠️ No shares of {ticker} to sell.")
                    return

            order = {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),  # Garantizar formato de timestamp correcto
                "ticker": ticker,
                "action": action,
                "price": price,
                "shares": shares,
                "balance": self.balance
            }
            self.save_order(order)

            execution_feedback = {
                "ticker": ticker,
                "status": "executed",
                "action": action,
                "price": price,
                "timestamp": order["timestamp"],
            }

            try:
                if self.execution_pub and not self.execution_pub.closed:
                    self.execution_pub.send_json(execution_feedback)
                    self.logger.info(f"📤 Execution feedback sent: {execution_feedback}")
                else:
                    self.logger.warning("⚠️ Execution feedback not sent: Publisher socket is closed.")
            except Exception as e:
                self.logger.error(f"❌ Failed to send execution feedback: {e}")

    def run(self):
        """Run ExecutionAgent continuously to process trade signals."""
        self.logger.info("🚀 Execution Agent Started.")
        if not self.trade_sub:
            self.logger.error("❌ ExecutionAgent cannot start: No valid subscriber.")
            return
        while self.running:
            try:
                message = self.trade_sub.recv_string(flags=zmq.NOBLOCK)
                if message:
                    signal = json.loads(message)
                    self.queue.put(signal)
                    self.execute_trade(self.queue.get())
            except zmq.Again:
                pass  
            except Exception as e:
                self.logger.error(f"❌ Error processing trade signal: {e}")
            time.sleep(0.5)

    def stop(self):
        """Stop ExecutionAgent safely."""
        self.logger.info("🛑 Stopping Execution Agent...")
        self.running = False  

if __name__ == "__main__":
    comm_framework = CommFramework()
    agent = ExecutionAgent(comm_framework)
    agent.run()
