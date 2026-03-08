"""
This script provides a basic Kafka consumer for testing purposes.

It connects to a specified Kafka topic and prints the value of each message
it receives to the console. This is useful for verifying that a producer is
sending messages correctly and for inspecting the content of a topic in real-time.

Before running, ensure that the `KAFKA_URL` in the project's configuration
is set correctly.

To run this script, execute the following command from the root of the project:
  poetry run python dt/scripts/hands-on-scripts/software/kafka/consumer.py
"""

import sys

# Add the project root to the Python path to allow for absolute imports.
sys.path.append(".")

from kafka import KafkaConsumer

from dt.utils import Config

# --- Kafka Configuration ---
# The address of the Kafka bootstrap server. Fetched from the central config.
KAFKA_BOOTSTRAP_SERVERS = Config.KAFKA_URL
# The topic to subscribe to. For this example, we use a simple 'test' topic.
KAFKA_TOPIC = "test"

print("--- Kafka Consumer ---")
print(f"Connecting to bootstrap server: {KAFKA_BOOTSTRAP_SERVERS}")
print(f"Subscribing to topic: {KAFKA_TOPIC}")
print("Waiting for messages... (Press Ctrl+C to exit)")

try:
    # --- Initialize Kafka Consumer ---
    # `auto_offset_reset='earliest'`: If this consumer group has no committed
    #   offset, it will start reading from the beginning of the topic.
    # `enable_auto_commit=True`: The consumer will automatically commit offsets
    #   in the background.
    consumer = KafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=[KAFKA_BOOTSTRAP_SERVERS],
        auto_offset_reset="earliest",
        enable_auto_commit=True,
    )

    # --- Message Consumption Loop ---
    # The consumer object is an iterator that blocks until a new message is
    # received. The loop will run indefinitely, processing messages as they arrive.
    for message in consumer:
        # Kafka messages are received as bytes, so they need to be decoded.
        # We assume UTF-8 encoding here.
        print(f"Received message: {message.value.decode('utf-8')}")

except Exception as e:
    print(f"An error occurred: {e}")
except KeyboardInterrupt:
    print("\nConsumer interrupted by user.")
finally:
    print("Closing consumer.")
    if "consumer" in locals() and consumer:
        consumer.close()
