# Preprocessing Pipeline Architecture

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Core Components](#core-components)
4. [Pipeline Stages](#pipeline-stages)
5. [Configuration](#configuration)
6. [Extending the Pipeline](#extending-the-pipeline)
7. [Testing](#testing)
8. [Troubleshooting](#troubleshooting)
9. [Examples](#examples)

---

## Overview

The preprocessing pipeline transforms raw sensor data from physical sensors into validated, calibrated, and normalized readings suitable for analytics, control systems, and machine learning models.

### What It Does

The pipeline takes a raw sensor reading (temperature, humidity, light intensity, soil moisture, etc.) and:

1. **Calibrates** the value to correct for sensor drift and manufacturing variations
2. **Validates** the reading against configured rules (range, rate-of-change, stuck values)
3. **Imputes** invalid readings using historical context
4. **Smooths** the signal to reduce noise
5. **Normalizes** values to a standard range [0, 1] for downstream processing

### Why This Architecture?

The original preprocessing implementation was a single 942-line file (`pipeline.py`) that became difficult to:

- **Read**: 20+ functions with mixed concerns and global state
- **Test**: Tight Spark coupling made unit testing nearly impossible
- **Maintain**: Global caches and intertwined logic
- **Extend**: Adding new processing steps required understanding the entire file

The refactored architecture uses the **Chain of Responsibility** pattern to address these issues:

- ✅ **Readable**: Each processor has a single, clear responsibility
- ✅ **Testable**: Components tested independently without Spark
- ✅ **Maintainable**: No global state, encapsulated caching
- ✅ **Extensible**: New processors can be added without modifying existing code

---

## Architecture

### High-Level Flow

```
┌─────────────┐
│ Raw Reading │
│  (Kafka)    │
└──────┬──────┘
       │
       v
┌─────────────────┐
│ ConfigManager   │  (Load config, resolve sensor, create strategies)
└─────────────────┘
       │
       v
┌──────────────────────────────────────────────────────────────┐
│                   ProcessingPipeline                         │
│                                                              │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐      │
│  │ Calibration  │ → │ Validation   │ → │ Imputation   │      │
│  │  Processor   │   │  Processor   │   │  Processor   │      │
│  └──────────────┘   └──────────────┘   └──────────────┘      │
│                                                │             │
│                                                v             │
│                     ┌──────────────┐   ┌──────────────┐      │
│                     │Normalization │ ← │ Smoothing    │      │
│                     │  Processor   │   │  Processor   │      │
│                     └──────────────┘   └──────────────┘      │
│                                                              │
└──────────────────────────────────────────────────────────────┘
       │
       v
┌─────────────────┐
│ Processed Data  │
│   (Kafka)       │
└─────────────────┘
```

### Data Flow Through Context

Each processor receives a `ProcessingContext` object, updates it, and passes it to the next processor:

```
ProcessingContext
├── reading (original raw data)
├── state_provider (historical context given by spark)
├── watermark_seconds (late event detection)
├── sensor_key (config identifier)
├── sensor_config (validation rules)
│
├── calibrated_reading ──────► Set by CalibrationProcessor
├── calibration_profile_id ───┘
│
├── flags ────────────────────► Set by ValidationProcessor
├── is_valid ─────────────────┤
├── is_late_event ────────────┤
├── dq_score ─────────────────┘
│
├── imputed ──────────────────► Set by ImputationProcessor
├── imputed_value ────────────┘
│
├── smoothed_value ───────────► Set by SmoothingProcessor
│
├── normalized_value ─────────► Set by NormalizationProcessor
└── normalization_profile_id ─┘
```

### Package Structure

```
dt/data/preprocess/
├── configuration/
│   ├── __init__.py              # Shared config exports
│   ├── preprocessing_config.py  # Sensor validation schema
│   ├── profiles.py              # Calibration/normalization profiles
│   ├── catalog.py               # Profile lookup catalog
│   └── manager.py               # ConfigurationManager
├── pipeline/
│   ├── __init__.py              # Package exports
│   ├── context.py               # ProcessingContext dataclass
│   ├── processing_pipeline.py   # ProcessingPipeline (chain executor)
│   ├── pipeline_builder.py      # PipelineBuilder (factory)
├── spark_adapter.py             # SparkStreamingAdapter
├── processors/
│   ├── __init__.py              # Processor exports
│   ├── base.py                  # BaseProcessor abstract class
│   ├── calibration.py           # CalibrationProcessor
│   ├── validation.py            # ValidationProcessor
│   ├── imputation.py            # ImputationProcessor
│   ├── smoothing.py             # SmoothingProcessor
│   └── normalization.py         # NormalizationProcessor
├── validators/
│   ├── __init__.py              # Range/RoC/Stuck exports
│   ├── range_check.py
│   ├── roc_check.py
│   └── stuck_check.py
├── imputers/
│   ├── __init__.py              # Imputation strategy registry
│   ├── base.py
│   ├── forward_fill.py
│   ├── window_average.py
│   ├── linear_extrapolation.py
│   └── factory.py
├── smoothing/
│   ├── __init__.py              # Smoothing strategy registry
│   ├── base.py
│   ├── pass_through.py
│   ├── ewma.py
│   └── factory.py
├── normalization/               # Normalization strategies
│   ├── __init__.py
│   ├── base.py
│   ├── identity.py
│   ├── min_max.py
│   └── factory.py
├── calibration/
│   ├── __init__.py
│   ├── base.py
│   ├── identity.py
│   ├── affine.py
│   ├── piecewise.py
│   └── factory.py
├── dq/                          # Data quality scoring helpers
│   ├── __init__.py
│   └── score.py
├── state/
│   ├── __init__.py              # State exports
│   ├── sensor_state.py          # State models
│   ├── state.py                 # Base provider
│   └── spark_state.py           # Spark-backed provider
└── main.py                      # Entry point
```

---

## Core Components

### 1. ProcessingContext

**Location**: `dt/data/preprocess/pipeline/context.py`

**Purpose**: Mutable dataclass that carries all state through the pipeline.

**Key Fields**:

```python
@dataclass
class ProcessingContext:
    # Inputs (set at creation)
    reading: RawSensorData              # Original raw reading
    state_provider: StateProvider       # Historical context
    watermark_seconds: float | None     # Event-time watermark
    sensor_key: str | None              # Config key (e.g., "dht22.temperature")
    sensor_config: SensorConfig | None  # Resolved sensor configuration

    # Outputs (populated by processors)
    calibrated_reading: RawSensorData | None
    calibration_profile_id: str | None
    flags: dict[ValidationFlag, bool]
    is_valid: bool | None
    is_late_event: bool
    dq_score: float | None
    imputed: bool
    imputed_value: float | None
    smoothed_value: float | None
    normalized_value: float | None
    normalization_profile_id: str | None
```

**Methods**:
- `to_dict()`: Converts context to ProcessedSensorData dictionary for Kafka output
- `mark_invalid__flag()`: Helper to mark validation flags as True (violation happened)
- `has_violations()`: Check if any validation flags are set
- `get_final_value()`: Get the final value at a given time (raw, calibrated, imputed, smoothed, or normalized)

**When to modify**: Add new fields here when implementing new processors that need to store state.

---

### 2. BaseProcessor

**Location**: `dt/data/preprocess/processors/base.py`

**Purpose**: Abstract interface that all processors must implement.

**Interface**:

```python
class BaseProcessor(ABC):
    @abstractmethod
    def process(self, context: ProcessingContext) -> ProcessingContext:
        """Process the reading and update the context."""
```

**Contract**:
- Receive a `ProcessingContext`
- Perform a single, focused operation
- Update the context with results
- Return the updated context
- Raise `DropReadingException` if the reading should be dropped

**When to extend**: Create a new class inheriting from `BaseProcessor` for each new processing step.

---

### 3. ConfigurationManager

**Location**: `dt/data/preprocess/configuration/manager.py`

**Purpose**: Centralized configuration loading and strategy caching.

**Responsibilities**:
1. Load preprocessing configuration from YAML
2. Build sensor registry from database
3. Resolve sensor identifiers to configuration keys
4. Create and cache processing strategies (calibration, normalization, imputation, smoothing)
5. Provide data quality weights

**Key Methods**:

```python
class ConfigurationManager:
    def __init__(self, config_path: str)

    def resolve_sensor_config(
        self, plant_id: int, sensor_id: int, topic: Topics
    ) -> tuple[str, SensorConfig]

    def get_calibration_strategy(
        self, sensor_key: str, sensor_id: int
    ) -> tuple[CalibrationStrategy, ProfileDefinition]

    def get_normalization_strategy(
        self, sensor_key: str, sensor_id: int
    ) -> tuple[NormalizationStrategy, ProfileDefinition]

    def get_imputation_strategy(
        self, sensor_key: str, sensor_config: SensorConfig
    ) -> ImputationStrategy

    def get_smoothing_strategy(
        self, sensor_key: str, sensor_config: SensorConfig
    ) -> SmoothingStrategy

    def get_dq_weights(self) -> dict[str, float]
```

**Caching**: Strategies are cached by sensor to avoid repeated construction. The same strategy instance is returned for the same sensor across multiple calls.

**When to modify**: Add new `get_*_strategy()` methods when introducing new processor types.

---

### 4. ProcessingPipeline

**Location**: `dt/data/preprocess/pipeline/processing_pipeline.py`

**Purpose**: Chain executor that runs processors in sequence.

**Usage**:

```python
pipeline = ProcessingPipeline()
pipeline.add_processor(CalibrationProcessor(config_manager))
pipeline.add_processor(ValidationProcessor(config_manager))
# ... add more processors

result = pipeline.process(context)
```

**Behavior**:
- Executes processors in the order they were added
- Passes the context through each processor
- Exceptions propagate to the caller
- No retry logic (processors are responsible for handling errors)

**When to modify**: Generally, you don't modify this class. Add new processors via `add_processor()`.

---

### 5. PipelineBuilder

**Location**: `dt/data/preprocess/pipeline/pipeline_builder.py`

**Purpose**: Factory for creating configured pipelines.

**Standard Pipeline**:

```python
builder = PipelineBuilder(config_manager)
pipeline = builder.build_standard_pipeline()
```

Creates a pipeline with all five processors:
1. CalibrationProcessor
2. ValidationProcessor
3. ImputationProcessor
4. SmoothingProcessor
5. NormalizationProcessor

**Custom Pipelines**:

You can create custom pipeline configurations:

```python
# Validation-only pipeline (no processing)
pipeline = builder.build_validation_only_pipeline()

# Custom pipeline
def build_fast_pipeline(self) -> ProcessingPipeline:
    pipeline = ProcessingPipeline()
    pipeline.add_processor(CalibrationProcessor(self._config_manager))
    pipeline.add_processor(ValidationProcessor(self._config_manager))
    # Skip imputation and smoothing for speed
    pipeline.add_processor(NormalizationProcessor(self._config_manager))
    return pipeline
```

**When to modify**: Add new `build_*_pipeline()` methods for different use cases.

---

### 6. SparkStreamingAdapter

**Location**: `dt/data/preprocess/spark_adapter.py`

**Purpose**: Isolate Spark Structured Streaming logic from business logic.

**Responsibilities**:
1. Read from Kafka
2. Apply watermarks
3. Manage stateful group processing
4. Call the processing pipeline
5. Write to Kafka

**Key Methods**:

```python
class SparkStreamingAdapter:
    def __init__(self, spark_session: SparkSession, config_manager: ConfigurationManager)

    def setup_watermark(self, raw_events: DataFrame, interval: str) -> DataFrame

    def build_preprocessing_stream(self, raw_events: DataFrame) -> DataFrame
```

**Why it's separate**: By isolating Spark logic, we can:
- Test processors without SparkSession
- Mock StateProvider in unit tests
- Potentially swap Spark for a different streaming engine

**When to modify**: Only modify this when changing Spark-specific behavior (watermarking, state management, Kafka integration).

---

## Pipeline Stages

### Stage 1: Calibration

**Processor**: `CalibrationProcessor`
**Location**: `dt/data/preprocess/processors/calibration.py`

**Purpose**: Apply sensor-specific calibration transformations to correct for sensor drift and manufacturing variations.

**Strategies**:

| Strategy | Description | Parameters | Use Case |
|----------|-------------|------------|----------|
| `identity` | No transformation (y = x) | None | Already-calibrated sensors |
| `affine` | Linear transformation (y = mx + b) | `slope`, `offset` | Simple drift correction |
| `piecewise` | Lookup table interpolation | `lookup_table` | Non-linear calibration curves |

**Configuration Example**:

```yaml
calibration_profiles:
  defaults:
    dht22.temperature:
      strategy: affine
      parameters:
        slope: 1.05
        offset: -0.5
```

**Input**: `context.reading.value` (raw value)
**Output**:
- `context.calibrated_reading` (RawSensorData with calibrated value)
- `context.calibration_profile_id` (e.g., "calibration.affine.dht22")

**Code Example**:

```python
# Inside CalibrationProcessor.process()
reading = context.reading
strategy, profile = self._config_manager.get_calibration_strategy(
    context.sensor_key, reading.sensor_id
)

calibrated_value = float(strategy.apply(float(reading.value)))

context.calibrated_reading = RawSensorData(
    plant_id=reading.plant_id,
    sensor_id=reading.sensor_id,
    timestamp=reading.timestamp,
    value=calibrated_value,
    unit=reading.unit,
    topic=reading.topic,
    correlation_id=reading.correlation_id,
)
context.calibration_profile_id = profile.profile_id
```

---

### Stage 2: Validation

**Processor**: `ValidationProcessor`
**Location**: `dt/data/preprocess/processors/validation.py`

**Purpose**: Check readings against configured rules and detect late-arriving events.

**Validation Checks**:

| Check | Description | Configuration | Failure Flag |
|-------|-------------|---------------|--------------|
| **Range** | Value within [min, max] bounds | `range.min`, `range.max` | `ValidationFlag.RANGE` |
| **Rate of Change** | Value doesn't change faster than threshold | `roc.active_max_per_minute` | `ValidationFlag.RATE_OF_CHANGE` |
| **Stuck Value** | Sensor not reporting same value for too long | `stuck.max_flat_seconds` | `ValidationFlag.STUCK` |

**Late Event Detection**:

A reading is considered "late" if:
1. Its timestamp is before the current watermark, OR
2. Its timestamp is before the last valid reading's timestamp

**Configuration Example**:

```yaml
sensors:
  dht22.temperature:
    range:
      min: -40
      max: 80
    roc:
      active_max_per_minute: 5.0  # Max 5°C change per minute
    stuck:
      max_flat_seconds: 300  # Flag if same value for 5 minutes

defaults:
  scoring:
    weights:
      range_ok: 0.4
      roc_ok: 0.3
      stuck_ok: 0.3
```

**Input**: `context.calibrated_reading`
**Output**:
- `context.flags` (dict of ValidationFlag → bool)
- `context.is_valid` (overall validation status)
- `context.is_late_event` (late arrival flag)
- `context.dq_score` (data quality score [0, 1])

**Data Quality Scoring**:

```
dq_score = Σ(weight_i × flag_i) / Σ(weight_i)
```

where `flag_i` is 1 if the check passed, 0 if it failed.

Example:
- Range: PASS (1) × 0.4 = 0.4
- ROC: FAIL (0) × 0.3 = 0.0
- Stuck: PASS (1) × 0.3 = 0.3
- **Total**: 0.7 / 1.0 = **0.7**

**Code Flow**:

```python
# 1. Check for late events
if watermark_seconds and reading.timestamp < watermark_seconds:
    context.is_late_event = True

# 2. Range validation
is_range_ok, range_flag = validators.check_range(reading, sensor_config.range)
if not is_range_ok:
    flags[range_flag] = True
    context.is_valid = False
    return context  # Early exit

# 3. Rate-of-change validation
previous_valid = state_provider.get_last_valid(reading.sensor_id)
is_roc_ok, roc_flag = validators.check_rate_of_change(
    reading, previous_valid, sensor_config.roc
)
if not is_roc_ok:
    flags[roc_flag] = True
    context.is_valid = False
    return context  # Early exit

# 4. Stuck value validation
history = state_provider.get_recent_history(
    sensor_id=reading.sensor_id,
    window_seconds=sensor_config.stuck.max_flat_seconds,
    reference_timestamp=reading.timestamp,
)
is_stuck_ok, stuck_flag = validators.check_stuck(history, sensor_config.stuck)

# 5. Compute DQ score
weights = self._config_manager.get_dq_weights()
context.dq_score = compute_dq_score(flags, weights)
```

---

### Stage 3: Imputation

**Processor**: `ImputationProcessor`
**Location**: `dt/data/preprocess/processors/imputation.py`

**Purpose**: Replace invalid readings with estimated values based on historical context.

**Strategies**:

| Strategy | Description | Parameters | Use Case |
|----------|-------------|------------|----------|
| `forward_fill` | Use last valid value with exponential decay | `max_gap_seconds`, `decay_seconds`, `baseline` | Temperature, humidity (slowly changing) |
| `window_average` | Average recent valid values | `window_seconds`, `min_samples` | Light intensity (noisy but stationary) |
| `linear_extrapolation` | Project recent trend forward | `window_seconds`, `min_samples`, `max_rate` | Soil moisture (linear trends) |

**Configuration Example**:

```yaml
sensors:
  dht22.temperature:
    imputation:
      strategy: forward_fill
      max_gap_seconds: 600      # Don't impute gaps > 10 minutes
      decay_seconds: 300        # Decay half-life = 5 minutes
      baseline: 20.0            # Room temperature baseline
```

**Input**: `context.calibrated_reading`, `context.is_valid`
**Output**:
- `context.imputed` (bool: was imputation performed?)
- `context.imputed_value` (imputed value if needed, else None)

**Behavior**:
- If `is_valid = True`: Skip imputation
- If `is_valid = False`: Attempt imputation
- If imputation fails (no history): Raise `DropReadingException`

**Code Flow**:

```python
# Skip valid readings
if context.is_valid:
    context.imputed = False
    return context

# Get imputation strategy
strategy = self._config_manager.get_imputation_strategy(
    context.sensor_key, context.sensor_config
)

# Attempt imputation
imputed_value = strategy.compute(
    sensor_id=reading.sensor_id,
    reading=reading,
    state=state_provider,
)

if imputed_value is None:
    raise DropReadingException(
        f"Imputation failed for sensor_id={reading.sensor_id}"
    )

context.imputed = True
context.imputed_value = float(imputed_value)
```

**Forward Fill with Decay**:

```
imputed_value = last_valid_value × e^(-Δt / decay_seconds) + baseline × (1 - e^(-Δt / decay_seconds))
```

where `Δt` is the time since the last valid reading.

**Example**:
- Last valid: 25.0°C at t=0
- Current: t=300s (5 minutes)
- Decay: 300s
- Baseline: 20.0°C

```
imputed = 25.0 × e^(-300/300) + 20.0 × (1 - e^(-1))
        = 25.0 × 0.368 + 20.0 × 0.632
        = 9.2 + 12.64
        = 21.84°C
```

---

### Stage 4: Smoothing

**Processor**: `SmoothingProcessor`
**Location**: `dt/data/preprocess/processors/smoothing.py`

**Purpose**: Reduce noise in sensor readings using filtering techniques.

**Strategies**:

| Strategy | Description | Parameters | Use Case |
|----------|-------------|------------|----------|
| `pass_through` | No smoothing | None | Already-clean signals |
| `ewma` | Exponentially Weighted Moving Average | `alpha` | Most sensors (balance responsiveness and noise) |

**Configuration Example**:

```yaml
sensors:
  dht22.temperature:
    smoothing:
      strategy: ewma
      alpha: 0.3  # Higher α = more responsive, less smoothing
```

**Input**: `context.imputed_value` (if imputed) or `context.calibrated_reading.value`
**Output**: `context.smoothed_value`

**EWMA Formula**:

```
smoothed[t] = α × value[t] + (1 - α) × smoothed[t-1]
```

where:
- `α` = smoothing factor [0, 1]
- Higher α: More responsive to changes, less smoothing
- Lower α: More smoothing, less responsive

**Example**:
- Previous smoothed: 24.0°C
- Current value: 26.0°C
- α = 0.3

```
smoothed = 0.3 × 26.0 + 0.7 × 24.0
         = 7.8 + 16.8
         = 24.6°C
```

**Code Flow**:

```python
# Determine input value (imputed or calibrated)
value = (
    context.imputed_value
    if context.imputed_value is not None
    else float(context.calibrated_reading.value)
)

# Get smoothing strategy
strategy = self._config_manager.get_smoothing_strategy(
    context.sensor_key, context.sensor_config
)

# Apply smoothing
smoothed = strategy.apply(
    sensor_id=reading.sensor_id,
    value=value,
    timestamp=float(reading.timestamp),
    state=state_provider,
)

context.smoothed_value = float(smoothed)
```

---

### Stage 5: Normalization

**Processor**: `NormalizationProcessor`
**Location**: `dt/data/preprocess/processors/normalization.py`

**Purpose**: Scale values to a standard range [0, 1] for ML/analytics.

**Strategies**:

| Strategy | Description | Parameters | Use Case |
|----------|-------------|------------|----------|
| `identity` | No normalization | None | Values already normalized |
| `minmax` | Scale to [0, 1] based on min/max | `min_value`, `max_value`, `clip` | Most sensors |

**Configuration Example**:

```yaml
normalization_profiles:
  defaults:
    dht22.temperature:
      strategy: minmax
      parameters:
        min_value: -40.0
        max_value: 80.0
        clip: true  # Clip values outside [min, max]
```

**Input**: `context.smoothed_value`
**Output**:
- `context.normalized_value`
- `context.normalization_profile_id`

**MinMax Formula**:

```
normalized = (value - min) / (max - min)
```

**Example**:
- Smoothed value: 25.0°C
- Min: -40.0°C
- Max: 80.0°C

```
normalized = (25.0 - (-40.0)) / (80.0 - (-40.0))
           = 65.0 / 120.0
           = 0.542
```

**Clipping**:
- If `clip = true`: Values outside [min, max] are clamped to [0, 1]
- If `clip = false`: Values can be < 0 or > 1 (extrapolation)

**Code Flow**:

```python
# Get normalization strategy
strategy, profile = self._config_manager.get_normalization_strategy(
    context.sensor_key, reading.sensor_id
)

# Apply normalization
normalized = float(strategy.apply(context.smoothed_value))

context.normalized_value = normalized
context.normalization_profile_id = profile.profile_id
```

---

## Configuration

### Configuration File Structure

**Location**: `dt/utils/preprocessing_config.yml` (or path set in `Config.PREPROCESSING_CONFIG_PATH`)

**Structure**:

```yaml
# Sensor validation rules
sensors:
  <sensor_key>:
    range:
      min: <float>
      max: <float>
    roc:
      active_max_per_minute: <float>
    stuck:
      max_flat_seconds: <float>
    imputation:
      strategy: <forward_fill | window_average | linear_extrapolation>
      # Strategy-specific parameters
    smoothing:
      strategy: <pass_through | ewma>
      # Strategy-specific parameters

# Data quality scoring weights
defaults:
  scoring:
    weights:
      range_ok: <float>
      roc_ok: <float>
      stuck_ok: <float>

# Calibration profiles
calibration_profiles:
  defaults:
    <sensor_type>:
      strategy: <identity | affine | piecewise>
      parameters:
        # Strategy-specific parameters
  overrides:
    <sensor_id>:
      sensor_type: <sensor_type>
      profile_id: <profile_id>
      # Override parameters

# Normalization profiles
normalization_profiles:
  defaults:
    <sensor_type>:
      strategy: <identity | minmax>
      parameters:
        # Strategy-specific parameters
  overrides:
    <sensor_id>:
      sensor_type: <sensor_type>
      profile_id: <profile_id>
      # Override parameters
```

### Complete Example

```yaml
sensors:
  # DHT22 Temperature Sensor
  dht22.temperature:
    range:
      min: -40.0
      max: 80.0
    roc:
      active_max_per_minute: 5.0
    stuck:
      max_flat_seconds: 300
    imputation:
      strategy: forward_fill
      max_gap_seconds: 600
      decay_seconds: 300
      baseline: 20.0
    smoothing:
      strategy: ewma
      alpha: 0.3

  # BH1750 Light Sensor
  bh1750.light:
    range:
      min: 0.0
      max: 65535.0
    roc:
      active_max_per_minute: 10000.0
    stuck:
      max_flat_seconds: 180
    imputation:
      strategy: window_average
      window_seconds: 180
      min_samples: 3
    smoothing:
      strategy: ewma
      alpha: 0.2

defaults:
  scoring:
    weights:
      range_ok: 0.4
      roc_ok: 0.3
      stuck_ok: 0.3

calibration_profiles:
  defaults:
    dht22.temperature:
      strategy: affine
      parameters:
        slope: 1.05
        offset: -0.5
    bh1750.light:
      strategy: identity

normalization_profiles:
  defaults:
    dht22.temperature:
      strategy: minmax
      parameters:
        min_value: -40.0
        max_value: 80.0
        clip: true
    bh1750.light:
      strategy: minmax
      parameters:
        min_value: 0.0
        max_value: 65535.0
        clip: true
```

### Sensor Registry

The sensor registry maps numeric sensor IDs to configuration keys. It's loaded from the database via `DatabaseApiClient().list_sensors()`.

**Example**:
- Sensor ID 101 → "dht22.temperature"
- Sensor ID 102 → "bh1750.light"

When a reading arrives with `sensor_id=101`, the ConfigurationManager:
1. Looks up "dht22.temperature" in the registry
2. Loads the sensor configuration from `sensors.dht22.temperature`
3. Creates/caches strategies for that sensor

---

## Extending the Pipeline

### Adding a New Processor

**Scenario**: You want to add anomaly detection to the pipeline.

**Step 1: Create the Processor Class**

Create `dt/data/preprocess/processors/anomaly_detection.py`:

**Step 2: Update ProcessingContext**

Add the new field to `dt/data/preprocess/pipeline/context.py`:

**Step 3: Add to PipelineBuilder**

Update `dt/data/preprocess/pipeline/pipeline_builder.py`:

**Step 4: Update ProcessedSensorData**

If you want to include the anomaly flag in Kafka output, update `dt/communication/dataclasses/processed_sensor_data.py`:

**Step 5: Update context.to_dict()**

Update `ProcessingContext.to_dict()` to include the new field:

**Step 6: Write Tests**

Create `tests/data/preprocess/test_anomaly_detection_processor.py`:

---

### Adding a New Strategy

**Scenario**: You want to add a Kalman filter smoothing strategy.

**Step 1: Implement the Strategy**

Update `dt/data/preprocess/smoothing.py`:

**Step 2: Update the Factory**

Update `build_smoothing_strategy()` in `dt/data/preprocess/smoothing.py`:

**Step 3: Update Configuration Schema**

Users can now configure Kalman smoothing:

```yaml
sensors:
  dht22.temperature:
    smoothing:
      strategy: kalman
      ...
      
```

**Step 4: Write Tests**

---

## Testing

### Unit Tests

**Location**: `tests/data/preprocess/`

**Test Structure**:

```
tests/data/preprocess/
├── test_context.py                  # ProcessingContext tests
├── test_base_processor.py           # BaseProcessor interface tests
├── test_configuration.py            # ConfigurationManager tests
├── test_processing_pipeline.py      # ProcessingPipeline tests
├── test_pipeline_builder.py         # PipelineBuilder tests
├── test_calibration_processor.py    # CalibrationProcessor tests
├── test_validation_processor.py     # ValidationProcessor tests
├── test_imputation_processor.py     # ImputationProcessor tests
├── test_smoothing_processor.py      # SmoothingProcessor tests
├── test_normalization_processor.py  # NormalizationProcessor tests
└── test_integration_full_pipeline.py # End-to-end integration test
```


---

## Troubleshooting

### Common Issues

#### Issue: "No sensor registry entry" error

**Symptom**:
```
KeyError: No sensor registry entry for sensor_id=101
```

**Solution**:
1. Check that the sensor exists in the database
2. Verify `DatabaseApiClient().list_sensors()` returns the sensor
3. Check that the sensor name matches a key in `preprocessing_config.yml`

**Debug**:
```python
from dt.data.preprocess.configuration.manager import ConfigurationManager

config_manager = ConfigurationManager("/path/to/preprocessing_config.yml")
print(config_manager.sensor_registry)
# Should print: {101: 'dht22.temperature', 102: 'bh1750.light', ...}
```

---

#### Issue: Spark tests timeout

**Symptom**:
Tests hang or timeout when running Spark integration tests.

**Solution**:
1. Reduce test data size
2. Check Spark logging level (set to WARN or ERROR)
3. Verify SparkSession is properly cleaned up in test teardown

```python
@pytest.fixture(scope="session")
def spark_session():
    spark = SparkSession.builder.appName("test").getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")
    yield spark
    spark.stop()
```


---

## Appendix

### Design Decisions

**Why Chain of Responsibility?**

The Chain of Responsibility pattern was chosen because:
1. **Sequential processing**: Each stage depends on the previous stage's output
2. **Easy to extend**: New processors can be added without modifying existing code
3. **Flexible ordering**: Pipeline can be reconfigured by changing processor order
4. **Clear responsibilities**: Each processor has a single, focused job


### Performance Considerations

**Strategy Caching**:
Strategies are cached by sensor to avoid repeated construction. For a system with 100 sensors and 5 strategies per sensor, this saves 500 object constructions per microbatch.

**State Access**:
StateProvider uses rolling windows to limit memory. Only the last N readings are kept per sensor (configurable via `max_history_length`).

**Spark Broadcasting**:
ConfigurationManager is broadcast to Spark executors to avoid repeated config loading on each executor.

### Future Enhancements

- **Config Hot-Reload**: Watch config file and rebuild pipelines on change

### Glossary

- **BaseProcessor**: Abstract interface that all processors must implement
- **CalibrationStrategy**: Strategy for transforming raw values (affine, piecewise, etc.)
- **Chain of Responsibility**: Design pattern where handlers pass requests along a chain
- **ConfigurationManager**: Service that loads config and creates/caches strategies
- **DQ Score**: Data Quality score [0, 1] based on validation checks
- **ImputationStrategy**: Strategy for filling missing/invalid values
- **Late Event**: Reading that arrives after the watermark or last valid reading
- **NormalizationStrategy**: Strategy for scaling values to [0, 1]
- **PipelineBuilder**: Factory for creating configured pipelines
- **ProcessingContext**: Mutable state object passed through the pipeline
- **ProcessingPipeline**: Chain executor that runs processors in sequence
- **SmoothingStrategy**: Strategy for noise reduction (EWMA, Kalman, etc.)
- **SparkStreamingAdapter**: Spark integration layer isolating Spark concerns
- **StateProvider**: Abstraction for accessing historical sensor data
- **Watermark**: Event-time boundary for late event detection

---

**Document Version**: 1.0
**Last Updated**: 2025-10-31
**Maintained By**: Digital Twin Team
