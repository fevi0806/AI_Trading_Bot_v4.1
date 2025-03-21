import zmq
import json
import time
import logging
import os
import sys

# Ensure Python can find the parent directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.logger import setup_logger
from agents.comm_framework import CommFramework

class RiskManagementAgent:
    def __init__(self, comm_framework):
        """Initialize the Risk Management Agent with communication framework."""
        self.comm = comm_framework
        self.logger = setup_logger("RiskManagementAgent", "logs/risk_management.log")
        self.running = True  #  Allows graceful shutdown

        try:
            self.subscriber = self.comm.create_subscriber("RiskManagementAgent")
            self.publisher = self.comm.create_publisher("RiskManagementAgent")
        except Exception as e:
            self.subscriber = None
            self.publisher = None
            self.logger.error(f" RiskManagementAgent Subscriber/Publisher Init Error: {e}")

    def evaluate_risk(self, trade_signal):
        """Evaluate the risk of a given trade signal."""
        self.logger.info(f" Evaluating Trade Signal: {trade_signal}")

        #  Basic Risk Evaluation Logic
        risk_status = "Approved"
        details = "No risk detected"

        if trade_signal["signal"] == "BUY":
            details = "Checking available funds..."
            # Example check: Reject trade if it exceeds a limit
            trade_amount = trade_signal.get("amount", 0)
            if trade_amount > 10000:  # Example limit
                risk_status = "Rejected"
                details = "Trade size exceeds risk threshold"

        if trade_signal["signal"] == "SELL":
            details = "Checking asset availability..."
            # Example check: Reject trade if short-selling is not allowed
            if not trade_signal.get("short_allowed", False):
                risk_status = "Rejected"
                details = "Short selling is not permitted"

        return {"status": risk_status, "details": details}

    def run(self):
        """Continuously listen for trade signals and process risk assessment."""
        self.logger.info(" Risk Management Agent Started.")

        if not self.subscriber or not self.publisher:
            self.logger.error(" RiskManagementAgent failed to initialize communication sockets.")
            return

        while self.running:
            try:
                message = None
                try:
                    message = self.subscriber.recv_string(flags=zmq.NOBLOCK)  #  Non-blocking receive
                except zmq.Again:
                    pass  #  No message available, continue looping

                if message:
                    trade_signal = json.loads(message)
                    self.logger.info(f" Received Trade Signal: {trade_signal}")

                    #  Evaluate the risk of the trade
                    risk_result = self.evaluate_risk(trade_signal)

                    #  Send the risk assessment result
                    response = json.dumps({
                        "ticker": trade_signal.get("ticker", "Unknown"),
                        "signal": trade_signal.get("signal", "Unknown"),
                        "risk_status": risk_result["status"],
                        "details": risk_result["details"],
                    })

                    if self.publisher and not self.publisher.closed:
                        self.publisher.send_string(response)
                        self.logger.info(f" Risk Evaluation Sent: {response}")
                    else:
                        self.logger.warning(" Cannot send risk evaluation: Publisher socket closed.")

            except Exception as e:
                self.logger.error(f" Error in RiskManagementAgent: {e}")

            time.sleep(1)  #  Prevent CPU overuse

    def stop(self):
        """Gracefully stops the RiskManagementAgent."""
        self.logger.info(" Stopping Risk Management Agent...")
        self.running = False  #  Stops the loop properly
