# Alert Rules Configuration

## Overview

Alert rules are defined in `dt/utils/alert_rules.yml` and control how the alert
engine service evaluates processed sensor data to generate alerts. The alert
engine consumes data from `dt.sensors.processed.*` Kafka topics and publishes
alert history events with `AlertStatus` to the `dt.alerts` topic.

## Configuration Location

**Default path:** `dt/utils/alert_rules.yml`

The alert engine loads rules at startup from this configuration file. Custom paths can be specified via the `config_path` parameter to `create_app()`.

## Rule Structure

Each alert rule is defined as a YAML object with the following fields:

```yaml
alert_rules:
  - rule_id: unique_identifier        # Unique identifier for this rule
    name: Human Readable Name          # Display name for UI
    description: "Message template"    # Template with format placeholders
    severity: warning                  # info | warning | critical
    evaluation_stage: processed        # Currently only 'processed' supported
    source: temperature                # Sensor type (* for wildcard)
    condition:                         # Condition definition
      type: threshold                  # threshold | range | dq_score | validation_flag
      operator: ">"                    # Condition-specific parameters
      threshold: 35.0
    persistence_count: 2               # Consecutive violations required
    cooldown_seconds: 300              # Minimum seconds between alerts
```

### Required Fields

- **rule_id** (string): Unique identifier used to track alert state. Must be unique across all rules.
- **name** (string): Human-readable name displayed in UI and notifications.
- **description** (string): Message template with format placeholders (e.g., `{threshold}`, `{value}`) populated from sensor data and condition parameters.
- **severity** (enum): Alert severity level
  - `info`: Informational alerts for low-priority conditions
  - `warning`: Warnings for conditions requiring attention
  - `critical`: Critical alerts for urgent conditions
- **evaluation_stage** (enum): When to evaluate the rule. Currently only `processed` is supported.
- **source** (string): Sensor type or topic short name to apply rule to
  - Use exact sensor type: `temperature`, `soil_moisture`, `humidity`, `light_intensity`
  - Use `*` wildcard to apply rule to all sensors
- **condition** (object): Condition definition (see Condition Types below)
- **persistence_count** (integer): Number of consecutive violations required before alert fires (≥1)
- **cooldown_seconds** (integer): Minimum seconds between repeated alerts for same rule/source (≥0)

## Condition Types

### Threshold Condition

Compares sensor value against a fixed threshold using comparison operators.

```yaml
condition:
  type: threshold
  operator: ">"     # >, <, >=, <=, ==, !=
  threshold: 35.0   # Numeric threshold value
```

**Example use cases:**
- Temperature exceeds 35°C
- Soil moisture drops below 20%
- Light intensity falls under 1000 lux

### Range Condition

Triggers when sensor value falls outside specified min/max bounds.

```yaml
condition:
  type: range
  min_value: 20.0   # Lower bound (null for unbounded)
  max_value: 80.0   # Upper bound (null for unbounded)
```

**Example use cases:**
- Soil moisture outside optimal 20-80% range
- Temperature outside safe 15-30°C range

**Note:** Condition triggers when value is **below** min_value OR **above** max_value. Set bounds to `null` for one-sided constraints.

### Data Quality Score Condition

Triggers when data quality score drops below threshold.

```yaml
condition:
  type: dq_score
  threshold: 0.7    # DQ score threshold (0.0-1.0)
```

**Example use cases:**
- Alert when sensor readings become unreliable (DQ < 0.5)
- Monitor data quality degradation across all sensors

**Note:** Commonly used with wildcard source (`source: "*"`) to monitor data quality across all sensors.

### Validation Flag Condition

Triggers when specific validation flags are set or cleared.

```yaml
condition:
  type: validation_flag
  flag: range_violation              # ValidationFlag enum value
  expected: true                     # true or false
```

**Available flags:**
- `range_violation`: Sensor value outside configured range
- `rate_of_change_violation`: Value changed too rapidly
- `stuck_violation`: Sensor appears stuck at same value
- `valid_data_point`: Data passed all validation checks

**Example use cases:**
- Alert when range violations occur
- Alert when sensor gets stuck
- Alert when rate of change is excessive

## Persistence and Cooldown

### Persistence Count

The `persistence_count` parameter prevents transient spikes from generating alerts. The rule must trigger on N **consecutive** evaluations before an alert is created.

**Example:**
```yaml
persistence_count: 3
```
- First violation: IGNORED (state tracked, no alert)
- Second violation: IGNORED (state tracked, no alert)
- Third violation: ACTIVE (alert fires)
- If condition clears before reaching threshold, counter resets

### Cooldown Timer

The `cooldown_seconds` parameter prevents alert fatigue by suppressing repeated alerts for the same condition.

**Example:**
```yaml
cooldown_seconds: 300  # 5 minutes
```
- Alert fires at T=0
- Condition persists at T=60: IGNORED (no new alert during cooldown)
- Condition persists at T=120: IGNORED (still in cooldown)
- Condition persists at T=400: ACTIVE (alert publishes again after cooldown)

