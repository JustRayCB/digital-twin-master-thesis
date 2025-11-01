from pathlib import Path
from typing import Any

import yaml

from dt.communication.db_client import DatabaseApiClient
from dt.communication.topics import Topics
from dt.data.preprocess.calibration import (CalibrationStrategy,
                                            build_calibration_strategy)
from dt.data.preprocess.configuration.catalog import CalibrationCatalog
from dt.data.preprocess.configuration.preprocessing_config import (
    SensorConfig, SensorValidationConfig)
from dt.data.preprocess.configuration.profiles import (ProfileConfiguration,
                                                       ProfileDefinition)
from dt.data.preprocess.imputers import (ImputationStrategy,
                                         build_imputation_strategy)
from dt.data.preprocess.normalization import (NormalizationStrategy,
                                              build_normalization_strategy)
from dt.data.preprocess.smoothing import (SmoothingStrategy,
                                          build_smoothing_strategy)
from dt.utils import get_logger

logger = get_logger(__name__)


class ConfigurationManager:
    """Manages preprocessing configuration, sensor registry, and strategy caching.

    This class consolidates:
    - Loading preprocessing configuration from YAML
    - Resolving sensor identifiers to configuration keys
    - Creating and caching processing strategies (calibration, normalization, imputation, smoothing)
    - Providing data quality weights

    Parameters
    ----------
    config_path : str
        Path to the preprocessing configuration YAML file.

    Attributes
    ----------
    rules : SensorValidationConfig
        Loaded preprocessing rules and sensor configurations.
    sensor_registry : dict[int, str]
        Mapping from sensor IDs to configuration keys.
    catalog : CalibrationCatalog
        Catalog for resolving calibration and normalization profiles.
    """

    def __init__(self, config_path: str) -> None:
        """Initialize the configuration manager.

        Parameters
        ----------
        config_path : str
            Path to preprocessing configuration YAML.
        """
        self._config_path = config_path

        # Strategy caches
        self._calibration_cache: dict[str, tuple[CalibrationStrategy, ProfileDefinition]] = {}
        self._normalization_cache: dict[str, tuple[NormalizationStrategy, ProfileDefinition]] = {}
        self._imputation_cache: dict[str, ImputationStrategy] = {}
        self._smoothing_cache: dict[str, SmoothingStrategy] = {}

        self.rules: SensorValidationConfig
        self._raw_config: dict[str, Any]
        self.sensor_registry: dict[int, str]
        self.catalog: CalibrationCatalog

        # Load configuration and build structures
        self._load_config()
        self._build_sensor_registry()
        self._build_catalog()

    def _load_config(self) -> None:
        """Load preprocessing configuration from YAML file."""
        with Path(self._config_path).expanduser().open("r", encoding="utf-8") as handle:
            raw_config = yaml.safe_load(handle) or {}

        self.rules = SensorValidationConfig.from_dict(raw_config)
        self._raw_config = raw_config

    def _build_sensor_registry(self) -> None:
        """Build sensor ID to config key mapping from database."""
        try:
            descriptors = DatabaseApiClient().list_sensors()
        except Exception as exc:
            logger.warning(f"Unable to load sensor registry from database: {exc}")
            self.sensor_registry = {}
            return

        registry: dict[int, str] = {}
        for descriptor in descriptors:
            config_key = descriptor.name
            if config_key in self.rules.sensors:
                registry[descriptor.sensor_id] = config_key

        self.sensor_registry = registry
        logger.info(f"Loaded sensor registry with {len(registry)} sensors")

    def _build_catalog(self) -> None:
        """Build calibration catalog from configuration."""
        profiles = ProfileConfiguration.from_dict(self._raw_config)
        sensor_types = self._build_sensor_type_index(profiles)
        self.catalog = CalibrationCatalog(profiles, sensor_types=sensor_types)

    def _build_sensor_type_index(self, profiles: ProfileConfiguration) -> dict[str, str]:
        """Build sensor identifier to sensor type mapping."""
        sensor_types: dict[str, str] = {}

        # Add defaults
        sensor_types.update({key: key for key in profiles.calibration.defaults})
        sensor_types.update({key: key for key in profiles.normalization.defaults})

        # Add overrides
        for sensor_id, entry in self.sensor_registry.items():
            sensor_types[str(sensor_id)] = entry

        for sensor_identifier, assignment in profiles.calibration.overrides.items():
            sensor_types[sensor_identifier] = assignment.sensor_type

        for sensor_identifier, assignment in profiles.normalization.overrides.items():
            sensor_types[sensor_identifier] = assignment.sensor_type

        return sensor_types

    def resolve_sensor_config(
        self, plant_id: int, sensor_id: int, topic: Topics
    ) -> tuple[str, SensorConfig]:
        """Resolve sensor configuration from registry.

        Parameters
        ----------
        plant_id : int
            Plant identifier.
        sensor_id : int
            Sensor identifier.
        topic : Topics
            Kafka topic for the reading.

        Returns
        -------
        tuple[str, SensorConfig]
            Sensor configuration key and the corresponding config object.

        Raises
        ------
        KeyError
            When the sensor is not found in the registry or configuration.
        """
        registry_key = self.sensor_registry.get(sensor_id)
        if registry_key is None:
            raise KeyError(
                f"No sensor registry entry for sensor_id={sensor_id} "
                f"(plant_id={plant_id}, topic={topic.value})"
            )

        try:
            sensor_config = self.rules.sensors[registry_key]
        except KeyError as exc:
            raise KeyError(
                f"Sensor registry maps sensor_id={sensor_id} to '{registry_key}', "
                "but configuration does not define that sensor."
            ) from exc

        return registry_key, sensor_config

    def get_calibration_strategy(
        self, sensor_key: str, sensor_id: int
    ) -> tuple[CalibrationStrategy, ProfileDefinition]:
        """Get or create calibration strategy for a sensor.

        Parameters
        ----------
        sensor_key : str
            Configuration key for the sensor.
        sensor_id : int
            Numeric sensor identifier.

        Returns
        -------
        tuple[CalibrationStrategy, ProfileDefinition]
            Calibration strategy instance and the profile used.
        """
        cache_key = f"{sensor_key}:{sensor_id}"
        if cache_key in self._calibration_cache:
            return self._calibration_cache[cache_key]

        # Try sensor_key first
        try:
            profile = self.catalog.get_calibration(sensor_key)
        except KeyError:
            # Fallback to sensor_id
            try:
                profile = self.catalog.get_calibration(str(sensor_id))
            except KeyError:
                # Default to identity
                profile = ProfileDefinition(
                    profile_id=f"calibration.identity.{sensor_key}",
                    strategy="identity",
                    parameters=None,
                )

        strategy = build_calibration_strategy(profile)
        self._calibration_cache[cache_key] = (strategy, profile)
        return strategy, profile

    def get_normalization_strategy(
        self, sensor_key: str, sensor_id: int
    ) -> tuple[NormalizationStrategy, ProfileDefinition]:
        """Get or create normalization strategy for a sensor.

        Parameters
        ----------
        sensor_key : str
            Configuration key for the sensor.
        sensor_id : int
            Numeric sensor identifier.

        Returns
        -------
        tuple[NormalizationStrategy, ProfileDefinition]
            Normalization strategy instance and the profile used.
        """
        cache_key = f"{sensor_key}:{sensor_id}"
        if cache_key in self._normalization_cache:
            return self._normalization_cache[cache_key]

        # Try sensor_key first
        try:
            profile = self.catalog.get_normalization(sensor_key)
        except KeyError:
            # Fallback to sensor_id
            try:
                profile = self.catalog.get_normalization(str(sensor_id))
            except KeyError:
                # Default to identity
                profile = ProfileDefinition(
                    profile_id=f"normalization.identity.{sensor_key}",
                    strategy="identity",
                    parameters=None,
                )

        strategy = build_normalization_strategy(profile)
        self._normalization_cache[cache_key] = (strategy, profile)
        return strategy, profile

    def get_imputation_strategy(
        self, sensor_key: str, sensor_config: SensorConfig
    ) -> ImputationStrategy:
        """Get or create imputation strategy for a sensor.

        Parameters
        ----------
        sensor_key : str
            Configuration key for the sensor.
        sensor_config : SensorConfig
            Sensor configuration containing imputation settings.

        Returns
        -------
        ImputationStrategy
            Imputation strategy instance.
        """
        if sensor_key in self._imputation_cache:
            return self._imputation_cache[sensor_key]

        strategy = build_imputation_strategy(sensor_config)
        self._imputation_cache[sensor_key] = strategy
        return strategy

    def get_smoothing_strategy(
        self, sensor_key: str, sensor_config: SensorConfig
    ) -> SmoothingStrategy:
        """Get or create smoothing strategy for a sensor.

        Parameters
        ----------
        sensor_key : str
            Configuration key for the sensor.
        sensor_config : SensorConfig
            Sensor configuration containing smoothing settings.

        Returns
        -------
        SmoothingStrategy
            Smoothing strategy instance.
        """
        if sensor_key in self._smoothing_cache:
            return self._smoothing_cache[sensor_key]

        strategy = build_smoothing_strategy(sensor_config)
        self._smoothing_cache[sensor_key] = strategy
        return strategy

    def get_dq_weights(self) -> dict[str, float]:
        """Get data quality scoring weights.

        Returns
        -------
        dict[str, float]
            Weights for validation flags (range_ok, roc_ok, stuck_ok).
        """
        return self.rules.defaults.scoring.weights.to_dict()
