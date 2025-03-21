import pandas as pd
import yfinance as yf
import os
import sys
import numpy as np
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ta.momentum import RSIIndicator
from ta.trend import MACD, SMAIndicator, ADXIndicator
from backtesting_agents.strategy_agent_test import StrategyAgentTest
from backtesting_agents.execution_agent_test import ExecutionAgentTest
from backtesting_agents.risk_agent_test import RiskAgentTest

class BacktestEngine:
    def __init__(self, ticker, start_date, end_date, initial_capital):
        self.ticker = ticker
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        self.data = self.load_data()
        self.strategy_agent = StrategyAgentTest()
        self.execution_agent = ExecutionAgentTest(capital=self.initial_capital)
        self.risk_agent = RiskAgentTest()

    def load_data(self):
        data = yf.download(self.ticker, start=self.start_date, end=self.end_date)
        data.dropna(inplace=True)

        # Calcular indicadores
        close = data["Close"].squeeze()
        high = data["High"].squeeze()
        low = data["Low"].squeeze()

        data["RSI"] = RSIIndicator(close=close).rsi()
        data["MACD"] = MACD(close=close).macd()
        data["Signal_Line"] = MACD(close=close).macd_signal()
        data["SMA_50"] = SMAIndicator(close=close, window=50).sma_indicator()
        data["SMA_200"] = SMAIndicator(close=close, window=200).sma_indicator()
        data["ADX"] = ADXIndicator(high=high, low=low, close=close).adx()

        return data

    def run(self):
        trade_log = []

        for i, (date, row) in enumerate(self.data.iterrows()):
            signal = self.strategy_agent.generate_signal(row, self.ticker, i)
            signal = self.risk_agent.evaluate_risk(signal, row, i)

            executed_trade = self.execution_agent.execute_trade(signal, row, date, self.ticker)

            if executed_trade:
                trade_log.append(executed_trade)

        return trade_log
