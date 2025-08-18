# digital-twin-plant

This thesis will focus on the practical implementation of a Digital Twin integrated in the framework of Internet of Things to monitor the health of a plant, using various sensors as data collectors and a Raspberry Pi as a central device.

# TODO

- Making Mock-up of Sensors ✅
- Configuring the MQTT broker ✅
- Make the sensor manager send the sensors data using MQTT ✅
- Displaying the data received by MQTT on the web app ✅
- Make a kind of "Global checkpoint" that will receive all the data send by the backend and update the corresponding fields on the web application
- Store the data in the database

    > ⚠️ The dabase and the dashboard run indepently of the main digital twin code

- Install kafka, influxdb
- See if the current implementation works
- Add a way to modify the read interval of sensors from the dashboard and of course ways to activate actuators (REST API ?)

# Dependencies

- Kafka `bash setup_kafka.sh`
- Influxdb `sudo apt install influxdb2`
- SPark (thus java 17 (max))

# INSTALLATION PATH

- RPI-imager -> os lite 64 bit
- `sudo apt update && sudo apt upgrade` 
- `sudo apt install python3 python3-pip git curl build-essential` 
- `sudo raspi-config`
  - Enable auto-login
  - Enable SSH server
  - Enable I2C kernel auto-loading
  - Enable one-wire  interface
  - Enable Remote GPIO access
- Clone repo
- `poetry install && poetry update`
- Setup kafka
- Setup influxdb

