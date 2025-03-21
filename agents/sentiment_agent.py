import zmq
import json
import time
import logging
import os
import sys


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.logger import setup_logger
from agents.comm_framework import CommFramework

class SentimentAgent:
    def __init__(self, comm_framework):
        self.comm = comm_framework
        self.publisher = self.comm.create_publisher("SentimentAgent")
        self.subscriber = self.comm.create_subscriber("SentimentAgent", topic="NEWS")
        self.logger = setup_logger("SentimentAgent", "logs/sentiment_agent.log")
        self.running = True  #  Allows graceful shutdown

    def run(self):
        """Continuously processes news sentiment until stopped."""
        self.logger.info(" Sentiment Agent Started.")

        while self.running:
            try:
                if self.subscriber:
                    message = self.subscriber.recv_string(flags=zmq.NOBLOCK)  #  Non-blocking receive
                    self.logger.info(f" Received News Data: {message}")

                    # Process sentiment analysis (Placeholder logic)
                    sentiment = "Positive"  # Dummy sentiment

                    sentiment_data = json.dumps({"sentiment": sentiment})

                    #  Ensure publisher is available before sending
                    if self.publisher and not self.publisher.closed:
                        self.publisher.send_string(sentiment_data)
                        self.logger.info(f" Sentiment Sent: {sentiment_data}")
                    else:
                        self.logger.warning(" Cannot send sentiment data: Publisher socket closed.")
                else:
                    self.logger.warning(" No subscriber available for SentimentAgent.")

            except zmq.Again:
                pass  #  No message available, continue looping
            except Exception as e:
                self.logger.error(f" Error in SentimentAgent loop: {e}")

            time.sleep(60)  #  Controlled delay to avoid infinite loop issues

    def stop(self):
        """Gracefully stops the SentimentAgent."""
        self.logger.info(" Stopping Sentiment Agent...")
        self.running = False  #  Signal loop to exit
