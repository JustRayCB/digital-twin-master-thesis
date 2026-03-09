from abc import ABC, abstractmethod
from typing import Any

from sqlalchemy import text

from dt.communication.adapters import dump, load
from dt.communication.dataclasses import SensorDescriptor
from dt.data.database.base_storage import DatabaseStorage


class MetadataStorage(DatabaseStorage, ABC):
    """Storage capability for plant, sensor, and actuator metadata."""

    @abstractmethod
    def upsert_plant(
        self, plant_id: int | None = None, name: str = "", notes: str | None = None
    ) -> int:
        """Create or update a plant record.

        Parameters
        ----------
        plant_id : int, optional
            If provided, updates the existing plant. Otherwise, creates a new plant.
        name : str
            The name of the plant.
        notes : str, optional
            Additional notes about the plant.

        Returns
        -------
        int
            The ID of the created or updated plant.
        """
        ...

    @abstractmethod
    def list_plants(self) -> list[dict[str, Any]]:
        """List all plants.

        Returns
        -------
        list[dict[str, Any]]
            List of plant records as dictionaries.
        """
        ...

    @abstractmethod
    def register_sensor(self, sensor: SensorDescriptor) -> int:
        """Register a new sensor and return its assigned ID.

        Parameters
        ----------
        sensor : SensorDescriptor
            The sensor descriptor to register.

        Returns
        -------
        int
            The assigned ID of the newly registered sensor.
        """
        ...

    @abstractmethod
    def list_sensors(self) -> list[SensorDescriptor]:
        """Return all registered sensors.

        Returns
        -------
        list[SensorDescriptor]
            List of all registered sensor descriptors.
        """
        ...

    @abstractmethod
    def register_actuator(self, plant_id: int, name: str, pin: int, relay_channel: int) -> int:
        """Register a new actuator and return its assigned ID.

        Parameters
        ----------
        plant_id : int
            The ID of the plant this actuator belongs to.
        name : str
            The name of the actuator.
        pin : int
            The GPIO pin the actuator is connected to.
        relay_channel : int
            The relay channel this actuator is connected to.

        Returns
        -------
        int
            The assigned ID of the newly registered actuator.
        """
        ...

    @abstractmethod
    def list_actuators(self) -> list[dict[str, Any]]:
        """List all actuators.

        Returns
        -------
        list[dict[str, Any]]
            List of actuator records as dictionaries.
        """
        ...


class MetadataStore(MetadataStorage):
    """Persistence for plant, sensor, and actuator metadata."""

    def upsert_plant(
        self,
        plant_id: int | None = None,
        name: str = "",
        notes: str | None = None,
    ) -> int:
        query = (
            "UPDATE plants SET name = :name, notes = :notes WHERE id = :id"
            if plant_id
            else "INSERT INTO plants (name, notes) VALUES (:name, :notes) RETURNING id"
        )
        params = {"name": name, "notes": notes, "id": plant_id}

        with self._get_connection() as conn:
            if plant_id:
                conn.execute(text(query), params)
                self.logger.info(f"Updated plant {plant_id}")
                return plant_id

            new_id = self._get_id(conn.execute(text(query), params))
            self.logger.info(f"Created plant {new_id}")
            return new_id

    def list_plants(self) -> list[dict[str, Any]]:
        query = "SELECT id, name, notes FROM plants ORDER BY id"
        with self._get_connection() as conn:
            result = conn.execute(text(query))
            plants = [{"id": row[0], "name": row[1], "notes": row[2]} for row in result]
            self.logger.info(f"Retrieved {len(plants)} plants")
            return plants

    def register_sensor(self, sensor: SensorDescriptor) -> int:
        query = """
            INSERT INTO sensors (plant_id, name, pin, read_interval, status)
            VALUES (:plant_id, :name, :pin, :read_interval, :status)
            ON CONFLICT (plant_id, name) DO UPDATE
            SET pin = EXCLUDED.pin,
                read_interval = EXCLUDED.read_interval,
                status = EXCLUDED.status
            RETURNING id
        """
        with self._get_connection() as conn:
            sensor_id = self._get_id(conn.execute(text(query), dump("db_row", sensor)))
            self.logger.info(f"Registered sensor {sensor.name} (ID: {sensor_id})")
            return sensor_id

    def list_sensors(self) -> list[SensorDescriptor]:
        query = "SELECT id, plant_id, name, pin, read_interval, status FROM sensors ORDER BY id"
        with self._get_connection() as conn:
            sensors = [load("db_row", SensorDescriptor, row) for row in conn.execute(text(query))]
            self.logger.info(f"Retrieved {len(sensors)} sensors")
            return sensors

    def register_actuator(self, plant_id: int, name: str, pin: int, relay_channel: int) -> int:
        query = """
            INSERT INTO actuators (plant_id, name, pin, relay_channel, status)
            VALUES (:plant_id, :name, :pin, :relay_channel, :status)
            ON CONFLICT (plant_id, name) DO UPDATE
            SET pin = EXCLUDED.pin,
                relay_channel = EXCLUDED.relay_channel,
                status = EXCLUDED.status
            RETURNING id
        """
        params = {
            "plant_id": plant_id,
            "name": name,
            "pin": pin,
            "relay_channel": relay_channel,
            "status": "active",
        }
        with self._get_connection() as conn:
            actuator_id = self._get_id(conn.execute(text(query), params))
            self.logger.info(f"Registered actuator {name} (ID: {actuator_id})")
            return actuator_id

    def list_actuators(self) -> list[dict[str, Any]]:
        query = "SELECT id, plant_id, name, pin, relay_channel, status FROM actuators ORDER BY id"
        with self._get_connection() as conn:
            actuators = [row._asdict() for row in conn.execute(text(query))]
            self.logger.info(f"Retrieved {len(actuators)} actuators")
            return actuators
