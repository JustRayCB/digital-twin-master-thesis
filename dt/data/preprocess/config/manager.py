from typing import Any

import yaml

from dt.communication.db_client import DatabaseApiClient
from dt.communication.topics import Topics
from dt.communication.adapters.registry import load
from dt.data.preprocess.stages.calibration import CalibrationStrategy, build_calibration_strategy
from dt.data.preprocess.stages.imputation import ImputationStrategy, build_imputation_strategy
from dt.data.preprocess.stages.normalization import (
    NormalizationStrategy,
    build_normalization_strategy,
)
from dt.data.preprocess.stages.smoothing import SmoothingStrategy, build_smoothing_strategy
from dt.utils import get_logger

from .serialization import ensure_config_serialization
from .types import SensorConfig, SystemConfig

logger = get_logger(__name__)


class ConfigurationManager:
    """Manages preprocessing configuration with template inheritance.

    This class loads the new Unified Schema and resolves sensor configurations
    by merging specific overrides onto base templates. It caches resolved
    configurations and built strategy objects.
    """

    def __init__(self, config_path: str) -> None:
        """Initialize and load configuration.

        Parameters
        ----------
        config_path : str
            Path to the YAML configuration file.
        """
        self._config_path = config_path
        self._raw_data: dict[str, Any] = {}
        self.config: SystemConfig
        self._config_cache: dict[str, SensorConfig] = {}
        self.sensor_registry: dict[int, str] = {}
        self._strategy_cache: dict[str, dict[str, Any]] = {
            "calibration": {},
            "normalization": {},
            "imputation": {},
            "smoothing": {},
        }

        self._load_config()
        self._build_sensor_registry()

    def _load_config(self) -> None:
        """Load and parse the YAML configuration."""

        ensure_config_serialization()

        with open(self._config_path, encoding="utf-8") as f:
            self._raw_data = yaml.safe_load(f) or {}

        # Validate root schema
        self.config = load("generic", SystemConfig, self._raw_data)

    def _build_sensor_registry(self) -> None:
        """Build sensor ID → configuration key mapping from the database.

        The preprocessing configuration is keyed by strings under the YAML
        `sensors:` mapping, but runtime readings carry a numeric `sensor_id`
        assigned by the database. This registry bridges the two by mapping
        each database sensor ID to the most specific applicable configuration
        key, with fallback to generic sensor-type keys when no specific override
        exists.

        Resolution priority for each sensor descriptor:
        1) Exact match: `SensorDescriptor.name` exists in YAML `sensors:`
        2) Derived generic key: `<type>.<metric>` exists in YAML `sensors:`
        """
        raw_sensors = self._raw_data.get("sensors", {})

        try:
            descriptors = DatabaseApiClient().list_sensors()
        except Exception as exc:
            logger.warning(f"Unable to load sensor registry from database: {exc}")
            self.sensor_registry = {}
            return

        registry: dict[int, str] = {}
        for descriptor in descriptors:
            config_key = descriptor.name
            if config_key in raw_sensors:
                # Most specific case: the DB-stored name is a direct configuration key.
                registry[descriptor.id] = config_key
                continue

            generic_key = self._derive_generic_sensor_key(config_key)
            if generic_key is not None and generic_key in raw_sensors:
                # Generic fallback: match by sensor type and metric only.
                registry[descriptor.id] = generic_key

        self.sensor_registry = registry
        logger.info(f"Loaded sensor registry with {len(registry)} sensors")

    def _derive_generic_sensor_key(self, config_key: str) -> str | None:
        """Derive a generic `<type>.<metric>` key from a specific sensor key.

        This supports configurations that define generic defaults keyed by
        sensor type and metric (e.g., `dht22.temperature`) while allowing
        sensor-specific overrides keyed by a fully-qualified identifier stored
        in the database (e.g., `sensors.basil.dht22.001.temperature`).

        The expected specific-key format is:
        `sensors.<plant_slug>.<sensor_type>.<manual_id>.<metric>`

        Parameters
        ----------
        config_key : str
            Sensor identifier as stored in the database.

        Returns
        -------
        str | None
            Generic key in the form `<sensor_type>.<metric>`, or ``None`` if the
            input does not match the expected specific-key format.
        """
        parts = config_key.split(".")
        if len(parts) < 3:
            return None

        if parts[0] != "sensors":
            return None

        if len(parts) < 5:
            return None

        sensor_type = parts[2]
        metric = parts[-1]
        return f"{sensor_type}.{metric}"

    def resolve_sensor_config(
        self, plant_id: int, sensor_id: int, topic: Topics
    ) -> tuple[str, SensorConfig]:
        """Resolve sensor configuration using database-backed registry.

        Parameters
        ----------
        plant_id : int
            Plant identifier.
        sensor_id : int
            Database-assigned sensor identifier.
        topic : Topics
            Kafka topic for the reading.

        Returns
        -------
        tuple[str, SensorConfig]
            A tuple of `(config_key, resolved_config)` where `config_key` is the
            YAML key used for lookup (specific override or fallback), and
            `resolved_config` is the parsed, template-merged configuration.

        Raises
        ------
        KeyError
            If no registry entry exists for the given sensor ID and there is no
            numeric-key configuration present in the YAML.
        """

        registry_key = self.sensor_registry.get(sensor_id)
        if registry_key is None:
            raise KeyError(
                f"No sensor registry entry for sensor_id={sensor_id} "
                f"(plant_id={plant_id}, topic={topic.value})"
            )

        return registry_key, self.get_sensor_config(registry_key)

    def get_sensor_config(self, sensor_id: str) -> SensorConfig:
        """Resolve configuration for a specific sensor ID.

        Logic:
        1. Check cache.
        2. Find sensor entry in 'sensors' map.
        3. If it has a 'template', load that template from 'templates'.
        4. Deep merge sensor overrides onto the template.
        5. Parse the result into a SensorConfig object and cache it.

        Parameters
        ----------
        sensor_id : str
            The unique identifier for the sensor.

        Returns
        -------
        SensorConfig
            The fully resolved configuration object.

        Raises
        ------
        KeyError
            If sensor_id is not found.
        """

        if sensor_id in self._config_cache:
            return self._config_cache[sensor_id]

        raw_sensors = self._raw_data.get("sensors", {})
        if sensor_id not in raw_sensors:
            raise KeyError(f"Sensor '{sensor_id}' not found in configuration.")

        sensor_dict = raw_sensors[sensor_id]
        template_name = sensor_dict.get("template")

        if template_name:
            raw_templates = self._raw_data.get("templates", {})
            if template_name not in raw_templates:
                raise ValueError(
                    f"Sensor '{sensor_id}' references unknown template '{template_name}'"
                )

            template_dict = raw_templates[template_name]
            final_dict = self._deep_merge(template_dict, sensor_dict)
        else:
            final_dict = sensor_dict

        resolved = load("generic", SensorConfig, final_dict)

        # Populate traceability metadata
        resolved.calibration_profile_id = self._generate_profile_id(
            sensor_id, sensor_dict, template_name, "calibration"
        )
        resolved.normalization_profile_id = self._generate_profile_id(
            sensor_id, sensor_dict, template_name, "normalization"
        )

        self._config_cache[sensor_id] = resolved
        return resolved

    def _generate_profile_id(
        self, sensor_id: str, sensor_dict: dict, template_name: str | None, section: str
    ) -> str:
        """Generate a traceability ID for a configuration section."""
        if not template_name:
            return f"standalone:{sensor_id}" if section in sensor_dict else "default"

        return f"{template_name}:{sensor_id}-custom" if section in sensor_dict else template_name

    def get_calibration_strategy(self, sensor_id: str) -> CalibrationStrategy:
        """Return the calibrated strategy for the specified sensor."""
        if sensor_id not in self._strategy_cache["calibration"]:
            config = self.get_sensor_config(sensor_id)
            self._strategy_cache["calibration"][sensor_id] = build_calibration_strategy(
                config.calibration
            )
        return self._strategy_cache["calibration"][sensor_id]

    def get_normalization_strategy(self, sensor_id: str) -> NormalizationStrategy:
        """Return the normalization strategy for the specified sensor."""
        if sensor_id not in self._strategy_cache["normalization"]:
            config = self.get_sensor_config(sensor_id)
            self._strategy_cache["normalization"][sensor_id] = build_normalization_strategy(
                config.normalization
            )
        return self._strategy_cache["normalization"][sensor_id]

    def get_imputation_strategy(self, sensor_id: str) -> ImputationStrategy:
        """Return the imputation strategy for the specified sensor."""
        if sensor_id not in self._strategy_cache["imputation"]:
            config = self.get_sensor_config(sensor_id)
            self._strategy_cache["imputation"][sensor_id] = build_imputation_strategy(
                config.imputation
            )
        return self._strategy_cache["imputation"][sensor_id]

    def get_smoothing_strategy(self, sensor_id: str) -> SmoothingStrategy:
        """Return the smoothing strategy for the specified sensor."""
        if sensor_id not in self._strategy_cache["smoothing"]:
            config = self.get_sensor_config(sensor_id)
            self._strategy_cache["smoothing"][sensor_id] = build_smoothing_strategy(
                config.smoothing
            )
        return self._strategy_cache["smoothing"][sensor_id]

    def _deep_merge(self, base: dict, override: dict) -> dict:
        """Recursively merge two dictionaries."""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def get_dq_weights(self) -> dict[str, float]:
        """Get data quality scoring weights."""
        from dt.communication.adapters.registry import dump

        return dump("generic", self.config.system.weights)
