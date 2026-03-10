from typing import Any

import yaml

from dt.communication.adapters.registry import dump, load
from dt.communication.db_client import DatabaseApiClient
from dt.communication.topics import Topics
from dt.data.preprocess.stages.calibration import (CalibrationStrategy,
                                                   build_calibration_strategy)
from dt.data.preprocess.stages.imputation import (ImputationStrategy,
                                                  build_imputation_strategy)
from dt.data.preprocess.stages.normalization import (
    NormalizationStrategy, build_normalization_strategy)
from dt.data.preprocess.stages.smoothing import (SmoothingStrategy,
                                                 build_smoothing_strategy)
from dt.utils import get_logger

from .serialization import ensure_config_serialization
from .types import SensorConfig, SystemConfig

logger = get_logger(__name__)


class ConfigurationManager:
    """Resolve preprocessing configuration for configured sensor streams.

    The preprocessing YAML is organized around streams entries, each of
    which describes the behavior for one logical measurement stream identified
    by (sensor name, topic). A stream can either define all of its settings
    inline or inherit from a named template and override only the fields that
    differ.

    """

    def __init__(self, config_path: str) -> None:
        """Initialise the configuration manager.

        Parameters
        ----------
        config_path : str
            Path to the YAML configuration file.
        """
        self._config_path = config_path
        self._raw_data: dict[str, Any] = {}
        self.config: SystemConfig
        # Mapping of (sensor_name, topic) to the raw stream dict from the YAML, used as the source of
        self._configured_streams: dict[tuple[str, Topics], dict[str, Any]] = {}
        # Cache of resolved SensorConfig objects by (sensor_name, topic) for quick lookup during row processing.
        self._stream_config_cache: dict[tuple[str, Topics], SensorConfig] = {}
        # Contains the resolved mapping from (sensor_id, topic) to sensor name for all configured streams.
        self.sensor_registry: dict[tuple[int, Topics], str] | None = None
        self._strategy_cache: dict[str, dict[tuple[str, Topics], Any]] = {
            "calibration": {},
            "normalization": {},
            "imputation": {},
            "smoothing": {},
        }

        self._load_config()
        self._index_configured_streams()
        self._load_sensor_registry()

    def _load_config(self) -> None:
        """Load and validate the raw YAML configuration document.

        The configuration is stored twice:

        - self._raw_data keeps the original dictionary form so template
          merging can operate on plain mappings.
        - self.config stores the typed SystemConfig view used by
          callers that only need global defaults such as DQ weights.
        """

        ensure_config_serialization()

        with open(self._config_path, encoding="utf-8") as f:
            self._raw_data = yaml.safe_load(f) or {}

        self.config = load("generic", SystemConfig, self._raw_data)

    def _index_configured_streams(self) -> None:
        """Index configured stream definitions by (sensor_name, topic).

        Raises
        ------
        ValueError
            If the YAML defines the same (sensor_name, topic) pair more
            than once.
        """
        configured_streams: dict[tuple[str, Topics], dict[str, Any]] = {}
        for stream in self._raw_data.get("streams", []):
            sensor_name = stream["sensor"]
            topic = load("generic", Topics, stream["topic"])
            configured_key = (sensor_name, topic)
            if configured_key in configured_streams:
                raise ValueError(
                    "Duplicate stream binding for " f"sensor='{sensor_name}' topic='{topic}'"
                )
            configured_streams[configured_key] = dict(stream)

        self._configured_streams = configured_streams

    def _load_sensor_registry(self) -> dict[tuple[int, Topics], str]:
        """Load the runtime sensor registry from the database.

        Returns
        -------
        dict[tuple[int, str], str]
            Mapping from (sensor_id, topic_value) to configured sensor
            name.

        Notes
        -----
        The database stores physical sensors by numeric ID, while the
        preprocessing config is written against sensor names. This method is
        the bridge between those two identity schemes.
        """
        try:
            descriptors = DatabaseApiClient().list_sensors()
        except Exception as exc:
            logger.warning(f"Unable to load sensor registry from database: {exc}")
            self.sensor_registry = {}
            return self.sensor_registry

        self.sensor_registry = {
            (descriptor.id, topic): descriptor.name
            for descriptor in descriptors
            for sensor_name, topic in self._configured_streams
            if sensor_name == descriptor.name
        }
        logger.info(
            f"Loaded resolved stream registry with {len(self.sensor_registry)} sensor streams"
        )
        return self.sensor_registry

    def resolve_sensor_config(
        self, plant_id: int, sensor_id: int, topic: Topics
    ) -> tuple[str, SensorConfig]:
        """Resolve runtime sensor identity back to a configured stream.

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
            Two values:

            - the configured sensor name used as the stream key in the YAML
            - the resolved, template-merged SensorConfig

        Raises
        ------
        KeyError
            If the database registry does not map this (sensor_id, topic)
            pair to any configured stream.
        RuntimeError
            If the database registry cannot be loaded.
        """
        sensor_name = self.sensor_registry.get((sensor_id, topic))
        if sensor_name is None:
            raise KeyError(
                f"No sensor stream registry entry for sensor_id={sensor_id} "
                f"(plant_id={plant_id}, topic={topic})"
            )

        return sensor_name, self.get_stream_config(sensor_name, topic)

    def get_stream_config(self, sensor_name: str, topic: Topics) -> SensorConfig:
        """Return the merged config for one configured stream.

        Parameters
        ----------
        sensor_name : str
            Sensor name used in the YAML streams block.
        topic : str or Topics
            Topic identifier for the logical stream.

        Returns
        -------
        SensorConfig
            Parsed and merged stream configuration.

        Raises
        ------
        KeyError
            If no such (sensor_name, topic) stream exists in the YAML.

        Notes
        -----
        Resolved configs are cached because strategy lookup and Spark row
        processing hit this method repeatedly for the same stream identities.
        """
        cache_key = (sensor_name, topic)
        # Check the cache before doing any work to resolve the config
        cached_config = self._stream_config_cache.get(cache_key)
        if cached_config is not None:
            return cached_config

        # Not in cache, resolve it from the raw YAML
        stream_dict = self._configured_streams.get(cache_key)
        if stream_dict is None:
            raise KeyError(f"Stream '{sensor_name}' on topic '{topic}' not found in configuration.")
        resolved_config = self._resolve_stream_config(stream_dict, topic)
        self._stream_config_cache[cache_key] = resolved_config
        return resolved_config

    def _resolve_stream_config(self, stream_dict: dict[str, Any], topic: Topics) -> SensorConfig:
        """Build a SensorConfig from one raw stream definition.

        Parameters
        ----------
        stream_dict : dict[str, Any]
            Raw stream mapping from the YAML streams section.
        topic_value : str
            Canonical base topic value for this stream.

        Returns
        -------
        SensorConfig
            Parsed, template-merged stream configuration with traceability
            metadata populated.

        Raises
        ------
        ValueError
            If the stream references a template that is not defined.
        """
        sensor_dict = dict(stream_dict)
        sensor_name = str(sensor_dict["sensor"])
        template_name = sensor_dict.get("template")

        if template_name:
            raw_templates = self._raw_data.get("templates", {})
            if template_name not in raw_templates:
                raise ValueError(
                    f"Stream '{sensor_name}' references unknown template '{template_name}'"
                )

            template_dict = raw_templates[template_name]
            # Stream-local fields override the template while preserving any
            # nested fields that are not explicitly replaced.
            final_dict = self._deep_merge(template_dict, sensor_dict)
        else:
            final_dict = sensor_dict

        resolved = load("generic", SensorConfig, final_dict)

        # Populate traceability metadata
        resolved.calibration_profile_id = self._generate_profile_id(
            sensor_name, topic, sensor_dict, template_name, "calibration"
        )
        resolved.normalization_profile_id = self._generate_profile_id(
            sensor_name, topic, sensor_dict, template_name, "normalization"
        )
        return resolved

    def _generate_profile_id(
        self,
        sensor_name: str,
        topic: Topics,
        sensor_dict: dict,
        template_name: str | None,
        section: str,
    ) -> str:
        """Generate a traceability identifier for one config section.

        Parameters
        ----------
        sensor_name : str
            Configured sensor name.
        topic_value : str
            Canonical base topic value for the stream.
        sensor_dict : dict
            Raw stream mapping from the YAML.
        template_name : str or None
            Template name referenced by this stream, if any.
        section : str
            Section name, currently "calibration" or "normalization".

        Returns
        -------
        str
            Stable identifier describing where the section came from.

        Notes
        -----
        When one sensor name is configured for multiple topics, the topic short
        name is appended so those profile IDs remain distinguishable in stored
        processed readings.
        """
        topic_suffix = f":{topic.short_name}" if self._has_multiple_topics(sensor_name) else ""
        if not template_name:
            return (
                f"standalone:{sensor_name}{topic_suffix}" if section in sensor_dict else "default"
            )

        if section in sensor_dict:
            return f"{template_name}:{sensor_name}{topic_suffix}-custom"
        return template_name

    def _has_multiple_topics(self, sensor_name: str) -> bool:
        """Return whether a configured sensor name appears on multiple topics.

        Parameters
        ----------
        sensor_name : str
            Configured sensor name.

        Returns
        -------
        bool
            True when the YAML contains more than one topic for the same
            sensor name, otherwise False.
        """
        configured_topics = {
            topic_value for name, topic_value in self._configured_streams if name == sensor_name
        }
        return len(configured_topics) > 1

    def get_calibration_strategy(self, sensor_name: str, topic: Topics) -> CalibrationStrategy:
        """Return the calibration strategy object for one stream.

        Parameters
        ----------
        sensor_name : str
            Configured sensor name.
        topic : str or Topics
            Topic identifier for the stream.

        Returns
        -------
        CalibrationStrategy
            Executable strategy built from the resolved config.
        """
        return self._get_strategy(
            cache_name="calibration",
            sensor_name=sensor_name,
            topic=topic,
            builder=build_calibration_strategy,
        )

    def get_normalization_strategy(self, sensor_name: str, topic: Topics) -> NormalizationStrategy:
        """Return the normalization strategy object for one stream.

        Parameters
        ----------
        sensor_name : str
            Configured sensor name.
        topic : str or Topics
            Topic identifier for the stream.

        Returns
        -------
        NormalizationStrategy
            Executable strategy built from the resolved config.
        """
        return self._get_strategy(
            cache_name="normalization",
            sensor_name=sensor_name,
            topic=topic,
            builder=build_normalization_strategy,
        )

    def get_imputation_strategy(self, sensor_name: str, topic: Topics) -> ImputationStrategy:
        """Return the imputation strategy object for one stream.

        Parameters
        ----------
        sensor_name : str
            Configured sensor name.
        topic : str or Topics
            Topic identifier for the stream.

        Returns
        -------
        ImputationStrategy
            Executable strategy built from the resolved config.
        """
        return self._get_strategy(
            cache_name="imputation",
            sensor_name=sensor_name,
            topic=topic,
            builder=build_imputation_strategy,
        )

    def get_smoothing_strategy(self, sensor_name: str, topic: Topics) -> SmoothingStrategy:
        """Return the smoothing strategy object for one stream.

        Parameters
        ----------
        sensor_name : str
            Configured sensor name.
        topic : str or Topics
            Topic identifier for the stream.

        Returns
        -------
        SmoothingStrategy
            Executable strategy built from the resolved config.
        """
        return self._get_strategy(
            cache_name="smoothing",
            sensor_name=sensor_name,
            topic=topic,
            builder=build_smoothing_strategy,
        )

    def _get_strategy(self, cache_name: str, sensor_name: str, topic: Topics, builder):
        """Return a cached executable strategy for one config section.

        Parameters
        ----------
        cache_name : str
            Strategy section name, such as "calibration".
        sensor_name : str
            Configured sensor name.
        topic : str or Topics
            Topic identifier for the stream.
        builder : callable
            Factory that converts the typed config section into an executable
            strategy object.

        Returns
        -------
        Any
            Executable strategy instance produced by builder.
        """
        cache_key = (sensor_name, topic)
        if cache_key not in self._strategy_cache[cache_name]:
            config = self.get_stream_config(sensor_name, topic)
            section = getattr(config, cache_name)
            self._strategy_cache[cache_name][cache_key] = builder(section)
        return self._strategy_cache[cache_name][cache_key]

    def _deep_merge(self, base: dict, override: dict) -> dict:
        """Recursively merge two dictionaries.

        Parameters
        ----------
        base : dict
            Template dictionary providing defaults.
        override : dict
            Stream-specific dictionary overriding parts of base.

        Returns
        -------
        dict
            New merged dictionary. The input mappings are not mutated.
        """
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def get_dq_weights(self) -> dict[str, float]:
        """Return configured data-quality scoring weights.

        Returns
        -------
        dict[str, float]
            Serializable weight mapping used by the validation logic.
        """

        return dump("generic", self.config.system.weights)
