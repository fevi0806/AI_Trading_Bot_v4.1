import zmq
import logging
import os
import sys
import time

# Ensure Python can find the parent directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.logger import setup_logger
from agents.comm_framework import CommFramework

class LoggingMonitoringAgent:
    def __init__(self, comm_framework):
        """Initialize the Logging Monitoring Agent to collect logs from all agents."""
        self.comm = comm_framework
        self.logger = setup_logger("LoggingMonitoringAgent", "logs/logging_monitoring_agent.log")
        self.running = True  #  Enables graceful shutdown

        self.logger.info(" Logging Monitoring Agent Started and ready to receive logs.")

        #  List of agents to monitor logs
        self.agents = ["MarketDataAgent", "SentimentAgent", "StrategyAgent", "RiskManagementAgent", "ExecutionAgent"]
        self.subscribers = {}

        #  Subscribe to logs from all agents
        for agent in self.agents:
            try:
                self.subscribers[agent] = self.comm.create_subscriber(agent, topic="LOG")
                self.logger.info(f" Subscribed to logs from {agent}")
            except Exception as e:
                self.logger.error(f" Failed to subscribe to logs from {agent}: {e}")
                self.subscribers[agent] = None  # Mark as failed

    def run(self):
        """Continuously listen for logs from all agents."""
        self.logger.info(" Logging Monitoring Agent Running...")

        while self.running:
            for agent, subscriber in self.subscribers.items():
                if not subscriber:
                    continue  #  Skip if subscription failed

                try:
                    message = None
                    try:
                        message = subscriber.recv_string(flags=zmq.NOBLOCK)  #  Non-blocking receive
                    except zmq.Again:
                        pass  #  No new messages, continue looping

                    if message:
                        self.logger.info(f" {agent} Log: {message}")

                except zmq.ZMQError as e:
                    self.logger.error(f" ZMQ Error receiving log from {agent}: {e}")
                except Exception as e:
                    self.logger.error(f" Unexpected error in LoggingMonitoringAgent for {agent}: {e}")

            time.sleep(1)  #  Prevent CPU overuse

    def stop(self):
        """Gracefully stops the LoggingMonitoringAgent."""
        self.logger.info(" Stopping Logging Monitoring Agent...")
        self.running = False  #  Stops the loop properly
