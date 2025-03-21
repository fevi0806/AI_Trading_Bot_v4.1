import threading
import logging
import sys
import os
import signal
import atexit
import time
import zmq

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.comm_framework import CommFramework
from agents.market_data_agent import MarketDataAgent
from agents.sentiment_agent import SentimentAgent
from agents.strategy_agent import StrategyAgent
from agents.risk_agent import RiskManagementAgent
from agents.execution_agent import ExecutionAgent
from agents.logging_monitoring_agent import LoggingMonitoringAgent

# 📌 Configuración de logging (Archivo y Consola)
LOG_FILE = "logs/main.log"
os.makedirs("logs", exist_ok=True)  # ✅ Crear carpeta si no existe

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, mode="w", encoding="utf-8"),  # ✅ Logs en archivo
        logging.StreamHandler(sys.stdout)  # ✅ Logs en terminal
    ]
)

# ✅ Inicializar ZeroMQ CommFramework
comm_framework = CommFramework()

# ✅ Lista de tickers para MarketDataAgent
TICKERS = ["QQQ", "SOXX", "SPY", "VGT", "ARKK"]

# ✅ Agentes registrados
AGENTS = {
    "MarketDataAgent": MarketDataAgent,
    "SentimentAgent": SentimentAgent,
    "StrategyAgent": StrategyAgent,
    "RiskManagementAgent": RiskManagementAgent,
    "ExecutionAgent": ExecutionAgent,
    "LoggingMonitoringAgent": LoggingMonitoringAgent
}

# ✅ Variables de control
threads = []
running_agents = []
shutdown_flag = False  # 🚨 Bandera de apagado


def shutdown(signum=None, frame=None):
    """Apaga todos los agentes de manera ordenada y limpia los recursos."""
    global shutdown_flag
    shutdown_flag = True
    logging.info(f"🚨 Señal de apagado recibida ({signum}). Cerrando agentes...")

    for agent in running_agents:
        try:
            logging.info(f"🛑 Apagando {agent.__class__.__name__}...")
            agent.running = False
        except Exception as e:
            logging.error(f"❌ Error apagando {agent.__class__.__name__}: {e}")

    time.sleep(2)  # ✅ Dar tiempo a los agentes para apagarse correctamente

    try:
        comm_framework.cleanup()
        logging.info("✅ Sockets ZeroMQ cerrados correctamente.")
    except Exception as e:
        logging.error(f"❌ Error cerrando ZeroMQ: {e}")

    logging.shutdown()
    sys.exit(0)


# ✅ Manejo de señales para cierre seguro
atexit.register(shutdown)
signal.signal(signal.SIGINT, shutdown)
signal.signal(signal.SIGTERM, shutdown)


def wait_for_market_data(timeout=10):
    """Espera hasta `timeout` segundos a que MarketDataAgent envíe datos antes de iniciar los demás agentes."""
    logging.info("⏳ Esperando a que MarketDataAgent envíe datos...")

    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    socket.connect("tcp://localhost:5555")
    socket.setsockopt_string(zmq.SUBSCRIBE, "")

    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            message = socket.recv_string(flags=zmq.NOBLOCK)
            if message:
                logging.info("📡 MarketDataAgent está enviando datos. Arrancando el resto de agentes...")
                socket.close()
                return
        except zmq.Again:
            time.sleep(0.5)  # ✅ Menos consumo de CPU durante la espera

    socket.close()
    logging.error("❌ MarketDataAgent no envió datos a tiempo. Abortando...")
    sys.exit(1)


def start_agent(agent_class, name):
    """Inicia un agente y lo añade a la lista de ejecución."""
    try:
        if name == "StrategyAgent":
            agent = agent_class()
        elif name == "MarketDataAgent":
            agent = agent_class(TICKERS)
        else:
            agent = agent_class(comm_framework)

        agent.running = True
        running_agents.append(agent)
        agent.run()

        logging.info(f"✅ {name} iniciado correctamente.")
    except Exception as e:
        logging.error(f"❌ Error al iniciar {name}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    logging.info("🚀 Iniciando todos los agentes...")

    # ✅ **Paso 1: Iniciar MarketDataAgent primero**
    market_thread = threading.Thread(target=start_agent, args=(MarketDataAgent, "MarketDataAgent"), daemon=True)
    market_thread.start()
    threads.append(market_thread)

    # ✅ **Paso 2: Esperar a que MarketDataAgent envíe datos**
    wait_for_market_data()

    # ✅ **Paso 3: Iniciar los demás agentes**
    for agent_name, agent_class in AGENTS.items():
        if agent_name == "MarketDataAgent":
            continue  # ✅ Ya fue iniciado antes

        thread = threading.Thread(target=start_agent, args=(agent_class, agent_name), daemon=True)
        thread.start()
        threads.append(thread)

    # ✅ Mantener `main.py` activo mientras los agentes corren
    try:
        while not shutdown_flag:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("🛑 Interrupción manual detectada.")
        shutdown()
