import dataclasses
import json
import os
import time
from typing import Any, Dict, Iterable, Tuple

import numpy as np
import pandas as pd
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import col, expr, from_json, struct
from pyspark.sql.streaming.state import GroupState, GroupStateTimeout
from pyspark.sql.types import (ArrayType, FloatType, IntegerType, StringType,
                               StructField, StructType)

from dt.communication.topics import Topics


# Those two classes are taken out from https://www.waitingforcode.com/apache-spark-structured-streaming/making-applyinpandaswithstate-less-painful/read#optimizations_state_management
@dataclasses.dataclass
class StructFieldWithStateUpdateHandler:
    field: StructField

    def get(self, state_dict_to_read: Dict[str, Any]) -> Any:
        return state_dict_to_read[self.field.name]

    def update(self, state_dict_to_update: Dict[str, Any], new_value: Any):
        state_dict_to_update[self.field.name] = new_value


class StateSchemaHandler:
    def __init__(
        self,
        beta: StructFieldWithStateUpdateHandler,
        V: StructFieldWithStateUpdateHandler,
        nu: StructFieldWithStateUpdateHandler,
        mse: StructFieldWithStateUpdateHandler,
        N: StructFieldWithStateUpdateHandler,
        recent_data: StructFieldWithStateUpdateHandler,
        errors: StructFieldWithStateUpdateHandler,
    ):
        self.beta = beta
        self.V = V
        self.nu = nu
        self.mse = mse
        self.N = N
        self.recent_data = recent_data
        self.errors = errors
        self.schema = StructType(
            [
                beta.field,
                V.field,
                nu.field,
                mse.field,
                N.field,
                recent_data.field,
                errors.field,
            ]
        )

    def get_state_as_dict(self, state_tuple: Tuple) -> Dict[str, Any]:
        return dict(zip(self.schema.fieldNames(), state_tuple))

    def get_empty_state_dict(self) -> Dict[str, Any]:
        field_names = self.schema.fieldNames()
        return {field_names[i]: None for i in range(0, len(field_names))}

    @staticmethod
    def transform_in_flight_state_to_state_to_write(in_flight_state: Dict[str, Any]) -> Tuple:
        return tuple(in_flight_state.values())


# Kafka setup
os.environ["PYSPARK_SUBMIT_ARGS"] = (
    "--packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.2.0 pyspark-shell"
)

# Schema for sensor data
sensor_schema = StructType(
    [
        StructField("sensor_id", IntegerType()),
        StructField("timestamp", FloatType()),
        StructField("value", FloatType()),
        StructField("unit", StringType()),
        StructField("topic", StringType()),
    ]
)

# Schema for RLS state - we need to define it for structured streaming
# rls_state_schema = StateSchemaHandler(
#     beta=StructFieldWithStateUpdateHandler(StructField("beta", ArrayType(FloatType()))),
#     V=StructFieldWithStateUpdateHandler(
#         StructField("V", ArrayType(ArrayType(FloatType())))
#     ),
#     nu=StructFieldWithStateUpdateHandler(StructField("nu", FloatType())),
#     mse=StructFieldWithStateUpdateHandler(StructField("mse", FloatType())),
#     N=StructFieldWithStateUpdateHandler(StructField("N", IntegerType())),
#     recent_data=StructFieldWithStateUpdateHandler(
#         StructField("recent_data", ArrayType(ArrayType(FloatType())))
#     ),
#     errors=StructFieldWithStateUpdateHandler(
#         StructField("errors", ArrayType(FloatType()))
#     ),
# )
rls_state_schema = StructType(
    [
        StructField("beta", ArrayType(FloatType())),
        StructField("V", ArrayType(ArrayType(FloatType()))),
        StructField("nu", FloatType()),
        StructField("mse", FloatType()),
        StructField("N", IntegerType()),
        StructField("recent_data", ArrayType(ArrayType(FloatType()))),
        StructField("errors", ArrayType(FloatType())),
    ]
)


def initializeRLSState(n_features: int) -> Dict:
    """Initialize the state for a RLS model with structured streaming format"""
    # Initialize parameters
    beta = np.zeros(n_features + 1)  # +1 for intercept

    # Initial covariance matrix (high values for faster initial adaptation)
    v0 = 10.0
    # V = np.eye(n_features + 1) * v0
    V = np.diag(np.zeros(n_features + 1) + v0)

    # Forgetting factor (1.0 = no forgetting, <1.0 = older samples have less weight)
    nu = 0.98  # Slight forgetting for adapting to changes

    # Metrics
    mse = 0.0
    N = 0

    # Recent data storage
    recent_size = 10
    recent_data = np.zeros((recent_size, n_features + 1))
    errors = np.zeros((1, 1))

    return {
        "beta": beta,
        "V": V,
        "nu": nu,
        "mse": mse,
        "N": N,
        "recent_data": recent_data,
        "errors": errors,
    }


def RLSstep(
    y: float, x: np.ndarray, beta: np.ndarray, V: np.ndarray, nu: float = 0.9
) -> Tuple[np.ndarray, np.ndarray, float, float]:
    """Perform one step of Recursive Least Squares update

    Parameters
    ----------
    y : float
        Target variable (scalar)
    x : numpy.ndarray
        Feature vector (1D array)
    beta : numpy.ndarray
        Current parameter vector
    V : numpy.ndarray
        Current covariance matrix
    nu : float, optional
        Forgetting factor (default is 0.9)

    Returns
    -------
    tuple
        Updated beta, V, prediction error, and predicted value

    """
    # Ensure we include intercept
    x_with_intercept = np.append(1, x)

    # Make prediction using current parameters
    yhat = np.dot(x_with_intercept, beta)

    # Calculate prediction error
    err = y - yhat

    # Update covariance matrix V
    Vx = np.dot(V, x_with_intercept)
    denominator = nu + np.dot(x_with_intercept, Vx)
    V_new = (V - np.outer(Vx, Vx) / denominator) / nu

    # Compute Kalman gain
    alpha = Vx / denominator

    # Update parameters
    beta_new = beta + alpha * err

    return beta_new, V_new, err, yhat


