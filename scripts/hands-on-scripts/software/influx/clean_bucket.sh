#!/bin/bash

# This script deletes all data from a specified InfluxDB bucket.
# It uses the `influx` CLI to perform the delete operation, removing all points
# from the beginning of epoch time (1970-01-01) to the current time.
#
# WARNING: This is a destructive operation. Make sure you have backups or are
# running this in a development environment.

# --- Configuration ---
# Set the following variables to match your InfluxDB setup. It is recommended
# to use environment variables for sensitive data like tokens in a production
# environment.
INFLUXDB_URL="http://localhost:8086"
INFLUXDB_TOKEN="my-influxdb-token" # Replace with your actual InfluxDB token
INFLUXDB_ORG="dt-ulb"
BUCKET="dt-ulb-bucket" # The name of the bucket to clean

# Get the current time in RFC3339 format, which is required by the --stop flag.
CURRENT_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

echo "--- InfluxDB Bucket Cleaner ---"
echo "This script will delete all data from the bucket: '$BUCKET'."
read -p "Are you sure you want to continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Operation cancelled."
    exit 1
fi

echo "Deleting all data from bucket '$BUCKET'..."

# --- Execute InfluxDB Delete Command ---
# The `influx delete` command removes data within a specified time range.
# --start: The beginning of the time range (1970-01-01T00:00:00Z is the Unix epoch).
# --stop: The end of the time range (set to the current time).
# --bucket, --token, --org, --host: Connection parameters for InfluxDB.
influx delete \
  --bucket "$BUCKET" \
  --start "1970-01-01T00:00:00Z" \
  --stop "$CURRENT_TIME" \
  --token "$INFLUXDB_TOKEN" \
  --org "$INFLUXDB_ORG" \
  --host "$INFLUXDB_URL"

echo "All data successfully deleted from bucket '$BUCKET'."
