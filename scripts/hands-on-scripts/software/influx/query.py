import os
import time
from datetime import datetime, timezone

import influxdb_client
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

from dt.communication.topics import Topics
from dt.utils.dataclasses import SensorData

token = "TWqFtTMaU8eO_Zu2TnN_BBGlkdzghfB2dyB9qwO4R6x7hRzLMx1LcPkjCJ-mxTtiwPRFsO2JRvk6qvgOuZ_KVw=="
org = "dt-ulb"
url = "http://localhost:8086"

write_client = influxdb_client.InfluxDBClient(url=url, token=token, org=org)
bucket = "plant-health-monitoring"

write_api = write_client.write_api(write_options=SYNCHRONOUS)

from_timestamp = 1743182501.272
to_timestamp = 1745774501.272
from_time = datetime.fromtimestamp(from_timestamp, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
to_time = datetime.fromtimestamp(to_timestamp, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

# |> pivot(rowKey:["_time", "sensor_id", "data_type"], columnKey: ["_field"], valueColumn: "_value")
query = f"""from(bucket: "plant-health-monitoring")
             |> range(start: {from_time}, stop: {to_time})
             |> filter(fn: (r) => r["_measurement"] == "sensor_data")
             |> filter(fn: (r) => r["data_type"]== "soil_moisture")
             |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")

 """
# sensor_name = "sensor_0"
# query = f"""from(bucket: "plant-health-monitoring")
#                 |> range(start: -30d)
#                 |> filter(fn: (r) => r._measurement == "sensor")
#                 |> filter(fn: (r) => r.name == "{sensor_name}")
#                 |> limit(n: 1)
#
#  """
query_api = write_client.query_api()
tables = query_api.query(query)
results = []
print(tables)
for table in tables:
    for record in table.records:
        # sensor_id = int(record.values.get("sensor_id", -1))
        # print(f"Sensor ID: {sensor_id}")
        # timestamp = record.get_time().timestamp()
        print(f"Timestamp: {record.get_time()}")
        print(record)
