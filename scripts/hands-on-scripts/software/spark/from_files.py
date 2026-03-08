from pyspark.sql import SparkSession
from pyspark.sql.functions import mean, window
from pyspark.sql.types import (DoubleType, StringType, StructField, StructType,
                               TimestampType)

spark = SparkSession.builder.appName("StreamingWindow").getOrCreate()
spark.sparkContext.setLogLevel("ERROR")

# Le schéma pour nos données de capteurs
schema_capteur = StructType(
    [
        StructField("timestamp", TimestampType(), True),
        StructField("id_capteur", StringType(), True),
        StructField("temperature", DoubleType(), True),
    ]
)

# On lit le flux de fichiers JSON
# Remplacez "dossier_capteurs" par le chemin réel
stream_df = spark.readStream.schema(schema_capteur).json("dossier_capteurs")

# On groupe par capteur et par fenêtre de temps de 10 secondes
moyennes_par_fenetre = stream_df.groupBy("id_capteur", window("timestamp", "10 seconds")).agg(
    mean("temperature").alias("temperature_moyenne")  # On applique l'alias ici
)

# On démarre la requête pour afficher le résultat
query = (
    moyennes_par_fenetre.writeStream.outputMode(
        "complete"
    )  # On utilise "complete" pour voir la table de moyennes mise à jour
    .format("console")
    .option("truncate", "false")
    .start()
)

query.awaitTermination()
