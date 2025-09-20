import os
import time
from datetime import datetime, timezone

import influxdb_client
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

from dt.communication.topics import Topics
from dt.utils.dataclasses import SensorData, SensorDataClass

token = "TWqFtTMaU8eO_Zu2TnN_BBGlkdzghfB2dyB9qwO4R6x7hRzLMx1LcPkjCJ-mxTtiwPRFsO2JRvk6qvgOuZ_KVw=="
org = "dt-ulb"
url = "http://localhost:8086"

write_client = influxdb_client.InfluxDBClient(url=url, token=token, org=org)
bucket = "plant-health-monitoring"

write_api = write_client.write_api(write_options=SYNCHRONOUS)

# for value in range(5):
#     point = Point("measurement1").tag("tagname1", "tagvalue1").field("field1", value)
#     data: SensorData = SensorData(
#         sensor_id=0,
#         value=value,
#         unit="%",
#         timestamp=float(time.time()),
#         topic=Topics.SOIL_MOISTURE,
#     )
#     point = (
#         Point("sensor_data")
#         .field("sensor_id", str(data.sensor_id))
#         .field("data_type", data.data_type)
#         .field("value", data.value)
#         .field("unit", data.unit)
#         # Transform a timestamp to a datetime utc
#         .time(datetime.fromtimestamp(data.timestamp, tz=timezone.utc))
#     )
#     write_api.write(bucket=bucket, org="dt-ulb", record=point)
#     time.sleep(1)  # separate points by 1 second

for value in range(5):
    data: SensorDataClass = SensorDataClass(
        sensor_id=0,
        name=f"sensor_{value}",
        pin=value,
        read_interval=2,
    )
    point = (
        Point("sensor")
        .tag("sensor_id", data.sensor_id)
        .tag("name", data.name)
        .field("pin", data.pin)
        .field("read_interval", str(data.read_interval))
    )
    write_api.write(bucket=bucket, org="dt-ulb", record=point)
    time.sleep(1)  # separate points by 1 second
