#!/bin/bash

# This script installs and configures InfluxDB 2.x on a Debian-based system.
# It follows the official InfluxData documentation to add the repository,
# install the package, and enable the service.

echo "--- Setting up InfluxDB ---"

# --- Add InfluxDB APT Repository ---
# 1. Download the InfluxDB public GPG key.
# 2. Verify the checksum of the downloaded key.
# 3. Add the key to the system's trusted keys.
# 4. Add the InfluxDB repository to the APT sources list.
echo "Adding InfluxDB repository..."
curl --silent --location -O https://repos.influxdata.com/influxdata-archive.key
echo "943666881a1b8d9b849b74caebf02d3465d6beb716510d86a39f6c8e8dac7515  influxdata-archive.key" |
  sha256sum --check - && cat influxdata-archive.key |
  gpg --dearmor |
  sudo tee /etc/apt/trusted.gpg.d/influxdata-archive.gpg >/dev/null &&
  echo 'deb [signed-by=/etc/apt/trusted.gpg.d/influxdata-archive.gpg] https://repos.influxdata.com/debian stable main' |
  sudo tee /etc/apt/sources.list.d/influxdata.list

# --- Install InfluxDB ---
# Update the package list to include the new repository and install influxdb2.
echo "Installing InfluxDB..."
sudo apt-get update && sudo apt-get install -y influxdb2

# --- Enable and Start InfluxDB Service ---
# Use systemctl to enable the InfluxDB service to start on boot and
# start it immediately.
echo "Enabling and starting InfluxDB service..."
sudo systemctl enable influxdb
sudo systemctl start influxdb

echo "InfluxDB setup complete."
echo "You can now set up your initial user, organization, and bucket by navigating to http://<your-server-ip>:8086"
