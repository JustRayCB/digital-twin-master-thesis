from abc import ABC, abstractmethod
from base64 import b64decode

from sqlalchemy import text

from dt.communication.adapters import dump, load
from dt.communication.dataclasses import CameraSnapshot
from dt.data.database.base_storage import DatabaseStorage


class SnapshotStorage(DatabaseStorage, ABC):
    """Storage capability for camera snapshot persistence and retrieval."""

    @abstractmethod
    def ingest_camera_snapshot(self, snapshot: CameraSnapshot) -> int:
        """Ingest a camera snapshot.

        Parameters
        ----------
        snapshot : CameraSnapshot
            The camera snapshot payload to persist.

        Returns
        -------
        int
            Identifier of the inserted snapshot row.
        """
        ...

    @abstractmethod
    def get_latest_camera_snapshot(self, plant_id: int) -> CameraSnapshot | None:
        """Fetch the latest camera snapshot for a plant.

        Parameters
        ----------
        plant_id : int
            Plant identifier.
        Returns
        -------
        CameraSnapshot | None
            Latest snapshot if present, otherwise None.
        """
        ...


class SnapshotStore(SnapshotStorage):
    """Persistence for camera snapshots."""

    def ingest_camera_snapshot(self, snapshot: CameraSnapshot) -> int:
        query = """
            INSERT INTO camera_snapshots (
                timestamp, sensor_id, plant_id, topic, mime_type, image,
                correlation_id, width, height
            ) VALUES (
                to_timestamp(:timestamp), :sensor_id, :plant_id, :topic,
                :mime_type, :image, :correlation_id, :width, :height
            )
            RETURNING id
        """
        params = dump("db_row", snapshot)
        params["image"] = b64decode(params.pop("image"))
        with self._get_connection() as conn:
            snapshot_id = self._get_id(conn.execute(text(query), params))
            self.logger.info(
                f"Ingested camera snapshot {snapshot_id} for sensor {snapshot.sensor_id}"
            )
            return snapshot_id

    def get_latest_camera_snapshot(self, plant_id: int) -> CameraSnapshot | None:
        query = """
            SELECT plant_id, sensor_id, timestamp, topic, correlation_id, mime_type, image, width, height
            FROM camera_snapshots
            WHERE plant_id = :plant_id
            ORDER BY timestamp DESC
            LIMIT 1
        """
        with self._get_connection() as conn:
            row = conn.execute(text(query), {"plant_id": plant_id}).fetchone()
            if row is None:
                return None
            return load("db_row", CameraSnapshot, row)
