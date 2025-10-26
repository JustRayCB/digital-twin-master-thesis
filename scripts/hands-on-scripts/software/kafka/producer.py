"""
This script provides a basic Kafka producer for testing purposes.

It connects to a specified Kafka topic and sends a series of simple JSON
messages at random intervals. This is useful for testing a consumer or for
populating a topic with sample data.

Before running, ensure that the `KAFKA_URL` in the project's configuration
is set correctly.

To run this script, execute the following command from the root of the project:
  poetry run python scripts/hands-on-scripts/software/kafka/producer.py
"""

import json
import random
import sys
import time

# Add the project root to the Python path to allow for absolute imports.
sys.path.append(".")

from kafka import KafkaProducer

from dt.utils import Config

# --- Kafka Configuration ---
# The address of the Kafka bootstrap server. Fetched from the central config.
KAFKA_BOOTSTRAP_SERVERS = Config.KAFKA_URL
# The topic to which messages will be sent.
KAFKA_TOPIC = "test"

print("--- Kafka Producer ---")
print(f"Connecting to bootstrap server: {KAFKA_BOOTSTRAP_SERVERS}")
print(f"Target topic: {KAFKA_TOPIC}")

try:
    # --- Initialize Kafka Producer ---
    # The producer is configured to connect to the specified bootstrap servers.
    # By default, it will handle serialization of the message value to bytes.
    producer = KafkaProducer(
        bootstrap_servers=[KAFKA_BOOTSTRAP_SERVERS],
    )

    # --- Message Production Loop ---
    # This loop sends 30 messages to the Kafka topic.
    message_count = 0
    while message_count < 30:
        message_count += 1
        message = {"message": f"Hello, Kafka! - message #{message_count}"}

        # Messages must be sent as bytes. We serialize the dictionary to a JSON
        # string and then encode it to UTF-8 bytes.
        message_bytes = json.dumps(message).encode("utf-8")

        print(f"Sending message {message_count}: {message}")
        producer.send(KAFKA_TOPIC, message_bytes)

        # Wait for a random interval between 1 and 5 seconds before sending the next message.
        sleep_interval = random.randint(1, 5)
        time.sleep(sleep_interval)

except Exception as e:
    print(f"An error occurred: {e}")

finally:
    # --- Flush and Close Producer ---
    # `flush()` ensures that all outstanding messages have been sent before closing.
    if "producer" in locals() and producer:
        print("Flushing messages and closing producer.")
        producer.flush()
        producer.close()
    print("Producer finished.")
