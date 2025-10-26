"""
This script provides an example of how to query data from an InfluxDB bucket
using the influxdb-client-python library.

It demonstrates how to:
- Connect to an InfluxDB instance.
- Construct a Flux query to retrieve data within a specific time range and
  filter by a measurement and a tag.
- Execute the query and process the results.

Before running, ensure that the InfluxDB connection details (URL, token, org,
bucket) are correctly set.

To run this script, execute the following command from the root of the project:
  poetry run python dt/scripts/hands-on-scripts/software/influx/query.py
"""

from datetime import datetime, timezone

import influxdb_client

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
client = influxdb_client.InfluxDBClient(url=url, token=token, org=org)
query_api = client.query_api()

# --- Define Query Parameters ---
# Set the time range for the query.
from_timestamp = datetime(2024, 1, 1).timestamp()  # Example start time
to_timestamp = datetime.now().timestamp()  # Current time

# Convert Python datetime objects to RFC3339 format, which is required by Flux.
from_time_str = datetime.fromtimestamp(from_timestamp, tz=timezone.utc).isoformat()
to_time_str = datetime.fromtimestamp(to_timestamp, tz=timezone.utc).isoformat()

# --- Construct Flux Query ---
# This Flux query retrieves data from the specified bucket within the given time range.
# - It filters by the "_measurement" which is 'sensor_data'.
# - It filters by the "data_type" tag, set to 'soil_moisture' in this example.
# - It uses `pivot` to transform the data from a columnar format to a row-based format,
#   which is often easier to work with.
query = f"""
from(bucket: "{bucket}")
    |> range(start: {from_time_str}, stop: {to_time_str})
    |> filter(fn: (r) => r["_measurement"] == "sensor_data")
    |> filter(fn: (r) => r["data_type"] == "soil_moisture")
    |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
"""

print("--- Executing InfluxDB Query ---")
print(f"Query:\n{query}")

# --- Execute Query and Process Results ---
try:
    tables = query_api.query(query, org=org)
    print("\n--- Query Results ---")
    if not tables:
        print("No data returned from query.")
    else:
        # Iterate through the tables and records in the response.
        for table in tables:
            for record in table.records:
                # Each record represents a row in the query result.
                # The `record.values` dictionary contains the data.
                print(
                    f"Time: {record.get_time()}, "
                    f"Sensor ID: {record.values.get('sensor_id', 'N/A')}, "
                    f"Value: {record.values.get('value', 'N/A')}, "
                    f"Unit: {record.values.get('unit', 'N/A')}"
                )
except Exception as e:
    print(f"An error occurred while querying InfluxDB: {e}")
finally:
    # --- Close the Client ---
    # It's important to close the client to release resources.
    client.close()
    print("\n--- InfluxDB client closed ---")
