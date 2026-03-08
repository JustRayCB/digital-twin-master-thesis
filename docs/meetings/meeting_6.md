# Présentation MLG

- Introduction
    - Mémoire
        - Pascal Tribel & Gianluca Bontempi
        - DT plant health monitoring
        - Projet qui regroupe plein de notions d'informatique, design de systèmes, IA, modélisation/simulation
    - Challenges
        - Optimisation de ressources
        - Monitorer avec précision
        - Simuler and prédire des problèmes (et le prévenirs)
- Objectifs
    - DT plant health monitoring
    - Parametres: humidité du sol, humidité ambian, température, lumières, couleur de la plante, taille
    - Actions automatiés. Eaux, température, lumière
    - Systèmes Modulaire et adaptable
- Architecture
    - Plusieurs capteurs
    - InfluxDB -> Time-series data
    - Spark Streaming -> Analytics of TS data, ML
    - Kafka
    - Visualisation via une web app Flask
- Vizualisation
    - Exemple
- Futur
    - Étendre les capacité de prédictions avec des modèles hors-ligne, différents paramètres
    - Intégrer ML
    - Automatisation
    - Intégrer d'autres Capteurs, pour rendre plus robust les modèles (CO2, lidar, ...)
    - Intégrer les capteurs actuels (car phase d'implémentation juste pour Data flow)

Pipeline complète
Plutot mettre au courrant la motivation du sujet et ce que c'est
Faire un liste de question
Quel plantes on prends
EN combien de temps mes modèles devienne stable
treshold model est considéré comme une modèle et pas un data preprocessing
Pas dispo en juillet mais peut travailler pendant l'été
