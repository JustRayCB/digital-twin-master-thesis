# Core Goals, Requirements, Constraints

Goals: The primary aim of the project is to design and implement a modular,
scalable digital twin prototype for plant health monitoring. This digital twin
system should enable real-time tracking of a plant's health parameters and
provide a user-friendly dashboard for data visualization and interaction. In
practical terms, the project goals include delivering a robust, scalable
Digital Twin with a closed-loop control capability (automated feedback to
actuators like irrigation or lighting), a real-time monitoring dashboard, and
baseline machine learning features for prediction/classification. Another key
goal is to produce a high-quality thesis and a reproducible codebase - meaning
the software should be well-documented, tested, and set up with continuous
integration (CI) to ensure reliability.

Constraints (Out of Scope): The project's scope is deliberately focused on a
small-scale prototype. Certain ambitious features are not planned in the
current cycle, serving as constraints on development. These non-goals include
any full greenhouse-scale deployment, integration of complex 3D Functional
Structural Plant Models (FSPM) for plant growth, advanced computer vision for
plant disease detection, and multi-tenant cloud SaaS features. In other words,
the current system will monitor a single plant (or small setup) and prioritize
core functionality over scale; it will not attempt large-scale farm management
or highly advanced modeling at this stage. These constraints ensure the project
remains feasible within the academic timeframe and available resources.

Requirements & Challenges: Several core requirements and design challenges were
identified for the digital twin system. These set the criteria that the
solution must meet:

- Real-Time Data Collection: The system must collect and process sensor data in
  real time to enable timely interventions. This ensures no significant lag
  between physical changes and the digital twin's response (e.g. adjusting
  irrigation immediately if soil moisture drops).
- Reliability of Data: The fidelity of decisions made by the twin depends on
  reliable data collection. Sensor drift, failures, or calibration issues should
  be detected and handled, so that inaccurate readings don't lead to misleading
  insights. The system needs mechanisms for validating sensor inputs and handling
  faulty or noisy data (ensuring robust decision-making despite imperfect
  hardware).
- Modular Design: The architecture should be modular and extensible. Each
  functionality (data collection, preprocessing, storage, analytics, etc.) should
  be a separate component, allowing easy integration of new sensors or algorithms
  without a major redesign. This separation of concerns facilitates maintenance
  and future growth. The modules communicate through well-defined interfaces,
  making it possible to upgrade or replace parts of the system independently.
- Scalability: The solution should remain scalable as it grows. If more sensors
  are added or data volume increases, the system must handle the load without
  degrading real-time performance. The design should support horizontal scaling
  and possibly transition to more powerful infrastructure (e.g. cloud or
  distributed services) when needed, given that the prototype runs on a Raspberry
  Pi but may migrate to cloud servers in the future.

By meeting these requirements, the digital twin will form a solid foundation
that addresses immediate needs (monitoring a single plant with feedback) while
being adaptable for more complex future use cases.

## Architecture (v1)
- **Producers**: Raspberry Pi 4B + sensors (DHT22, BH1750, soil moisture, camera)
- **Backbone**: Kafka topics
  - `dt.sensor.*.raw`, `dt.sensor.*.proc`, `dt.alerts.*`, `dt.actions.*`,  `dt.audit.*`
- **Processing**: Spark Structured Streaming jobs for validation, calibration, alerts
- **Storage**:
  - **InfluxDB** for TS data (+ downsampling 1m/5m/1h)
  - **Relational Action & Audit Store** (SQLite→PostgreSQL) for non-TS events
- **Services**: Flask (+ Socket.IO) dashboard; AI service (batch/online scoring); Control service (GPIO abstractions, policies)

## Deliverables & success criteria (by Jun 2026)
- **P1** Preprocessing live, DQ dashboard; retention/downsampling configured
- **P2** Closed-loop with interlocks + manual override; simulation mode; ops runbook
- **P3** Forecast v1 + classifier v1; model registry; offline/online pipelines
- **P4** Enhanced UI (alerts center, controls, reports)
