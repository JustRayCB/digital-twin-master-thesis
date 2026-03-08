import json
import time
import random
from datetime import datetime
import os

# Assurez-vous que ce dossier existe !
DOSSIER_CAPTEURS = "dossier_capteurs"
if not os.path.exists(DOSSIER_CAPTEURS):
    os.makedirs(DOSSIER_CAPTEURS)

print(f"Génération de données dans le dossier '{DOSSIER_CAPTEURS}'...")
print("Appuyez sur Ctrl+C pour arrêter.")

try:
    i = 0
    while True:
        # Données pour un capteur aléatoire
        donnees = {
            "timestamp": datetime.now().isoformat(),
            "id_capteur": f"capteur_{random.choice(['A', 'B'])}",
            "temperature": round(20 + random.uniform(-2.0, 2.0), 2),
        }

        # Nom de fichier unique
        nom_fichier = f"donnees_{i}.json"
        chemin_fichier = os.path.join(DOSSIER_CAPTEURS, nom_fichier)

        with open(chemin_fichier, "w") as f:
            json.dump(donnees, f)

        print(f"Fichier créé : {nom_fichier} avec id {donnees['id_capteur']}")

        i += 1
        time.sleep(3)  # Attendre 3 secondes
except KeyboardInterrupt:
    print("\nGénérateur arrêté.")
