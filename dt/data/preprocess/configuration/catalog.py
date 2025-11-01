from typing import Mapping

from .profiles import (ProfileCollection, ProfileConfiguration,
                       ProfileDefinition, SensorProfileAssignment,
                       load_profile_configuration)


class CalibrationCatalog:
    """Resolve calibration and normalization profiles for known sensors."""

    def __init__(
        self,
        profiles: ProfileConfiguration,
        sensor_types: Mapping[str, str] | None = None,
    ) -> None:
        self._profiles = profiles
        self._sensor_types: dict[str, str] = dict(sensor_types or {})
        self._bootstrap_override_sensor_types()

    @classmethod
    def from_config_path(
        cls, path: str, sensor_types: Mapping[str, str] | None = None
    ) -> "CalibrationCatalog":
        """Create a catalog by loading profile configuration from disk."""
        profiles = load_profile_configuration(path)
        return cls(profiles, sensor_types=sensor_types)

    def register_sensor(self, sensor_id: str, sensor_type: str) -> None:
        """Associate a sensor identifier with a sensor type."""
        self._sensor_types[sensor_id] = sensor_type

    def reload(
        self,
        profiles: ProfileConfiguration,
        sensor_types: Mapping[str, str] | None = None,
    ) -> None:
        """Replace catalog profiles and optionally reset sensor mappings.

        Parameters
        ----------
        profiles
            Fresh profile configuration to replace the cached instance.
        sensor_types
            Optional mapping of sensor identifiers to sensor types. When provided,
            this replaces all previously registered sensor mappings. When omitted,
            existing registrations are preserved.
        """
        self._profiles = profiles
        if sensor_types is None:
            new_map = dict(self._sensor_types)
        else:
            new_map = dict(sensor_types)
        self._sensor_types = new_map
        self._bootstrap_override_sensor_types()

    def get_calibration(self, sensor_id: str) -> ProfileDefinition:
        """Return the calibration profile for ``sensor_id``."""
        return self._resolve(self._profiles.calibration, sensor_id, "calibration")

    def get_normalization(self, sensor_id: str) -> ProfileDefinition:
        """Return the normalization profile for ``sensor_id``."""
        return self._resolve(self._profiles.normalization, sensor_id, "normalization")

    def _bootstrap_override_sensor_types(self) -> None:
        """Seed sensor type mappings using override metadata."""
        overrides: dict[str, SensorProfileAssignment] = {}
        overrides.update(self._profiles.calibration.overrides)
        overrides.update(self._profiles.normalization.overrides)

        for sensor_id, assignment in overrides.items():
            self._sensor_types[sensor_id] = assignment.sensor_type

    def _resolve(
        self,
        collection: ProfileCollection,
        sensor_id: str,
        section: str,
    ) -> ProfileDefinition:
        override = collection.overrides.get(sensor_id)
        if override:
            return override.profile

        sensor_type = self._sensor_types.get(sensor_id)
        if sensor_type is None:
            raise KeyError(f"No {section} sensor_type mapping registered for '{sensor_id}'")

        try:
            return collection.defaults[sensor_type]
        except KeyError as exc:
            raise KeyError(
                f"No default {section} profile for sensor_type '{sensor_type}' "
                f"(sensor_id='{sensor_id}')"
            ) from exc
