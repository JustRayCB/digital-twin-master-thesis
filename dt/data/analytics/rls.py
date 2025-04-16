import os

# os.environ["PYSPARK_SUBMIT_ARGS"] = "--packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.5"
os.environ["PYSPARK_SUBMIT_ARGS"] = (
    "--packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.2.0 pyspark-shell"
)


import json

import numpy as np
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import col, from_json
from pyspark.sql.types import FloatType, IntegerType, StringType, StructField, StructType

from dt.communication.topics import Topics


def initializeRLSState(n_features):
    """Initialize the state for a RLS model"""
    # Initialize parameters
    beta = np.zeros((n_features + 1, 1))  # +1 for intercept

    # Initial covariance matrix (high values for faster initial adaptation)
    v0 = 10.0
    V = np.eye(n_features + 1) * v0

    # Forgetting factor (1.0 = no forgetting, <1.0 = older samples have less weight)
    nu = 0.98  # Slight forgetting for adapting to changes

    # Metrics
    mse = 0.0
    N = 0

    # Recent data storage
    recent_size = 50
    recent_data = np.zeros((recent_size, n_features + 1))
    errors = np.zeros(1)

    return (beta, V, nu, mse, N, recent_data, errors)


def RLSstep(y, x, beta, V, nu=0.9):
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
    # Reshape x for matrix operations
    # x = x.reshape(1, -1)

    # Ensure we include intercept
    x_with_intercept = np.append(1, x)  # .reshape(1, -1)

    # Update covariance matrix V
    V = (1 / nu) * (
        V
        - (
            (V @ x_with_intercept.T @ x_with_intercept @ V)
            / (1 + (x_with_intercept @ V @ x_with_intercept.T))
        )
    )

    # Compute Kalman gain
    alpha = V @ x_with_intercept.T

    # Make prediction using current parameters
    yhat = x_with_intercept @ beta

    # Calculate prediction error
    err = y - yhat

    # Update parameters
    beta = beta + alpha * err

    return beta, V, err, yhat


def updateFunction(new_values, state):
    """Update function for maintaining RLS state across batches

    Parameters
    ----------
    new_values : RDD
        New sensor readings
    state : tuple
        Current state containing beta, V, error metrics, etc.

    Returns
    -------
    tuple
        Updated state containing new beta, V, error metrics, etc.

    """
    if len(new_values) > 0:
        # Extract state
        beta, V, nu, mse, N, recent_data, errors = state

        # Process all new values in the batch
        for yx in new_values:
            # Extract value, assuming format [timestamp, target, feature1, feature2, ...]
            # Extract sensor reading and features
            # Get target value (current reading)
            y = float(yx["value"])

            # Create feature vector from historical data
            # For simplicity, assume we have lagged values available
            # In practice, these would come from the recent_data buffer
            if N < 8:  # Not enough history yet
                # Just store data and wait for more
                if N == 0:
                    x = np.zeros(8)
                else:
                    # Use what we have with padding
                    history = recent_data[:N, 0]
                    x = np.pad(history, (0, 8 - N), "constant")
            else:
                # Use the last 8 values as features
                x = recent_data[:8, 0]

            # # Reshape beta for matrix operations
            # beta = beta.reshape(-1, 1)

            # Perform RLS update
            beta, V, err, yhat = RLSstep(y, x, beta, V, nu)

            # Update metrics
            N += 1
            mse = mse + (err**2 - mse) / (N)
            errors = np.append(errors, err)

            # Store recent data for potential retraining or analysis
            recent_data = np.vstack((yx[1:].reshape(1, -1), recent_data[:-1, :]))

        return (beta, V, nu, mse, N, recent_data, errors, y, yhat)
    else:
        return state


sensor_schema = StructType(
    [
        StructField("sensor_id", IntegerType(), True),
        StructField("timestamp", FloatType(), True),
        StructField("value", FloatType(), True),
        StructField("unit", StringType(), True),
        StructField("topic", StringType(), True),
    ]
)


# Create Spark session
spark = (
    SparkSession.builder.appName("DigitalTwinRLS")  # pyright: ignore[]
    .master("local[5]")
    .getOrCreate()
)

# Initialize streaming context
sc = spark.sparkContext

# kafka_stream = ssc.socketTextStream("localhost", 9092)  # Adjust as needed for your Kafka setup
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

kafka_stream.printSchema()

# Create separate models for each sensor type
models = {
    "soil_moisture": initializeRLSState(10),  # 10 features
    "temperature": initializeRLSState(10),
    "humidity": initializeRLSState(10),
    "light_intensity": initializeRLSState(10),
}

# Create initial RDD with states for all models
initialStateRDD = sc.parallelize([(k, v) for k, v in models.items()])
# Parse the Kafka value column into our sensor schema
parsed_stream = kafka_stream.select(
    from_json(col("value").cast("string"), sensor_schema).alias("data")
).select("data.*")

print(type(parsed_stream))
parsed_stream.printSchema()

parsed_stream.writeStream.format("console").outputMode("append").start().awaitTermination()
