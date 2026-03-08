#!/bin/bash

# This script sets up the development environment for the digital twin project on a
# Debian-based system (like Ubuntu or Raspberry Pi OS). It installs system
# dependencies, Java, and Python project dependencies using Poetry.

# Note: It is recommended to run `sudo apt update && sudo apt upgrade` manually
# before executing this script to ensure all system packages are up-to-date.

# --- Install System Dependencies ---
# Installs essential packages:
# - python3 and python3-pip: For running Python applications.
# - git: For version control.
# - curl: For downloading files from the internet.
# - build-essential: For compiling software from source.
echo "Installing system dependencies..."
sudo apt install -y python3 python3-pip git curl build-essential npm, python3-libcamera python3-picamera2

# --- Install Java Development Kit (JDK) ---
# Installs OpenJDK 17, which is required for running Kafka and Spark.
echo "Installing OpenJDK 17..."
sudo apt install -y openjdk-17-jre
sudo apt install -y openjdk-17-jdk

# --- Install Poetry ---
# Downloads and installs Poetry, a dependency management tool for Python.
echo "Installing Poetry..."
curl -sSL https://install.python-poetry.org | python3 -

# --- Install Python Dependencies ---
# Installs the Python packages defined in pyproject.toml and poetry.lock.
# It also updates the dependencies to their latest allowed versions.
# This command needs to be run from the root of the project directory.
echo "Installing Python dependencies with Poetry..."
poetry install && poetry update

echo "Setup complete."
echo "Note: The InfluxDB and Kafka setup scripts were not run automatically."
echo "You can run them manually if needed:"
echo "  bash ./scripts/setup_influxdb.sh"
echo "  bash ./scripts/setup_kafka.sh"

# The following lines are commented out by default to allow for more granular setup.
# Uncomment them if you want to automatically set up InfluxDB and Kafka as well.
# bash ./scripts/setup_influxdb.sh
# bash ./scripts/setup_kafka.sh
