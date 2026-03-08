# Spart Streaming

Va nous permettre de traiter des flux de données en temps réel sous formes de DataFrame.
Les DataFrame sont des structures de données distribuées qui permettent de manipuler des données de manière similaire à Pandas.
On peut utiliser des DataFrame pour effectuer des opérations SQL et des fonctions analytiques.

Nous voulons donc transformer un flux de données en DataFrame et faire des opérations comme

- aggregation: C'est une opération qui consiste à regrouper les données en fonction de certaines
  colonnes et à effectuer des calculs sur ces groupes. Par exemple, on peut vouloir calculer la somme ou la moyenne d'une colonne pour chaque groupe.
- join: C'est une opération qui consiste à combiner deux DataFrames en fonction d'une ou plusieurs colonnes communes.
  Par exemple, on peut vouloir combiner les données de deux DataFrames en fonction d'une colonne clé.
- window: C'est une opération qui consiste à diviser les données en fenêtres temporelles et à effectuer des calculs sur ces fenêtres.
  Par exemple, on peut vouloir calculer la somme ou la moyenne d'une colonne pour chaque fenêtre temporelle.
- filter: C'est une opération qui consiste à filtrer les données en fonction de certaines conditions.
  Par exemple, on peut vouloir filtrer les données pour ne garder que celles qui répondent à certaines conditions.
- map: C'est une opération qui consiste à appliquer une fonction à chaque élément d'un DataFrame.
  Par exemple, on peut vouloir appliquer une fonction de transformation à chaque élément d'une colonne

=> Elles vont nous aider à extraire des **feature** en se basant sur les données (historique) de streaming.

# Learning tasks

- Détection d'anomalies
    -
- Prédiction de besoin de d'arrosage
    - Fenêtre de données par exemple de 30 min
    - Jointure de ces données avec l'historique d'humidité du sol
    - Analyser avec la moyenne sur plusieurs jours pour ajuster la durée d'arrosage idéale
    - Calculer la tendance de séchage pour prédire à quel moment on atteindra le seuil critique
- Prédiction de besoin de lumière
    - Fenêtre de données par 24H séparant le jour et la nuit
    - Jointure de ces données avec les données de
    - Analyser avec la moyenne sur plusieurs jours pour ajuster la durée d'exposition idéale
- Prédiction de besoin de chaleur (ou fraicheur)
    - Fenêtre de donénes à court-terme (1H) pour des ajustement immédiats et à long terme (7j) pour analyser les tendance
    - Jointure de ces données avec les données de humidité, humidité du sol et observer la relation

Explorer la technologie pour un grand nombre de capteurs
Feature engineering grace à Spark streaming
Avoir un exemple avec une 10e de capteurs
Stocker les variables dans la bdd (évaluer le relevance des variables ) Centaine de variable (moyenne sur 10min etc ...)
Avoir un réflexion sur ça
10 modèles ,comparer et au long terme se passer des données long-terme de la BDD

Intégrer la bdd tS et Spark series
Petit truc de prédictions (prédire température ds 10 min), ou ce modèle va être stocker, comment est-ce qu'il va être stocker

Prendre 2 semaines pour avancer puis rapport

- Introduction
- SOA
- Analyse gestion données en streaming, architecture, comment faire du ML
- Partie modèlisation
- Implémentation
- Que faire l'année prochaine
