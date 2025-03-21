import pandas as pd
import os

def analyze_performance():
    file_path = "backtesting/results/performance_report.csv"

    if not os.path.exists(file_path):
        print("❌ performance_report.csv not found.")
        return

    df = pd.read_csv(file_path)

    print("\n📊 Análisis de Resultados por Ticker:")
    print(df)

    # ➕ Ganancia total por estrategia vs Buy & Hold
    total_strategy = df["total_pnl"].sum()
    total_buy_hold = df["buy_hold_pnl"].sum()

    print("\n📈 Rentabilidad Total:")
    print(f"🔹 Estrategia: {round(total_strategy, 2)} USD")
    print(f"🔹 Buy & Hold: {round(total_buy_hold, 2)} USD")

    # ➗ Rentabilidad promedio por trade (si hay trades)
    if df["num_trades"].sum() > 0:
        avg_pnl_per_trade = total_strategy / df["num_trades"].sum()
    else:
        avg_pnl_per_trade = 0.0

    print(f"\n⚖️ PnL promedio por trade: {round(avg_pnl_per_trade, 2)} USD")

    # 📁 Guardar análisis limpio
    summary = {
        "total_strategy_pnl": [round(total_strategy, 2)],
        "total_buy_hold_pnl": [round(total_buy_hold, 2)],
        "avg_pnl_per_trade": [round(avg_pnl_per_trade, 2)],
        "total_trades": [int(df['num_trades'].sum())]
    }

    summary_df = pd.DataFrame(summary)
    summary_df.to_csv("backtesting/results/performance_summary.csv", index=False)
    print("\n✅ Resumen guardado en: backtesting/results/performance_summary.csv")

if __name__ == "__main__":
    analyze_performance()
