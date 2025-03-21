import pandas as pd

class ExecutionAgentTest:
    def __init__(self, capital, take_profit_pct=0.06, trailing_stop_pct=0.03):
        self.capital = capital
        self.position = {}
        self.position_price = {}
        self.take_profit_pct = take_profit_pct
        self.trailing_stop_pct = trailing_stop_pct
        self.trailing_stop = {}

    def execute_trade(self, signal, row, date, ticker):
        price = float(row["Close"].iloc[0]) if isinstance(row["Close"], pd.Series) else float(row["Close"])

        if signal == "BUY":
            if self.capital >= price:
                shares = self.capital // price
                if shares > 0:
                    self.position[ticker] = shares
                    self.position_price[ticker] = price
                    self.trailing_stop[ticker] = price * (1 - self.trailing_stop_pct)
                    self.capital -= shares * price
                    return (date, ticker, "BUY", shares * price)

        elif signal == "SELL":
            if ticker in self.position and self.position[ticker] > 0:
                shares = self.position[ticker]
                proceeds = shares * price
                cost = shares * self.position_price[ticker]
                pnl = proceeds - cost

                # Reset position
                self.capital += proceeds
                self.position[ticker] = 0
                self.position_price[ticker] = 0
                self.trailing_stop[ticker] = 0
                return (date, ticker, "SELL", pnl)

        elif signal == "HOLD":
            if ticker in self.position and self.position[ticker] > 0:
                # Check take profit
                entry_price = self.position_price[ticker]
                if price >= entry_price * (1 + self.take_profit_pct):
                    shares = self.position[ticker]
                    proceeds = shares * price
                    cost = shares * entry_price
                    pnl = proceeds - cost
                    self.capital += proceeds
                    self.position[ticker] = 0
                    self.position_price[ticker] = 0
                    self.trailing_stop[ticker] = 0
                    return (date, ticker, "SELL (TP)", pnl)

                # Check trailing stop
                if price > self.position_price[ticker]:
                    self.trailing_stop[ticker] = max(self.trailing_stop[ticker], price * (1 - self.trailing_stop_pct))
                if price <= self.trailing_stop[ticker]:
                    shares = self.position[ticker]
                    proceeds = shares * price
                    cost = shares * entry_price
                    pnl = proceeds - cost
                    self.capital += proceeds
                    self.position[ticker] = 0
                    self.position_price[ticker] = 0
                    self.trailing_stop[ticker] = 0
                    return (date, ticker, "SELL (TS)", pnl)

        return None
