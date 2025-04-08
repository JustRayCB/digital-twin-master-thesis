import json
import random
import time

from kafka import KafkaProducer

KAFKA_BOOTSTRAP_SERVERS = "192.168.129.7:9092"
KAFKA_TOPIC_TEST = "test"
producer = KafkaProducer(
    bootstrap_servers=[KAFKA_BOOTSTRAP_SERVERS],
)
i = 0
while i <= 30:
    print(f"Producing message {i} to topic {KAFKA_TOPIC_TEST}")
    producer.send(
        KAFKA_TOPIC_TEST,
        json.dumps({"message": f"Hello, Kafka! - test {i}"}).encode("utf-8"),
    )
    i += 1
    time.sleep(random.randint(1, 5))
producer.flush()