def process_sensor_batch(
    _, new_values_iter: Iterable[pd.DataFrame], current_state: GroupState
) -> Iterable[pd.DataFrame]:
    if current_state.exists:
        # If state exists, retrieve it
        state_data = current_state.get
    else:
        # If no state exists, initialize it
        state_data = tuple(initializeRLSState(10).values())
        current_state.update(state_data)

    beta, V, nu, mse, N, recent_data, errors = state_data
    recent_data = np.array(recent_data)  # Convert the list of lists to a NumPy array

    results: list[pd.DataFrame] = []
    for new_values in new_values_iter:
        # Convert the incoming DataFrame to a NumPy array

        print("=========")
        print(new_values)
        print(type(new_values))
        y = float(new_values.iloc[0]["value"])

        # Create feature vector from historical data
        # TODO: have more meaningful features
        if N > 0:
            x = np.array(
                [
                    float(N),  # Counter
                    float(new_values.iloc[0]["timestamp"]),  # Time feature
                    float(recent_data[-1][0]) if N > 0 else 0.0,  # Last value
                    float(recent_data[-2][0]) if N > 1 else 0.0,  # Second last value
                    float(recent_data[-3][0]) if N > 2 else 0.0,  # Third last value
                    float(np.mean(recent_data[:, 0])) if N > 0 else 0.0,  # Mean
                    float(np.std(recent_data[:, 0])) if N > 1 else 0.0,  # Std deviation
                    float(np.max(recent_data[:, 0])) if N > 0 else 0.0,  # Max
                    float(np.min(recent_data[:, 0])) if N > 0 else 0.0,  # Min
                    float(new_values["timestamp"] % 86400),  # Time of day (cyclical)
                ],
                dtype=float,
            )
        else:
            # Initial features when no history exists
            x = np.zeros(10, dtype=float)
            x[0] = float(N)
            x[1] = float(new_values.iloc[0]["timestamp"])
            x[9] = float(new_values.iloc[0]["timestamp"] % 86400)
        # Apply RLS step
        beta, V, err, yhat = RLSstep(y, x, beta, V, nu)

        # Update metrics
        N += 1
        mse = (mse * (N - 1) + err**2) / N if N > 0 else err**2
        # Update recent data (add new data point and shift)
        new_data_point = np.append(y, x)
        if N <= len(recent_data):
            recent_data[N - 1] = new_data_point
        else:
            recent_data = np.roll(recent_data, -1, axis=0)
            recent_data[-1] = new_data_point
        # Add error to history
        errors = np.append(errors, err)
        if len(errors) > 100:  # Keep last 100 errors
            errors = errors[-100:]
        # Add results
        result = {
            "topic": new_values["topic"],
            "timestamp": new_values["timestamp"],
            "value": float(y),
            "prediction": float(yhat),
            "error": float(err),
        }
        results.append(pd.DataFrame(result))

    # Update state for next batch
    updated_state = {
        "beta": beta.tolist(),
        "V": V.tolist(),
        "nu": float(nu),
        "mse": float(mse),
        "N": int(N),
        "recent_data": recent_data.tolist(),
        "errors": errors.tolist(),
    }

    # Update the state with the new values
    current_state.update(tuple(updated_state.values()))

    return results


def main():
    # Create Spark session
    spark = (
        SparkSession.builder.appName("DigitalTwinRLS")  # pyright: ignore[]
        .master("local[*]")
        .config("spark.sql.shuffle.partitions", "1")
        .config("spark.executor.extraJavaOptions", "-Dio.netty.tryReflectionSetAccessible=true")
        .config("spark.driver.extraJavaOptions", "-Dio.netty.tryReflectionSetAccessible=true")
        .getOrCreate()
    )

    # Connect to Kafka stream
    kafka_stream = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", "81.243.95.83:9092")
        .option(
            "subscribe",
            f"{Topics.SOIL_MOISTURE.processed}, {Topics.TEMPERATURE.processed}, {Topics.HUMIDITY.processed}, {Topics.LIGHT_INTENSITY.processed}",
        )
        .option("startingOffsets", "latest")
        .option("failOnDataLoss", "false")
        .load()
    )

    # Parse the Kafka value column into our sensor schema
    parsed_stream = kafka_stream.select(
        from_json(col("value").cast("string"), sensor_schema).alias("data")
    ).select("data.*")

    # Set up state timeout to prevent stale states

    output_schema = StructType(
        [
            StructField("topic", StringType()),
            StructField("timestamp", FloatType()),
            StructField("value", FloatType()),
            StructField("prediction", FloatType()),
            StructField("error", FloatType()),
        ]
    )

    # Group by topic and apply RLS algorithm with state
    result_stream = parsed_stream.groupBy("topic").applyInPandasWithState(
        process_sensor_batch,
        outputStructType=output_schema,
        stateStructType=rls_state_schema,
        outputMode="append",
        timeoutConf=GroupStateTimeout.NoTimeout,
    )

    # Output the predictions to console (for debugging)
    console_output = (
        result_stream.writeStream.outputMode("append")
        .format("console")
        .option("truncate", False)
        .start()
    )

    # Wait for termination
    console_output.awaitTermination()


if __name__ == "__main__":
    main()
