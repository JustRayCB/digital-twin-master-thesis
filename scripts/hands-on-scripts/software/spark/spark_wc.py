"""
This script provides a basic example of a Spark Structured Streaming job that
performs a word count on data received from a network socket.

It demonstrates how to:
- Create a SparkSession.
- Read a stream of data from a socket source.
- Perform transformations on the streaming DataFrame (split lines into words,
  explode the array of words into separate rows, group by word, and count).
- Write the resulting aggregated DataFrame to the console.

How to run this example:
1.  Open a terminal and start a netcat (nc) server to act as the data source:
    `nc -lk 9999`
    (Type some words into this terminal and press Enter. Each line will be
    sent to the Spark script.)

2.  In a separate terminal, run this Spark script from the root of the project:
    `poetry run python scripts/hands-on-scripts/software/spark/spark_wc.py`

The console running the Spark script will display the running word counts,
updating each time new data is processed.
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import explode, split

# --- Create SparkSession ---
# A SparkSession is the entry point to any Spark functionality.
# `appName` sets a name for the application, which will appear in the Spark UI.
# `master("local[*]")` tells Spark to run locally using all available cores.
spark = SparkSession.builder.appName("SocketStreamWordCount").master("local[*]").getOrCreate()

# Set the log level to WARN to reduce the verbosity of the output.
spark.sparkContext.setLogLevel("WARN")

# --- Create Streaming DataFrame ---
# `readStream` is used to create a DataFrame that represents a stream of data.
# `format("socket")` specifies that the data source is a network socket.
# `option("host", "localhost")` and `option("port", "9999")` define the
# address of the socket server.
lines = spark.readStream.format("socket").option("host", "localhost").option("port", "9999").load()

# --- Transformations ---
# The 'lines' DataFrame has a single column "value" of type string.
# 1. `split(lines.value, " ")`: Splits each line into an array of words.
# 2. `explode(...)`: Transforms the array of words into separate rows, each
#    containing a single word in a new column named "word".
words = lines.select(explode(split(lines.value, " ")).alias("word"))

# 3. `groupBy("word").count()`: Groups the DataFrame by the "word" column and
#    counts the occurrences of each word.
wordCounts = words.groupBy("word").count()

# --- Output Sink ---
# `writeStream` is used to define how the output of the streaming query is handled.
# `outputMode("complete")`: The entire result table will be written to the sink
#   after every trigger. This is suitable for aggregate queries like this one.
# `format("console")`: The output will be printed to the console.
query = wordCounts.writeStream.outputMode("complete").format("console").start()

# --- Start the Query ---
# `awaitTermination()` waits for the streaming query to be terminated, either
# by an error or by an explicit stop command (e.g., Ctrl+C).
print("--- Spark Streaming Word Count ---")
print("Listening on localhost:9999. Type words into the netcat terminal.")
print("Press Ctrl+C to stop the script.")
query.awaitTermination()
