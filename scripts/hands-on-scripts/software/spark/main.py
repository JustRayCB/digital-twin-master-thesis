from __future__ import annotations

from collections.abc import Iterable as IterableABC

import pandas as pd
from pyspark.sql import DataFrame, Row, SparkSession
from pyspark.sql.streaming.state import GroupState, GroupStateTimeout
from pyspark.sql.types import (StringType, StructField, StructType,
                               TimestampType)

STATE_SCHEMA = StructType([StructField("dernier_timestamp_vu", TimestampType(), True)])

STATUS_SCHEMA = StructType(
    [
        StructField("id_capteur", StringType(), True),
        StructField("status", StringType(), True),
    ]
)

STATUS_COLUMNS = ("id_capteur", "status")


def _normalize_sensor_id(raw_id: object) -> str:
    """Retourne l'identifiant de capteur sous forme de chaîne."""

    if isinstance(raw_id, str):
        return raw_id

    if isinstance(raw_id, Row):
        row_dict = raw_id.asDict(recursive=False)
        if len(row_dict) == 1:
            return str(next(iter(row_dict.values())))
        raise TypeError("La clé de regroupement contient plusieurs colonnes.")

    if isinstance(raw_id, IterableABC) and not isinstance(raw_id, (bytes, bytearray)):
        items = list(raw_id)
        if len(items) == 1:
            return str(items[0])
        raise TypeError("La clé de regroupement contient plusieurs colonnes.")

    return str(raw_id)


def _materialize_events(events: object) -> pd.DataFrame:
    """Retourne une table pandas à partir du batch fourni par Spark."""

    if isinstance(events, pd.DataFrame):
        df = events.copy()
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
        return df

    if isinstance(events, IterableABC):
        frames = [frame for frame in events if isinstance(frame, pd.DataFrame) and not frame.empty]
        if not frames:
            return pd.DataFrame()
        combined = pd.concat(frames, ignore_index=True)
        if "timestamp" in combined.columns:
            combined["timestamp"] = pd.to_datetime(combined["timestamp"], utc=True, errors="coerce")
        return combined

    return pd.DataFrame()


def update_sensor_state(id_capteur: str, events: object, state: GroupState):
    """Met à jour l'état d'un capteur et retourne un statut lors d'un timeout."""

    sensor_id = _normalize_sensor_id(id_capteur)

    if state.hasTimedOut:
        state.remove()
        yield pd.DataFrame([(sensor_id, "Inactif")], columns=STATUS_COLUMNS)
        return

    materialized = _materialize_events(events)
    if not materialized.empty:
        dernier_timestamp = materialized["timestamp"].max()
        if dernier_timestamp is not None:
            state.update(Row(dernier_timestamp_vu=dernier_timestamp))
            state.setTimeoutDuration(5_000)
        yield pd.DataFrame([(sensor_id, "Actif")], columns=STATUS_COLUMNS)


def build_sensor_status_updates(sensor_stream: DataFrame) -> DataFrame:
    """Applique la logique stateful en Python via applyInPandasWithState."""

    return sensor_stream.groupBy("id_capteur").applyInPandasWithState(
        update_sensor_state,
        outputStructType=STATUS_SCHEMA,
        stateStructType=STATE_SCHEMA,
        outputMode="append",
        timeoutConf=GroupStateTimeout.ProcessingTimeTimeout,
    )


def _build_demo_stream(spark: SparkSession) -> DataFrame:
    """Construit un flux artificiel à partir de la source 'rate'."""

    return (
        spark.readStream.format("rate")
        .load()
        .selectExpr(
            "timestamp",
            "CASE WHEN value % 2 = 0 THEN 'capteur_A' ELSE 'capteur_B' END AS id_capteur",
            "CAST(20 + (value % 5) AS DOUBLE) AS temperature",
        )
    )


def main() -> None:
    spark = SparkSession.builder.appName("StatefulSensorMonitoring").getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")

    sensor_stream = _build_demo_stream(spark)
    sensor_status = build_sensor_status_updates(sensor_stream)

    query = (
        sensor_status.writeStream.outputMode("append")
        .format("console")
        .option("truncate", "false")
        .start()
    )

    query.awaitTermination()


if __name__ == "__main__":
    main()
