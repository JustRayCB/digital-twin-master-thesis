#!/bin/bash

INFLUXDB_URL="http://localhost:8086"
INFLUXDB_TOKEN="ttX_TQAsmsu9SAJ0xUGosEdA72b6DJoIFhbOYK8iRzRMHl5dggZAJwbPsGjxt8K-mgdSIPKEkuXUIsGOWxDotA=="
INFLUXDB_ORG="dt-ulb"
BUCKET="plant-health-monitoring"

# Get current UTC time in the expected format
CURRENT_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

echo "Deleting all data from bucket '$BUCKET'..."
influx delete \
  --bucket "$BUCKET" \
  --start "1970-01-01T00:00:00Z" \
  --stop "$CURRENT_TIME" \
  --token "$INFLUXDB_TOKEN" \
  --org "$INFLUXDB_ORG" \
  --host "$INFLUXDB_URL"

echo "All data deleted from bucket '$BUCKET'"
