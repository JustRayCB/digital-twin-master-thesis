> Topics: raw.sensor.*, proc.sensor.*, alerts.*, actions.*, control.events.*, audit.*  
> IDs: correlation_id propagated end-to-end  
> Storage: Influx ‘events’ + Relational Action/Audit (SQLite→Postgres)  

# Design Patterns, Coding Standards

## Architecture & Design Patterns

The project embraces a **Microservices and Event-Driven** design pattern. Each
functional area (sensing, preprocessing, storage, analytics, UI) is implemented
as an independent service/module, communicating via a **publish-subscribe**
model (Kafka topics) and REST interfaces. This is essentially an **event-driven
architecture**: sensors produce events, and multiple consumers (data cleaner,
database, ML, UI) react to those events. The benefits of this pattern are
evident in the system's flexibility and scalability as new sensor types or new
processing modules can be added by simply introducing a new Kafka topic and
consumer, without disrupting existing components. Moreover, the use of Kafka
decouples producers and consumers in time, if one component goes down
temporarily, Kafka buffers the data, and consumers can catch up, which adds
resilience.

The **Observer pattern** is inherent in how components subscribe to Kafka
topics (the broker notifies subscribers of new messages). For example, the web
dashboard and AI service both observe the stream of processed sensor data and
react accordingly. Similarly, the alerting mechanism (part of the AI/analytics
module) observes the incoming data for threshold breaches.

Another key pattern is the separation of **concerns and layering** in the
system. The data flow pipeline is segmented: acquisition -> preprocessing ->
storage/analysis -> presentation. By clearly separating these stages, the
system follows a **pipeline pattern** where each stage transforms or handles
data and passes it along. This makes the workflow easier to manage and test in
pieces.

The codebase heavily utilizes **Object-Oriented Programming (OOP)** principles
within each module. Classes and objects represent key abstractions (e.g., a
SensorManager class for the data collector, or a KafkaService in the communication module).
This OOP approach promotes encapsulation and reusability, it is
explicitly noted that each module's implementation encourages code reuse and
ease of extension as the system evolves. This pattern means that if a new
sensor needs to be integrated or a new algorithm added, the developers can
subclass or extend existing classes rather than rewriting functionality,
maintaining a clean structure.

For future development, the architecture is set to incorporate patterns
relevant to control systems and MLOps. The Phase P2 **closed-loop control**
introduces a classic **feedback control pattern**: sensor data -> decision
logic -> actuation -> effect on environment -> new sensor data. The software
will include controllers (likely implemented with simple rule-based or PID
patterns) that adjust actuators based on sensor feedback. This will be done in
a safe manner (with interlocks and manual override), following design patterns
from control engineering (e.g., fail-safes, hysteresis in control to avoid
rapid toggling).

On the analytics side (Phase P3), the project plans to adopt an **MLOps**
pattern by integrating a **model registry** and pipeline for training/serving
models. The use of MLflow or a similar tool for model versioning is
anticipated. This introduces patterns like **Continuous Training/Deployment**
of models and monitoring for model drift (triggering retraining or alerts when
performance drops). While these are beyond the current implementation, they
shape the system's architecture: for instance, the AI module is being built
with a placeholder model registry hook in mind so that in future, models can be
swapped or updated seamlessly.

It's also worth highlighting the **audit trail** pattern used for system
actions. Every important event (control commands issued, alerts generated,
configuration changes) will produce a log entry with a unique correlation ID
that ties together cause and effect through the system. This pattern of
**correlation IDs propagated end-to-end** is a design choice to enable
traceability. You can trace, for example, a high temperature reading from
sensor, through the decision that triggered a fan on, to an entry in the audit
database that the fan was activated at a certain time by the automation logic.
This is a common enterprise design pattern for observability in distributed
systems and is being adopted here to ensure the digital twin's actions are
transparent and debuggable.

In summary, the system's architecture patterns emphasize modularity
(microservices, pipeline), reactivity (event-driven pub/sub), and
maintainability (OOP, separation of concerns). These choices align with the
goals of scalability and flexibility. As the project progresses, patterns for
control loops and continuous ML integration will further enrich the system's
design, ensuring that even as complexity grows, the system remains organized
and understandable.

## Coding Standards & Practices

The codebase follows standard **Python coding conventions** (PEP8 style for
naming, formatting, etc.) and is organized for clarity. Early in the project, a
consistent repository structure was established: all code resides under a dt/
package with clear sub-packages for each module (data/, ai/, webapp/, utils/,
etc.), as outlined in the kickoff phase. This structure makes it easy to
navigate the project and locate relevant code (for example, anything related to
data processing is in dt/data/...). Configuration is managed via a central
**config file and environment variables** (a .env file and config.py) to
avoid hard-coding parameters and credentials. This means things like database
URLs, API keys, sensor calibration constants, etc., can be changed in one place
without modifying the code, adhering to the **12-factor app** principles for
config separation.

**Dependency management** is handled with Poetry (as mentioned), which ensures
that all contributors or deployments use the same library versions. The project
likely includes a pyproject.toml with pinned versions, and a lockfile for
reproducibility. This is complemented by environment spec
for deploying on the Raspberry Pi (making use of Poetry's export or the extras
groups defined for raspi, spark, dev to install appropriate subsets of
packages). Ensuring the Pi doesn't install heavy dev or Spark libraries unless
needed was a thought-out step, indicating a mindful approach to environment
management.

In the current phase, the project introduced unit tests to verify that each
module performs as expected.  Already in the preprocessing phase, unit tests
were planned for schema validation and other functionalities. The code includes
test cases (using **pytest**) to verify that each module performs as expected
(e.g., does the missing-data handler fill gaps correctly? Do alerts fire under
the right conditions?). 

Currently, the project utilizes Python's built-in `logging` package for
application logs. While logs are not yet structured in JSON or unified by a
correlation ID, the codebase could follow a more advanced logging
strategies in the future. 

**Documentation** and contributor guidelines are treated seriously. The roadmap
indicates deliverables such as CONTRIBUTING.md and technical documentation
(e.g., preprocessing-spec.md, an alert catalog, etc.). This means the code
likely contains docstrings (numpydoc-style) and comments where complex logic
occurs, and the repository includes markdown docs for setup instructions,
design decisions, and how to contribute/test. Adhering to these documentation
standards ensures new contributors (or the future self) can understand the code
and system design without guesswork.

In coding style, one can infer that the project values clarity and
maintainability. Functions and classes are probably kept concise, following
single-responsibility principle (since each service itself has a single
responsibility, and within a service, components likely mirror that). The use
of type hints in Python could be present to improve code clarity and catch type
errors. 

Finally, the project integrates **DevOps practices** like using a Makefile for
common operations (as seen in the installation instructions). This provides a
simple interface to run the system (make main, make web, make db, etc.) and can
enforce running things like linters or tests via make targets. Continuous
deployment isn't currently implemented (since this is a prototype), but the
groundwork (unit tests) sets the stage for easy deployment when the time comes.

In summary, the coding standards revolve around **maintainability, and
reliability**: a clean project structure, thorough documentation, environment
consistency, rigorous testing, and logging/monitoring to know what's happening
internally. These practices ensure that the digital twin system can be
confidently extended and used, aligning with the goal of a reproducible and
high-quality outcome.
