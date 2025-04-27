"""
Digital Twin Real-time Sensor Prediction Module using Recursive Least Squares (RLS).

This module implements a Recursive Least Squares algorithm to predict sensor values
in real-time from streaming data, providing a digital twin representation of
environmental monitoring systems.
"""

import dataclasses
import os
from typing import Any, Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json
from pyspark.sql.streaming.state import GroupState, GroupStateTimeout
from pyspark.sql.types import (ArrayType, FloatType, IntegerType, StringType,
                               StructField, StructType)

from dt.communication.topics import Topics
from dt.utils import Config

""" 
Kafka configuration if not : 
Failed to find data source: kafka. Please deploy the application as per the deployment section of Structured Streaming + Kafka Integration Guide. 
"""
os.environ["PYSPARK_SUBMIT_ARGS"] = (
    "--packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.2.0 pyspark-shell"
)

# Define schemas
SENSOR_SCHEMA = StructType(
    [
        StructField("sensor_id", IntegerType()),
        StructField("timestamp", FloatType()),
        StructField("value", FloatType()),
        StructField("unit", StringType()),
        StructField("topic", StringType()),
    ]
)

RLS_STATE_SCHEMA = StructType(
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
# Define output schema
OUTPUT_SCHEMA = StructType(
    [
        StructField("topic", StringType()),
        StructField("timestamp", FloatType()),
        StructField("value", FloatType()),
        StructField("prediction", FloatType()),
        StructField("error", FloatType()),
        StructField("mse", FloatType()),
    ]
)


# Model parameters
DEFAULT_FORGETTING_FACTOR = 0.98  # Slight forgetting for adapting to changes
INITIAL_COVARIANCE_VALUE = 10.0  # High values for faster initial adaptation
# RECENT_DATA_SIZE = 100  # Number of recent data points to store
# ERROR_HISTORY_SIZE = 100  # Number of recent errors to store
MAX_HISTORY_SIZE = 100  # Maximum number of historical data points/errors to keep
N_FEATURES = 10  # Number of features in the model


@dataclasses.dataclass
class RLSState:
    """Represents the state of the Recursive Least Squares model.

    This class encapsulates all state parameters needed for the RLS algorithm,
    making state management more explicit and maintainable.
    """

    beta: np.ndarray  # Model parameters (weights)
    V: np.ndarray  # Covariance matrix
    nu: float  # Forgetting factor
    mse: float  # Mean squared error
    N: int  # Number of samples processed
    recent_data: np.ndarray  # Recent data points for feature engineering
    errors: np.ndarray  # History of prediction errors

    @classmethod
    def initialize(
        cls, n_features: int = N_FEATURES, nu: float = DEFAULT_FORGETTING_FACTOR
    ) -> "RLSState":
        """Initialize a new RLS state with default parameters.

        Args:
            n_features: Number of features in the model

        Returns:
            A new RLSState instance with initialized values
        """
        beta = np.zeros(n_features + 1)  # +1 for intercept
        V = np.eye(n_features + 1) * INITIAL_COVARIANCE_VALUE
        recent_data = np.zeros((MAX_HISTORY_SIZE, n_features + 1))
        errors = np.array([])

        return cls(
            beta=beta,
            V=V,
            nu=nu,
            mse=0.0,
            N=0,
            recent_data=recent_data,
            errors=errors,
        )

    def to_tuple(self) -> Tuple:
        """Convert the state to a tuple format for Spark state storage.

        Returns:
            Tuple representation of the state
        """
        return (
            self.beta.tolist(),
            self.V.tolist(),
            float(self.nu),
            float(self.mse),
            int(self.N),
            self.recent_data.tolist(),
            self.errors.tolist(),
        )

    @classmethod
    def from_tuple(cls, state_data: Tuple) -> "RLSState":
        """Create an RLSState from a tuple of state values.

        Args:
            state_data: Tuple containing state parameters

        Returns:
            Reconstructed RLSState object
        """
        beta, V, nu, mse, N, recent_data, errors = state_data
        return cls(
            beta=np.array(beta),
            V=np.array(V),
            nu=nu,
            mse=mse,
            N=N,
            recent_data=np.array(recent_data),
            errors=np.array(errors),
        )


class RLSPredictor:
    """Implements the Recursive Least Squares prediction algorithm.

    This class handles the core RLS algorithm logic, including prediction,
    parameter updates, and feature engineering.
    """

    def __init__(
        self,
        feature_dim: int,
        nu: float = DEFAULT_FORGETTING_FACTOR,
        max_history: int = MAX_HISTORY_SIZE,
    ):
        """
        Initialize the RLS predictor

        Args:
            feature_dim: dimension of feature vector
            nu: forgetting factor (0 < nu <= 1)
            max_history: maximum number of recent observations to store
        """
        self.feature_dim = feature_dim
        self.nu = nu
        self.max_history = max_history

    def initialize_state(self) -> RLSState:
        """Create initial state for RLS algorithm"""
        return RLSState.initialize(self.feature_dim, self.nu)

    def RLS_step(
        self,
        state: RLSState,
        x: np.ndarray,
        y: float,
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
        # Add intercept term to features
        x_with_intercept = np.append(1, x)

        # Make prediction using current parameters
        yhat = np.dot(x_with_intercept, state.beta)

        # Calculate prediction error
        err = y - yhat

        # Update covariance matrix V
        Vx = np.dot(state.V, x_with_intercept)
        denominator = state.nu + np.dot(x_with_intercept, Vx)
        V_new = (state.V - np.outer(Vx, Vx) / denominator) / state.nu

        # Compute Kalman gain
        alpha = Vx / denominator

        # Update parameters
        beta_new = state.beta + alpha * err

        return beta_new, V_new, err, yhat

    def update(
        self, state: RLSState, x: np.ndarray, y: float
    ) -> Tuple[RLSState, float, float, float]:
        """Update the RLS state with new observation

        Parameters
        ----------
        state : RLSState
            Current state of the RLS algorithm
        x : numpy.ndarray
            Feature vector (1D array)
        y : float
            Target variable (scalar)

        Returns
        -------
        tuple
            Updated state, predicted value, prediction error, and mean squared error

        """
        # Perform RLS step and update state
        beta_new, V_new, error, yhat = self.RLS_step(state, x, y)
        N_new = state.N + 1
        mse_new = (state.mse * (N_new - 1) + error**2) / N_new if N_new > 1 else error**2

        # Update recent data (add new data point and shift if needed)
        new_data_point = np.append(y, x)
        if N_new <= len(state.recent_data):
            recent_data_new = state.recent_data.copy()
            recent_data_new[N_new - 1] = new_data_point
        else:
            recent_data_new = np.roll(state.recent_data, -1, axis=0)
            recent_data_new[-1] = new_data_point

        # Add error to history
        errors_new = np.append(state.errors, error)
        if len(errors_new) > self.max_history:
            errors_new = errors_new[-self.max_history :]

        new_state = RLSState(
            beta=beta_new,
            V=V_new,
            nu=self.nu,
            mse=mse_new,
            N=N_new,
            recent_data=recent_data_new,
            errors=errors_new,
        )
        return new_state, yhat, error, mse_new

    def predict_future(
        self, state: RLSState, steps_ahead: int = 1, timestamp_increment: float = 1.0
    ) -> List[Dict[str, float]]:
        """Predict future values based on current state

        Args:
            state: Current RLS state
            steps_ahead: Number of time points to predict ahead
            timestamp_increment: Time increment between predictions (in seconds)

        Returns:
            List of predicted future values
        """
        # At least half of the history is needed for prediction
        if state.N < self.max_history // 2 and not state.N % timestamp_increment == 0:
            # No data available for prediction
            return []
        predictions = []
        # Get the correct index for the most recent data
        most_recent_idx = min(state.N - 1, len(state.recent_data) - 1)

        most_recent_data = state.recent_data[most_recent_idx]
        original_timestamp = most_recent_data[2]  # Timestamp is at index 2
        last_value = most_recent_data[0]  # Value is at index 0

        # TODO: Calculate average time difference between recent samples if not provided

        # Work with a copy of features to avoid modifying state
        # NOTE: timestamp is at index 1 in engineer_features + 1 because we add the value at 0 in update
        # original_timestamp = state.recent_data[-1][2]
        # last_value = state.recent_data[-1][0]  # See update
        sim_state = RLSState(
            beta=state.beta.copy(),
            V=state.V.copy(),
            nu=state.nu,
            mse=state.mse,
            N=state.N,
            recent_data=state.recent_data.copy(),
            errors=state.errors.copy(),
        )

        for step in range(1, steps_ahead + 1):

            next_timestamp = original_timestamp + step * timestamp_increment
            x = self.engineer_features(
                {"timestamp": next_timestamp},  # Only need timestamp
                sim_state,
            )

            # Make prediction using current beta
            x_with_intercept = np.append(1, x)
            yhat = np.dot(x_with_intercept, sim_state.beta)
            predictions.append(
                {
                    "timestamp": next_timestamp,
                    "value": yhat,
                }
            )

            # Update state with the predicted value
            # NOTE: we use the predicted value as the new value
            sim_state, _, _, _ = self.update(sim_state, x, yhat)

        return predictions

    def engineer_features(self, new_value: Dict[str, Any], state: RLSState) -> np.ndarray:
        """
        Create feature vector from current value and historical data

        Args:
            new_value: dictionary with current sensor reading
            state: current RLS state containing historical data

        Returns:
            feature vector for prediction
        """
        # Prepare historical data array
        historical_values = np.array(state.recent_data)

        # Initialize feature vector
        features = np.zeros(self.feature_dim, dtype=float)

        # If we have historical data, extract meaningful features
        if state.N > 0:
            features[0] = float(state.N)  # Counter/time feature
            features[1] = float(new_value["timestamp"])  # Timestamp

            # Last observations
            features[2] = float(historical_values[-1][0]) if state.N > 0 else 0.0
            features[3] = float(historical_values[-2][0]) if state.N > 1 else 0.0
            features[4] = float(historical_values[-3][0]) if state.N > 2 else 0.0

            # Statistical features
            values = historical_values[:, 0]
            features[5] = float(np.mean(values)) if state.N > 0 else 0.0
            features[6] = float(np.std(values)) if state.N > 1 else 0.0
            features[7] = float(np.max(values)) if state.N > 0 else 0.0
            features[8] = float(np.min(values)) if state.N > 0 else 0.0

            # Time-related features
            features[9] = float(new_value["timestamp"] % 86400)  # Time of day (seconds)
        else:
            # If no history yet, populate what we can
            features[0] = 0.0  # First observation
            features[1] = float(new_value["timestamp"])
            features[9] = float(new_value["timestamp"] % 86400)

        return features


def process_batch(
    _: Any, new_values_iter: Iterable[pd.DataFrame], current_state: GroupState
) -> List[pd.DataFrame]:
    """Process a batch of sensor data with RLS prediction.

    This function is used with Spark's applyInPandasWithState to process
    grouped sensor data while maintaining state across micro-batches.

    Args:
        _: Key for the group (not used)
        new_values_iter: Iterator of DataFrames containing new sensor values
        current_state: GroupState object for maintaining state

    Returns:
        List of DataFrames containing prediction results
    """

    predictor = RLSPredictor(N_FEATURES)
    # Initialize or retrieve state
    if current_state.exists:
        state = RLSState.from_tuple(current_state.get)
    else:
        state = predictor.initialize_state()

    results = []

    # Process each batch of new values
    for new_values in new_values_iter:
        # Extract sensor value
        new_v = new_values.iloc[0].to_dict()
        y = new_v["value"]
        timestamp = new_v["timestamp"]

        # Engineer features
        x = predictor.engineer_features(new_v, state)

        state, yhat, err, mse = predictor.update(state, x, y)

        # Create result record
        result = {
            "topic": new_v["topic"],
            "timestamp": timestamp,
            "value": float(y),
            "prediction": float(yhat),
            "error": float(err),
            "mse": float(mse),
        }
        results.append(pd.DataFrame([result]))

        # Predict future values
        future_predictions = predictor.predict_future(state, steps_ahead=5, timestamp_increment=5)
        for future in future_predictions:
            future_result = {
                "topic": new_v["topic"],
                "timestamp": future["timestamp"],
                "value": None,
                "prediction": float(future["value"]),  # Predicted value
                "error": None,
                "mse": None,
            }
            results.append(pd.DataFrame([future_result]))

    # Update state for next batch
    current_state.update(state.to_tuple())

    return results


def main():
    """Main entry point to start the Digital Twin RLS streaming job."""

    # Create Spark session with appropriate configurations
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
        .option("kafka.bootstrap.servers", Config.KAFKA_URL)
        .option(
            "subscribe",
            ", ".join(
                [
                    Topics.SOIL_MOISTURE.processed,
                    Topics.TEMPERATURE.processed,
                    Topics.HUMIDITY.processed,
                    Topics.LIGHT_INTENSITY.processed,
                ]
            ),
        )
        .option("startingOffsets", "latest")
        .option("failOnDataLoss", "false")
        .load()
    )

    # Parse the Kafka messages into our sensor schema
    parsed_stream = kafka_stream.select(
        from_json(col("value").cast("string"), SENSOR_SCHEMA).alias("data")
    ).select("data.*")

    # Group by topic and apply RLS algorithm with state
    result_stream = parsed_stream.groupBy("topic").applyInPandasWithState(
        process_batch,
        outputStructType=OUTPUT_SCHEMA,
        stateStructType=RLS_STATE_SCHEMA,
        outputMode="append",
        timeoutConf=GroupStateTimeout.NoTimeout,
    )

    # Write predictions to console for debugging
    console_output = (
        result_stream.writeStream.outputMode("append")
        .format("console")
        .option("truncate", False)
        .start()
    )

    # Wait for stream termination
    console_output.awaitTermination()


if __name__ == "__main__":
    main()
