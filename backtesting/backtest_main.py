import pandas as pd
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backtest_engine import BacktestEngine
from datetime import datetime


def main():
    tickers = ["QQQ", "SOXX", "SPY", "VGT", "ARKK"]
    start_date = "2020-01-01"
    end_date = "2023-12-31"
    initial_capital = 10000

    results = []

    for ticker in tickers:
        print(f"\nIniciando backtest para {ticker}...")
        backtest = BacktestEngine(ticker, start_date, end_date, initial_capital)
        trade_log = backtest.run()

        total_pnl = sum([trade[3] for trade in trade_log]) - initial_capital

        buy_hold_pnl = (
            backtest.data["Close"].iloc[-1] - backtest.data["Close"].iloc[0]
            if not backtest.data["Close"].empty else 0
        )

        results.append({
            "ticker": ticker,
            "total_pnl": round(total_pnl, 2),
            "num_trades": len(trade_log),
            "buy_hold_pnl": round(float(buy_hold_pnl.iloc[0]) if isinstance(buy_hold_pnl, pd.Series) else float(buy_hold_pnl), 2)

        })

    df_results = pd.DataFrame(results)
    print("\n📊 Resultados del Backtesting:")
    print(df_results)

    output_path = os.path.join("backtesting", "results", "performance_report.csv")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df_results.to_csv(output_path, index=False)
    print(f"\n✅ Resultados guardados en: {output_path}")

if __name__ == "__main__":
    main()
