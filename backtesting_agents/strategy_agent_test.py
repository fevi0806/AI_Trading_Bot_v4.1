import pandas as pd

class StrategyAgentTest:
    def __init__(self):
        self.last_trade_index = {}
        self.entry_price = {}

    def generate_signal(self, row, ticker, current_index):
        indicators = ["SMA_50", "SMA_200", "ADX", "MACD", "Signal_Line", "RSI", "Close"]
        for ind in indicators:
            value = row[ind]
            if isinstance(value, pd.Series):
                value = value.iloc[0]
            if pd.isna(value):
                return "HOLD"

        sma_50 = float(row["SMA_50"])
        sma_200 = float(row["SMA_200"])
        adx = float(row["ADX"])
        macd = float(row["MACD"])
        signal_line = float(row["Signal_Line"])
        rsi = float(row["RSI"])
        close_price = float(row["Close"])

        trend_up = sma_50 > sma_200
        adx_strong = adx > 25
        sideways = adx < 20
        signal = "HOLD"

        # --- Estrategia por ETF ---
        if ticker == "QQQ":
            if trend_up and adx_strong and macd > signal_line and rsi < 65:
                signal = "BUY"
            elif ticker in self.entry_price:
                entry = self.entry_price[ticker]
                if macd < signal_line and rsi > 68 and (close_price - entry) / entry > 0.015:
                    signal = "SELL"

        elif ticker == "SOXX":
            if trend_up and macd > signal_line and rsi < 60:
                signal = "BUY"
            elif sideways and rsi < 35 and macd > signal_line:
                signal = "BUY"
            elif ticker in self.entry_price:
                entry = self.entry_price[ticker]
                if (macd < signal_line and rsi > 65) and (close_price - entry) / entry > 0.015:
                    signal = "SELL"

        elif ticker == "SPY":
            if trend_up and macd > signal_line and rsi < 60:
                signal = "BUY"
            elif ticker in self.entry_price:
                entry = self.entry_price[ticker]
                if macd < signal_line and rsi > 70 and (close_price - entry) / entry > 0.015:
                    signal = "SELL"

        elif ticker == "VGT":
            if trend_up and macd > signal_line and rsi < 60:
                signal = "BUY"
            elif ticker in self.entry_price:
                entry = self.entry_price[ticker]
                if macd < signal_line and rsi > 68 and (close_price - entry) / entry > 0.015:
                    signal = "SELL"

        elif ticker == "ARKK":
            if sideways and rsi < 35 and macd > signal_line:
                signal = "BUY"
            elif trend_up and adx_strong and rsi < 60 and macd > signal_line:
                signal = "BUY"
            elif ticker in self.entry_price:
                entry = self.entry_price[ticker]
                if (macd < signal_line and rsi > 70) and (close_price - entry) / entry > 0.02:
                    signal = "SELL"

        # Guardar precio de entrada
        if signal == "BUY":
            self.entry_price[ticker] = close_price
            self.last_trade_index[ticker] = current_index

        return signal
