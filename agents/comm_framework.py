import zmq
import logging
import yaml
import os
import psutil
import time
import sys

# Ensure Python can find the parent directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.logger import setup_logger

class CommFramework:
    def __init__(self, config_path="config/config.yml"):
        """Initialize the communication framework with ZeroMQ context."""
        self.context = zmq.Context()
        self.publishers = {}
        self.subscribers = {}
        self.logger = setup_logger("trading", "logs/comm_framework.log")
        self.config = self.load_config(config_path)

        if not self.config:
            self.logger.error(" No valid configuration found. Exiting CommFramework initialization.")
            return
        
        #  Ensure ports are free before starting (but DO NOT terminate active agents)
        self.free_ports(exclude_ports=[5555, 5557, 5564])  #  Protect MarketDataAgent, SentimentAgent & StrategyAgent

    def load_config(self, config_path):
        """Load the configuration file for port assignments."""
        if not os.path.exists(config_path):
            self.logger.error(f" Config file not found: {config_path}")
            return {}

        try:
            with open(config_path, "r") as file:
                config = yaml.safe_load(file)
            if not config or "ports" not in config:
                self.logger.error(" Invalid or missing 'ports' section in configuration file.")
                return {}

            self.logger.info(" Configuration loaded successfully.")
            return config.get("ports", {})
        except Exception as e:
            self.logger.error(f" Failed to load configuration: {e}")
            return {}

    def free_ports(self, exclude_ports=None):
        """Finds and terminates only inactive processes using our system's ports (but keeps active agents running)."""
        if exclude_ports is None:
            exclude_ports = []
        self.logger.info(f" Excluding ports from termination: {exclude_ports}")

        for agent, ports in self.config.items():
            for key in ["publisher", "subscriber"]:
                port = ports.get(key)
                if port and port not in exclude_ports:
                    self._kill_process_using_port(port)

    def _kill_process_using_port(self, port):
        """Kill process occupying a given port if it's NOT used by an active agent."""
        for conn in psutil.net_connections():
            if conn.laddr.port == port:
                try:
                    process = psutil.Process(conn.pid)
                    process_name = process.name()
                    
                    #  PROTECT AGENTS (Do not terminate our own trading agents)
                    if process_name in ["python.exe", "python3"]:
                        self.logger.info(f" Port {port} in use by active agent ({process_name} - PID {conn.pid}). Skipping termination.")
                        return

                    self.logger.warning(f" Port {port} in use by {process_name} (PID {conn.pid}). Terminating...")
                    process.terminate()
                    time.sleep(1)
                    self.logger.info(f" Port {port} is now free.")
                except psutil.NoSuchProcess:
                    self.logger.warning(f" No process found on port {port}, skipping.")

    def create_publisher(self, agent_name):
        """Create and bind a publisher socket for a given agent."""
        if agent_name not in self.config:
            self.logger.error(f" No port assigned for {agent_name} in config.")
            return None

        port = self.config[agent_name].get("publisher")
        if not port:
            self.logger.error(f" Publisher port missing for {agent_name}.")
            return None

        try:
            socket = self.context.socket(zmq.PUB)
            socket.bind(f"tcp://*:{port}")
            self.publishers[agent_name] = socket
            self.logger.info(f" {agent_name} Publisher bound on port {port}")
            return socket
        except zmq.ZMQError as e:
            self.logger.error(f" Failed to bind publisher for {agent_name} on port {port}: {e}")
            return None

    def create_subscriber(self, agent_name, topic=""):
        """Create and connect a subscriber socket for a given agent."""
        if agent_name not in self.config:
            self.logger.error(f" No port assigned for {agent_name} in config.")
            return None

        port = self.config[agent_name].get("subscriber")
        if not port:
            self.logger.error(f" Subscriber port missing for {agent_name}.")
            return None

        try:
            socket = self.context.socket(zmq.SUB)
            socket.connect(f"tcp://localhost:{port}")
            socket.setsockopt_string(zmq.SUBSCRIBE, topic)
            self.subscribers[agent_name] = socket
            self.logger.info(f" {agent_name} Subscriber connected to port {port} with topic '{topic}'")
            return socket
        except zmq.ZMQError as e:
            self.logger.error(f" Failed to connect subscriber for {agent_name} on port {port}: {e}")
            return None

    def cleanup(self):
        """Cleanup all ZeroMQ sockets on shutdown."""
        self.logger.info(" Cleaning up ZeroMQ sockets...")

        for agent, socket in list(self.publishers.items()):
            try:
                socket.close()
                self.logger.info(f" Closed publisher socket for {agent}")
            except Exception as e:
                self.logger.error(f" Error closing publisher socket for {agent}: {e}")

        for agent, socket in list(self.subscribers.items()):
            try:
                socket.close()
                self.logger.info(f" Closed subscriber socket for {agent}")
            except Exception as e:
                self.logger.error(f" Error closing subscriber socket for {agent}: {e}")

        try:
            self.context.term()
            self.logger.info(" ZeroMQ context terminated.")
        except Exception as e:
            self.logger.error(f" Error terminating ZeroMQ context: {e}")
