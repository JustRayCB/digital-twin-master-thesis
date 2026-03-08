from pyspark.sql import SparkSession

# 1. Initialiser la SparkSession
spark = SparkSession.builder.appName("StructuredStreamingHelloWorld").getOrCreate()
spark.sparkContext.setLogLevel("WARN")
# 2. Créer un DataFrame de streaming (notre source de données)
# On utilise le format "rate" qui génère des données en mémoire,
# parfait pour les tests. Il crée une table avec deux colonnes :
# 'timestamp' (l'heure) et 'value' (un compteur qui commence à 0).
lines = spark.readStream.format("rate").option("rowsPerSecond", 1).load()

df_doubled = lines.withColumn("value_doubled", lines["value"] * 2)

# 3. Démarrer la requête de streaming
# On affiche simplement le contenu du DataFrame dans la console.
query = df_doubled.writeStream.outputMode("append").format("console").start()

# 4. Attendre que la requête se termine
query.awaitTermination()
