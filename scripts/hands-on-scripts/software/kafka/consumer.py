from kafka import KafkaConsumer

KAFKA_BOOTSTRAP_SERVERS = "192.168.129.7:9092"
KAFKA_TOPIC_TEST = "test"
consumer = KafkaConsumer(
    KAFKA_TOPIC_TEST,
    bootstrap_servers=[KAFKA_BOOTSTRAP_SERVERS],
    auto_offset_reset="earliest",
    enable_auto_commit=True,
)
for message in consumer:
    print(message.value.decode("utf-8"))
