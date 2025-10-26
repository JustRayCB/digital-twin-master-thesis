# Tech Stack, Libraries, Architecture

## Hardware Platform & Sensors

The prototype runs on a **Raspberry Pi 4B** as the core hardware platform
(running Raspberry Pi OS with Python 3.11). The Raspberry Pi interfaces with
several **environmental sensors** to capture the plant's context and state. Key
sensors include an **Adafruit STEMMA Soil Sensor** (capacitive moisture sensor
with temperature sensing) communicating via I²C, a **DHT22** digital sensor for
ambient temperature and humidity (GPIO interface), a **BH1750** ambient light
sensor (I²C, range 1-65,535 lux), and a **Raspberry Pi Camera Module** for
capturing images of the plant. These specific sensors were chosen compatibility
with the Pi's GPIO/I2C interfaces, and cost-effectiveness. They provide the
essential data points defined by the project: soil moisture, air temperature,
humidity, light intensity, and visual cues of plant health (via images). The
hardware setup also includes actuators (planned for later phases) like a water
pump, lights, heater resistor and a fan, which will be used in the feedback
control loop once implemented (Phase P2). 

## Software Stack

The system is implemented in **Python**, chosen for its simplicity and rich
ecosystem in data science and IoT. The project uses **Poetry** for Python
dependency management, ensuring reproducible environments and easy packaging.
Low-level sensor interfacing is greatly simplified by the **Adafruit
CircuitPython** libraries, which provide high-level drivers for each sensor
(e.g., adafruit_dht for DHT22, adafruit_bh1750 for the light sensor, etc.). The
Raspberry Pi's GPIO control uses the standard **RPI.GPIO** library for any
direct pin interactions.

For the web interface, the project employs **Flask**, a lightweight Python web
framework, to serve a dashboard and RESTful endpoints. The dashboard front-end
uses JavaScript libraries **Socket.IO** (for real-time bi-directional
communication) and **Plotly.js** (for interactive charts) to display live
sensor data and alerts in the browser. This allows users to observe plant
conditions in real time and interact with the system (e.g., acknowledge alerts
or in the future, adjust settings).

A critical part of the stack is the data pipeline for streaming analytics. The
project sets up **Apache Kafka** as the central message broker to enable an
**event-driven architecture**. All sensor readings are published as events to
Kafka topics (e.g., raw sensor data topic), allowing decoupling between
producers (sensor module) and consumers (processing, storage, etc.). Kafka
provides a scalable, resilient pipeline for real-time streaming data. On top of
this, **Apache Spark (PySpark)** is used for streaming data processing. The
**Spark Structured Streaming** API (accessed via PySpark) handles continuous
processing of sensor data, enabling the preprocessing module to clean and
transform data on the fly and handle large volumes gracefully. Spark was chosen
for its ability to perform complex computations (like windowed aggregations,
anomaly detection) in real-time and because it can scale beyond the single Pi
if needed by distributing jobs.

For data storage, the system utilizes **InfluxDB**, a time-series database
optimized for sensor data. InfluxDB stores historical sensor readings and makes
queries efficient (e.g., retrieving the last 24 hours of moisture readings). It
is deployed on the Pi (or a server) to archive all incoming processed data with
timestamps. Additionally, a relational database is used as an **Action & Audit
log store**: initially SQLite for development, with plans to move to PostgreSQL
in production. This relational store keeps records of system actions, alerts,
and configuration changes, enabling complex queries like "who triggered this
action and why" for accountability.

It's worth noting that **Java 17** is required on the system to run Kafka and
Spark, and the setup scripts ensure these services (Kafka broker, InfluxDB) are
installed and configured on the Pi. The project provides setup scripts
(setup_kafka.sh, setup_influxdb.sh) and uses a Makefile for common tasks
(running modules, etc.) to streamline environment setup.

## System Architecture

The application follows a **microservices-inspired architecture**, breaking the
system into distinct components (services) that communicate through Kafka
events and REST APIs. Each major function of the digital twin is a separate
module/process under a top-level package dt/. For example: 
- The **Data Collector** module (dt/main.py) reads sensor inputs in real-time and
  immediately publishes raw data to Kafka. This service runs on the Raspberry Pi
  (since it directly accesses GPIO and I2C hardware) and uses CircuitPython
  libraries to interface with sensors. 
- The **Data Preprocessing** module (dt/data/preprocess/main.py) subscribes to
  the raw data stream from Kafka, performs cleaning and preprocessing (described
  in Active Context below), and then publishes **processed** sensor data back to
  another Kafka topic for downstream consumers. This module is implemented with
  PySpark to leverage structured streaming for data handling. 
- The **Data Storage** service
  (dt/data/database/app.py) consumes the processed data and stores it into
  InfluxDB in near real-time. It also provides a REST API for querying historical
  data (so that other services or the web dashboard can request data without
  speaking directly to the database). 
- The **AI/Analytics** service (dt/ai/app.py) is responsible for machine
  learning tasks. In the current prototype, this might simply log data or perform
  basic anomaly detection. In later phases it will host predictive models (e.g.,
  a moisture forecast, a health classifier) and manage a **model registry** for
  versioning ML models. It will expose REST endpoints to deliver predictions or
  analytics results to other components. 
- The **Web Dashboard** module (dt/webapp/app.py) is a Flask application that
  serves the user interface. It subscribes to the Kafka processed-data topic (via
  a WebSocket or Socket.IO connection) to get live updates and also calls the
  REST APIs of other services (like AI service or storage) to fetch analysis
  results or historical data for visualization. The dashboard displays real-time
  sensor readings, recent alerts, and system status, and in future will allow
  user controls (like triggering manual actuator overrides or uploading new model
  configurations) and plant state visualization.

Communication between these components is largely asynchronous and
event-driven, thanks to Kafka. For instance, the Data Collector doesn't need to
know who will use the data; it simply produces messages. The processing,
storage, and AI modules **subscribe** to the relevant topics (pub/sub pattern),
ensuring a decoupled design. Where direct querying or commands are needed,
RESTful APIs are used (e.g., the web app requesting a report from the storage
service). This dual communication mode (Kafka for streaming data, REST for
queries/commands) provides both real-time responsiveness and request-reply
capabilities.

The architecture's modularity and loose coupling not only make the system
easier to extend, but also support scalability and resilience. Each service can
be developed and tested in isolation, and potentially deployed on separate
hardware or containers. In fact, although the initial deployment is on a single
Raspberry Pi for convenience, the components could be distributed (for example,
running the web dashboard on a PC while the data collector runs on the Pi) by
adjusting configuration endpoints. The design allows migration to cloud
infrastructure if needed in the future without fundamental changes.