**Note:** Cooldown applies per unique alert_id (`{rule_id}:{source}`). Different sensors trigger independent alerts.

## Message Templates

Alert descriptions support format placeholders that are populated with sensor data and condition parameters.

**Available placeholders:**
- All `ProcessedSensorData` fields: `{value}`, `{sensor_id}`, `{timestamp}`, `{dq_score}`, etc.
- All condition parameters: `{threshold}`, `{min_value}`, `{max_value}`, `{operator}`, etc.

**Example:**
```yaml
description: "Temperature {value}°C exceeds threshold {threshold}°C (sensor {sensor_id})"
```

Produces: `"Temperature 38.5°C exceeds threshold 35.0°C (sensor 101)"`

## Complete Examples

### Temperature Warning (Threshold)

```yaml
- rule_id: temp_high_warning
  name: High Temperature Warning
  description: "Temperature exceeds {threshold}°C (current: {value}°C)"
  severity: warning
  evaluation_stage: processed
  source: temperature
  condition:
    type: threshold
    operator: ">"
    threshold: 35.0
  persistence_count: 2
  cooldown_seconds: 300
```

Triggers after 2 consecutive temperature readings above 35°C, with 5-minute cooldown.

### Soil Moisture Alert (Range)

```yaml
- rule_id: moisture_low
  name: Low Soil Moisture
  description: "Soil moisture below {min_value}% (current: {value}%)"
  severity: warning
  evaluation_stage: processed
  source: soil_moisture
  condition:
    type: range
    min_value: 20.0
    max_value: null
  persistence_count: 3
  cooldown_seconds: 600
```

Triggers after 3 consecutive readings below 20%, with 10-minute cooldown.

### Data Quality Monitor (DQ Score, Wildcard)

```yaml
- rule_id: dq_score_low
  name: Low Data Quality
  description: "Data quality score {dq_score} below threshold {threshold}"
  severity: info
  evaluation_stage: processed
  source: "*"
  condition:
    type: dq_score
    threshold: 0.7
  persistence_count: 1
  cooldown_seconds: 120
```

Monitors all sensors for low data quality, triggers immediately, with 2-minute cooldown.

## Alert Lifecycle

When a rule triggers, the alert engine tracks alerts with `AlertStatus`:

1. **IGNORED**: Condition met but below persistence threshold or within cooldown (state tracked, no event published)
2. **ACTIVE**: Persistence threshold reached or re-trigger after cooldown (event published to Kafka)
3. **ACKNOWLEDGED**: Alert acknowledged via REST API (event published with actor)
4. **CLEARED**: Alert cleared via REST API (event published, state removed)

Only ACTIVE, ACKNOWLEDGED, and CLEARED statuses are published to the `dt.alerts` Kafka topic.

## REST API Integration

External modules (AI, control) can submit programmatic alerts via the REST API:

```bash
curl -X POST http://localhost:5003/alerts/submit \
  -H "Content-Type: application/json" \
  -d '{
    "alert_id": "ai_anomaly_123",
    "source": "ai_detector",
    "severity": "critical",
    "message": "Anomaly detected with score 0.95",
    "correlation_id": "corr-ai-456",
    "persistence_count": 1,
    "cooldown_seconds": 300,
    "payload": {"anomaly_score": 0.95}
  }'
```

These submissions bypass rule evaluation and are immediately registered with the alert registry.

## Troubleshooting

### Rules Not Triggering

1. **Check source name**: Ensure `source` matches topic short name exactly (`temperature` not `TEMPERATURE`)
2. **Verify persistence count**: Rule may be IGNORED if not enough consecutive violations
3. **Check cooldown**: Alert may be IGNORED if within cooldown period
4. **Inspect logs**: Alert engine logs all evaluation results and state transitions

### Alert Fatigue

1. **Increase persistence_count**: Require more consecutive violations
2. **Increase cooldown_seconds**: Suppress repeated alerts for longer periods
3. **Adjust condition thresholds**: Make conditions less sensitive
4. **Review rule severity**: Consider downgrading from `warning` to `info`

### Missing Alerts

1. **Check processed topics**: Ensure preprocessing pipeline is publishing to `dt.sensors.processed.*`
2. **Verify rule evaluation_stage**: Must be `processed` to match processed topics
3. **Inspect condition parameters**: Ensure thresholds/ranges are appropriate for sensor units
4. **Review alert registry state**: Use `GET /alerts/active` to check current alert state

## See Also

- Implementation plan: `docs/plans/alert_engine_implementation_plan.md`
- Alert event contract: `docs/briefs/systemPatterns.md` (Alert Event Contract section)
- REST API documentation: `docs/briefs/systemPatterns.md` (Alert Service REST API section)
- Alert engine service: `dt/alerts/app.py`
- Sample configuration: `dt/utils/alert_rules.yml`
