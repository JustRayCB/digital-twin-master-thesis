#!/bin/bash

# Variables
KAFKA_VERSION="4.0.0"
SCALA_VERSION="2.13"
KAFKA_DIR="/opt/kafka"
KAFKA_TARBALL="kafka_${SCALA_VERSION}-${KAFKA_VERSION}.tgz"
KAFKA_DOWNLOAD_URL="https://archive.apache.org/dist/kafka/${KAFKA_VERSION}/${KAFKA_TARBALL}"
JAVA_PACKAGE="default-jdk"
DEPENDENCIES="net-tools jq netcat-traditional"
DATA_DIR="/var/kafka-logs"

# Update and install Java
echo "Updating system and installing Dependencies (Java, net-tools, jq)..."
sudo apt-get update -y
sudo apt-get upgrade -y
sudo apt-get install -y $JAVA_PACKAGE
sudo apt-get install -y $DEPENDENCIES

# Check if Java is installed
if ! java -version &>/dev/null; then
  echo "Java installation failed. Exiting."
  exit 1
fi

# Check if wget is installed
if ! command -v wget &>/dev/null; then
  echo "wget could not be found. Installing wget..."
  sudo apt-get install -y wget
fi

# Check if Kafka directory already exists
if [ -d "$KAFKA_DIR" ]; then
  echo "Kafka directory already exists. Please remove it or choose a different directory."
  exit 1
fi

# Create Kafka directory
echo "Creating Kafka directory..."
sudo mkdir -p $KAFKA_DIR

echo "Creating Data directories..."
sudo mkdir -p $DATA_DIR

echo "Creating kafka user"
sudo useradd -r -d /opt/kafka -s /bin/false kafka
sudo chown -R kafka:kafka $KAFKA_DIR
sudo chown -R kafka:kafka $DATA_DIR
sudo chmod -R 755 $KAFKA_DIR
sudo chmod -R 755 $DATA_DIR
# Add your user to the kafka group
sudo usermod -aG kafka $USER

# Download Kafka
echo "Downloading Kafka version $KAFKA_VERSION..."
wget -q $KAFKA_DOWNLOAD_URL -O /tmp/$KAFKA_TARBALL

# Extract Kafka
echo "Extracting Kafka..."
sudo tar -xzf /tmp/$KAFKA_TARBALL -C $KAFKA_DIR --strip-components 1
rm /tmp/$KAFKA_TARBALL

# Create kraft directory if it doesn't exist
sudo mkdir -p $KAFKA_DIR/config/kraft

# Generate a cluster ID
CLUSTER_ID=$($KAFKA_DIR/bin/kafka-storage.sh random-uuid)
echo "Generated Kafka cluster ID: $CLUSTER_ID"
echo "$CLUSTER_ID" | sudo tee $KAFKA_DIR/cluster-id >/dev/null

echo "Creating KRaft configuration..."
# Create the server.properties file in the kraft directory
cat <<EOF | sudo tee $KAFKA_DIR/config/kraft/server.properties >/dev/null
# KRaft mode settings
process.roles=broker,controller
node.id=1

# Controller settings
controller.quorum.voters=1@localhost:9093
controller.listener.names=CONTROLLER

# Listener configurations
listeners=PLAINTEXT://0.0.0.0:9092,CONTROLLER://localhost:9093
advertised.listeners=PLAINTEXT://localhost:9092
listener.security.protocol.map=CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT

# Log directory
log.dirs=$DATA_DIR

# Other broker settings
num.partitions=1
default.replication.factor=1
offsets.topic.replication.factor=1
transaction.state.log.replication.factor=1
transaction.state.log.min.isr=1
auto.create.topics.enable=false
# Keep logs for 7 days
log.retention.hours=168
EOF

# num.network.threads=3
# num.io.threads=8
# log.segment.bytes=1073741824
# log.retention.check.interval.ms=300000

# Format the storage directory
echo "Formatting Kafka storage directory..."
sudo $KAFKA_DIR/bin/kafka-storage.sh format -t $CLUSTER_ID -c $KAFKA_DIR/config/kraft/server.properties

# Create systemd service files for Kafka
echo "Setting up Kafka service (KRaft mode)..."
sudo tee /etc/systemd/system/kafka-kraft.service >/dev/null <<EOT
[Unit]
Description=Apache Kafka in KRaft Mode
Requires=network.target
After=network.target

[Service]
Type=simple
User=kafka
Group=kafka
Environment="KAFKA_HEAP_OPTS=-Xmx512M -Xms512M"
ExecStart=${KAFKA_DIR}/bin/kafka-server-start.sh ${KAFKA_DIR}/config/kraft/server.properties
ExecStop=${KAFKA_DIR}/bin/kafka-server-stop.sh
Restart=on-abnormal

[Install]
WantedBy=multi-user.target
EOT

# Start Kafka
echo "Starting Kafka..."
sudo systemctl daemon-reload # Reload systemd to recognize new service files
sudo systemctl enable kafka-kraft.service
sudo systemctl start kafka-kraft.service

# Wait for Kafka to start
echo "Waiting for Kafka to start..."
while ! nc -z localhost 9092; do
  sleep 1
  # Add a timeout check to prevent infinite loop
  let TIMEOUT_COUNT++
  if [ $TIMEOUT_COUNT -gt 60 ]; then
    echo "Kafka startup timed out after 60 seconds. Check the logs: sudo journalctl -u kafka-kraft.service"
    exit 1
  fi
done
echo "Kafka started."

echo "Kafka installation with KRaft mode completed!"
echo "Kafka is running on port 9092"
echo "Cluster ID: $CLUSTER_ID (saved in $KAFKA_DIR/cluster-id)"
echo ""
echo "To check the service status: sudo systemctl status kafka-kraft.service"
echo "To view logs: journalctl -u kafka-kraft.service"

# Uncomment if you want to create a default topic at install time
# echo "Creating default Kafka topic..."
# sudo $KAFKA_DIR/bin/kafka-topics.sh --create --topic plant_monitoring \
#   --bootstrap-server localhost:9092 \
#   --partitions 1 --replication-factor 1
#
# echo "Kafka setup complete. Topic 'plant_monitoring' created."
