"""
This script provides an example of how to write data to an InfluxDB bucket
using the influxdb-client-python library.

It demonstrates how to:
- Connect to an InfluxDB instance.
- Create `Point` objects to represent time-series data.
- Write these points to a specified bucket synchronously.

The script includes two examples:
1. (Commented out) Writing sensor measurement data (`SensorData`).
2. (Active) Writing sensor metadata (`SensorDescriptor`).

Before running, ensure that the InfluxDB connection details (URL, token, org,
bucket) are correctly set in the configuration.

To run this script, execute the following command from the root of the project:
  poetry run python dt/scripts/hands-on-scripts/software/influx/write.py
"""

import time
from datetime import datetime, timezone

import influxdb_client
from influxdb_client import Point
from influxdb_client.client.write_api import SYNCHRONOUS

from dt.communication.dataclasses import SensorDescriptor
from dt.utils import Config

# --- InfluxDB Connection Configuration ---
# It's recommended to use environment variables for sensitive data like tokens.
# These values are fetched from the central configuration.
token = Config.INFLUX_TOKEN
org = Config.INFLUX_ORG
url = Config.INFLUX_URL
bucket = Config.INFLUX_BUCKET

# --- Initialize InfluxDB Client ---
# Create a client object to interact with the InfluxDB API.
# The `write_api` is configured for SYNCHRONOUS writing, which means the
# script will wait for the write to complete before proceeding.
client = influxdb_client.InfluxDBClient(url=url, token=token, org=org)
write_api = client.write_api(write_options=SYNCHRONOUS)

print(f"--- Writing data to InfluxDB bucket '{bucket}' ---")

# --- Example 1: Writing Sensor Measurement Data (Commented Out) ---
# This example demonstrates how to write time-series data, such as sensor readings.
# A `Point` is created with a measurement name ('sensor_data'), tags for querying
# (sensor_id, data_type), fields for the actual values (value, unit), and a timestamp.
# --------------------------------------------------------------------
# print("\nWriting sensor measurement data (example)...")
# for value in range(5):
#     sensor_data = SensorData(
#         plant_id=1,
#         sensor_id=1,
#         value=float(value * 10),
#         unit="%",
#         timestamp=time.time(),
#         topic=Topics.SOIL_MOISTURE,
#         correlation_id="",
#     )
#     point = (
#         Point("sensor_data")
#         .tag("sensor_id", str(sensor_data.sensor_id))
#         .tag("data_type", sensor_data.data_type)
#         .field("value", sensor_data.value)
#         .field("unit", sensor_data.unit)
#         .time(datetime.fromtimestamp(sensor_data.timestamp, tz=timezone.utc))
#     )
#     write_api.write(bucket=bucket, org=org, record=point)
#     print(f"Wrote point: {sensor_data.value}")
#     time.sleep(1)

# --- Example 2: Writing Sensor Metadata (Active) ---
# This example shows how to store metadata, such as sensor configurations.
# Here, we use a measurement named 'sensors' and store the sensor's name, pin,
# and read interval as fields. The sensor ID and name are also used as tags
# to facilitate querying.
# --------------------------------------------------------------------
print("\nWriting sensor metadata...")
for i in range(3):
    sensor_descriptor = SensorDescriptor(
        sensor_id=i,
        name=f"sensor_{i}",
        pin=i,
        read_interval=5,
    )
    point = (
        Point("sensors")
        .tag("sensor_id", str(sensor_descriptor.sensor_id))
        .tag("name", sensor_descriptor.name)
        .field("pin", sensor_descriptor.pin)
        .field("read_interval", sensor_descriptor.read_interval)
        .time(datetime.now(timezone.utc))  # Use current time for metadata entry
    )
    write_api.write(bucket=bucket, org=org, record=point)
    print(f"Wrote metadata for sensor: {sensor_descriptor.name}")
    time.sleep(1)

# --- Close the Client ---
# It's important to close the client to release resources.
client.close()
print("\n--- InfluxDB client closed ---")
