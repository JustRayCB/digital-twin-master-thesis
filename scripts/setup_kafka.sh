#!/bin/bash

# This script automates the installation and configuration of a single-node
# Apache Kafka cluster running in KRaft mode on a Debian-based system.
# It handles dependency installation, user creation, Kafka download,
# configuration, and setting up a systemd service for management.

set -e # Exit immediately if a command exits with a non-zero status.

# --- Get Network Information ---
# Fetches the public and local IP addresses, which are used to configure
# Kafka's advertised listeners for both internal and external access.
echo "Fetching network information..."
PUBLIC_IP=$(curl -4s ifconfig.me)
if [ -z "$PUBLIC_IP" ]; then
    echo "Could not determine public IP address. Exiting."
    exit 1
fi
echo "Your public IP address is: $PUBLIC_IP"
LOCAL_IP=$(ip -4 addr show | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | grep -v '^127\.' | head -n 1)

# Variables
KAFKA_VERSION="4.0.0"
SCALA_VERSION="2.13"
KAFKA_DIR="/opt/kafka"
KAFKA_TARBALL="kafka_${SCALA_VERSION}-${KAFKA_VERSION}.tgz"
KAFKA_DOWNLOAD_URL="https://archive.apache.org/dist/kafka/${KAFKA_VERSION}/${KAFKA_TARBALL}"
JAVA_PACKAGE="default-jdk"
DEPENDENCIES="net-tools jq netcat-traditional"
DATA_DIR="/var/kafka-logs"
KAFKA_USER="kafka"

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

# --- Setup Kafka User and Directories ---
echo "Setting up Kafka user and directories..."
if id "$KAFKA_USER" &>/dev/null; then
    echo "User '$KAFKA_USER' already exists."
else
    sudo useradd -r -d $KAFKA_DIR -s /bin/false $KAFKA_USER
    echo "Created user '$KAFKA_USER'."
fi

sudo mkdir -p $KAFKA_DIR $DATA_DIR
sudo chown -R $KAFKA_USER:$KAFKA_USER $KAFKA_DIR $DATA_DIR
sudo chmod -R 755 $KAFKA_DIR $DATA_DIR
# Add the current user to the kafka group to allow management
sudo usermod -aG $KAFKA_USER $USER

# Download Kafka
echo "Downloading Kafka version $KAFKA_VERSION..."
wget -q $KAFKA_DOWNLOAD_URL -O /tmp/$KAFKA_TARBALL

# Extract Kafka
echo "Extracting Kafka..."
sudo tar -xzf /tmp/$KAFKA_TARBALL -C $KAFKA_DIR --strip-components 1
rm /tmp/$KAFKA_TARBALL

# Create kraft directory if it doesn't exist
echo "Configuring Kafka for KRaft mode..."
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
listeners=PLAINTEXT://0.0.0.0:9092,EXTERNAL://0.0.0.0:19092,CONTROLLER://localhost:9093
advertised.listeners=PLAINTEXT://$LOCAL_IP:9092,EXTERNAL://$PUBLIC_IP:19092
listener.security.protocol.map=CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT,EXTERNAL:PLAINTEXT
inter.broker.listener.name=PLAINTEXT

# Log directory
log.dirs=$DATA_DIR

# Default Topic configurations
num.partitions=1
default.replication.factor=1
offsets.topic.replication.factor=1
transaction.state.log.replication.factor=1
transaction.state.log.min.isr=1
auto.create.topics.enable=true
# Keep logs for 2 days
log.retention.hours=48
EOF

# num.network.threads=3
# num.io.threads=8
# log.segment.bytes=1073741824
# log.retention.check.interval.ms=300000

# Format the storage directory
echo "Formatting Kafka storage directory..."
sudo -u $KAFKA_USER $KAFKA_DIR/bin/kafka-storage.sh format -t $CLUSTER_ID -c $KAFKA_DIR/config/kraft/server.properties


# Create systemd service files for Kafka
echo "Setting up Kafka systemd service..."
sudo tee /etc/systemd/system/kafka-kraft.service >/dev/null <<EOT
[Unit]
Description=Apache Kafka in KRaft Mode
Requires=network.target
After=network.target

[Service]
Type=simple
User=$KAFKA_USER
Group=$KAFKA_USER
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
