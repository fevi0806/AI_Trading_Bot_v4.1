import pandas as pd

class RiskAgentTest:
    def __init__(self):
        pass  # Se elimina cooldown/restricción temporal

    def evaluate_risk(self, signal, row, current_index):
        rsi = float(row["RSI"].iloc[0]) if isinstance(row["RSI"], pd.Series) else float(row["RSI"])
        adx = float(row["ADX"].iloc[0]) if isinstance(row["ADX"], pd.Series) else float(row["ADX"])
        macd = float(row["MACD"].iloc[0]) if isinstance(row["MACD"], pd.Series) else float(row["MACD"])
        signal_line = float(row["Signal_Line"].iloc[0]) if isinstance(row["Signal_Line"], pd.Series) else float(row["Signal_Line"])

        # ⚠️ Filtro por condiciones extremas
        if signal == "BUY":
            if rsi > 75:
                return "HOLD"  # Sobrecompra fuerte
            if adx < 15 and macd < signal_line:
                return "HOLD"  # Señal débil sin momentum

        elif signal == "SELL":
            if rsi < 25:
                return "HOLD"  # Sobreventa fuerte
            if adx < 15 and macd > signal_line:
                return "HOLD"  # Señal poco confiable

        return signal
