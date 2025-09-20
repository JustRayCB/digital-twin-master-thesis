from pyspark.sql import SparkSession
from pyspark.sql.functions import explode, split

# Create SparkSession
spark = SparkSession.builder.appName("Socket Stream Example").master("local[*]").getOrCreate()

spark.sparkContext.setLogLevel("WARN")

# Connect to socket server on localhost:9999
lines = spark.readStream.format("socket").option("host", "localhost").option("port", "9999").load()

# Split the lines into words
words = lines.select(explode(split(lines.value, " ")).alias("word"))

# Count occurrences of each word
wordCounts = words.groupBy("word").count()

# Output running word counts to the console in "complete" mode
query = wordCounts.writeStream.outputMode("complete").format("console").start()

query.awaitTermination()
