import mimetypes
from abc import ABC, abstractmethod
from base64 import b64decode, b64encode
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text

from dt.communication.adapters import dump
from dt.communication.dataclasses import CameraSnapshot
from dt.communication.dataclasses.queries import CameraSnapshotQuery
from dt.communication.topics import Topics
from dt.data.database.base_storage import DatabaseStorage
from dt.utils import Config


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
    def get_latest_camera_snapshot(
        self, plant_id: int, topic: Topics | None = None
    ) -> CameraSnapshot | None:
        """Fetch the latest camera snapshot for a plant.

        Parameters
        ----------
        plant_id : int
            Plant identifier.
        topic : Topics | None
            Optional camera topic to restrict the lookup.
        Returns
        -------
        CameraSnapshot | None
            Latest snapshot if present, otherwise None.
        """
        ...

    @abstractmethod
    def query_camera_snapshots(self, query: CameraSnapshotQuery) -> list[CameraSnapshot]:
        """Fetch camera snapshots for a plant within an optional time interval."""
        ...


class SnapshotStore(SnapshotStorage):
    """Persistence for camera snapshots."""

    def __init__(
        self,
        storage_root: str = Config.SNAPSHOT_STORAGE_ROOT,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.storage_root = Path(storage_root)

    def _build_file_ref(self, snapshot: CameraSnapshot) -> Path:
        """Build a deterministic relative file reference for a snapshot."""
        timestamp = datetime.fromtimestamp(snapshot.timestamp, tz=timezone.utc)
        stamp = timestamp.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        suffix = mimetypes.guess_extension(snapshot.mime_type)
        return (
            Path(f"plant-{snapshot.plant_id}")
            / f"sensor-{snapshot.sensor_id}"
            / f"{stamp}-{snapshot.correlation_id}{suffix}"
        )

    def _write_snapshot_file(self, file_ref: Path, snapshot: CameraSnapshot) -> None:
        """Persist raw decoded snapshot bytes under the configured storage root."""
        file_path = self.storage_root / file_ref
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(b64decode(snapshot.image))

    def _load_snapshot_image(self, file_ref: Path) -> str:
        """Load raw snapshot bytes from disk and return inline base64 data."""
        file_path = self.storage_root / file_ref
        try:
            image_bytes = file_path.read_bytes()
        except FileNotFoundError as exc:
            raise RuntimeError(f"Snapshot file not found: {file_ref}") from exc
        return b64encode(image_bytes).decode("ascii")

    def _snapshot_from_row(self, row, image: str) -> CameraSnapshot:
        """Construct a public snapshot payload from a DB row and inline image data."""
        return CameraSnapshot(
            plant_id=row.plant_id,
            sensor_id=row.sensor_id,
            timestamp=row.timestamp.timestamp(),
            topic=Topics.from_short_name(row.topic),
            correlation_id=row.correlation_id,
            mime_type=row.mime_type,
            image=image,
            width=row.width,
            height=row.height,
        )

    def ingest_camera_snapshot(self, snapshot: CameraSnapshot) -> int:
        query = """
            INSERT INTO camera_snapshots (
                timestamp, sensor_id, plant_id, topic, mime_type,
                correlation_id, width, height, file_ref
            ) VALUES (
                to_timestamp(:timestamp), :sensor_id, :plant_id, :topic,
                :mime_type, :correlation_id, :width, :height, :file_ref
            )
            RETURNING id
        """
        params = dump("db_row", snapshot)
        params.pop("image")
        file_ref = self._build_file_ref(snapshot)
        params["file_ref"] = str(file_ref)
        self._write_snapshot_file(file_ref, snapshot)

        try:
            with self._get_connection() as conn:
                snapshot_id = self._get_id(conn.execute(text(query), params))
        except Exception:
            (self.storage_root / file_ref).unlink(missing_ok=True)
            raise

        self.logger.info(f"Ingested camera snapshot {snapshot_id} for sensor {snapshot.sensor_id}")
        return snapshot_id

    def get_latest_camera_snapshot(
        self, plant_id: int, topic: Topics | None = None
    ) -> CameraSnapshot | None:
        query = """
            SELECT id, plant_id, sensor_id, timestamp, topic, correlation_id, mime_type,
                   width, height, file_ref
            FROM camera_snapshots
            WHERE plant_id = :plant_id
        """
        params: dict[str, int | str] = {"plant_id": plant_id}

        if topic is not None:
            query += " AND topic = :topic"
            params["topic"] = topic.short_name

        query += """
            ORDER BY timestamp DESC
            LIMIT 1
        """
        with self._get_connection() as conn:
            row = conn.execute(text(query), params).fetchone()

        if row is None:
            return None

        image = self._load_snapshot_image(Path(row.file_ref))
        return self._snapshot_from_row(row, image)

    def query_camera_snapshots(self, query: CameraSnapshotQuery) -> list[CameraSnapshot]:
        sql = """
            SELECT id, plant_id, sensor_id, timestamp, topic, correlation_id, mime_type,
                   width, height, file_ref
            FROM camera_snapshots
            WHERE plant_id = :plant_id
        """
        params: dict[str, float | int] = {"plant_id": query.plant_id}

        if query.since is not None:
            sql += " AND timestamp >= to_timestamp(:since)"
            params["since"] = query.since
        if query.until is not None:
            sql += " AND timestamp <= to_timestamp(:until)"
            params["until"] = query.until

        sql += " ORDER BY timestamp ASC"

        with self._get_connection() as conn:
            rows = conn.execute(text(sql), params).fetchall()

        snapshots: list[CameraSnapshot] = []
        for row in rows:
            image = self._load_snapshot_image(Path(row.file_ref))
            snapshots.append(self._snapshot_from_row(row, image))
        return snapshots
