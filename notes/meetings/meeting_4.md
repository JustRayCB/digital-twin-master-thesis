## **1️⃣ Amélioration de l'Architecture et Modularité**

✅ **Vérifier si l'architecture est modulaire et scalable**

- Réfléchir à comment adapter le système à **1 000 capteurs**
- S'assurer que le système est **facilement adaptable** à d'autres problèmes

✅ **Documenter l'architecture**

- Expliquer **d'où vient l'inspiration** du design actuel
- Préciser **les modifications** apportées et pourquoi

✅ **Gérer de grandes quantités de capteurs et données**

- Comment gérer des **débits différents selon les capteurs**
- Identifier **les limites** actuelles et possibles solutions

✅ **Penser à l'ajout d’actionneurs (fermeture de la boucle)**

- Ajouter **arrosage automatique, lumière, ventilation**
- Étudier **l’impact des actions sur la santé de la plante**

---

## **2️⃣ Gestion et Traitement des Données**

✅ **Optimiser le stockage des données**

- **Éviter de tout stocker** → Modélisation pour ne conserver que l’essentiel
- Penser à la **compression des données**
- Utiliser un **modèle offline** pour réduire la dépendance au stockage brut

✅ **Trouver la meilleure façon de stocker et analyser les données**

- Comparer **différents formats et bases de données**
- Penser **à la vitesse d’accès** et **à la scalabilité**

✅ **Analyser la qualité des modèles**

- Comment évaluer et améliorer la **fiabilité des prédictions**
- Comparer **modèles physiques** (équations) vs **modèles basés sur les données**

---

## **3️⃣ Recherche et Amélioration de la Surveillance de la Plante**

✅ **Explorer les capteurs avancés**

- Mesurer la **couleur des feuilles**, la **hauteur**, la **texture**
- Définir **comment analyser la santé de la plante**
- Rechercher **d’autres types de capteurs utiles**

✅ **Travailler avec un botaniste**

- Identifier **quelles plantes sont intéressantes** à étudier
- Par ex. **basilic** car il réagit rapidement à son environnement

✅ **Proposer de nouvelles idées et expérimentations**

- Regarder **s’il existe des modèles physiques de croissance des plantes**
- Expérimenter **différents types d’approches**

---

## **4️⃣ Tâches Pratiques et Documentation**

✅ **Lister toutes les librairies utilisées dans un Google Doc**

- Regrouper les dépendances Python (**Flask, MQTT, DB, IA, etc.**)

✅ **Analyser les difficultés d’implémentation**

- Exemple: Pourquoi ça fonctionne bien avec **10 capteurs mais pas plus** -> Scalabilité
- Identifier **les goulots d’étranglement** et solutions possibles

---

### 🚀 **Prochaines Actions**

1. **Documenter l’architecture et les choix techniques**
2. **Rechercher et tester des techniques de compression et stockage optimisé**
3. **Définir un plan pour intégrer les actionneurs et mesurer leur impact**
4. **Explorer l’ajout de capteurs plus avancés**
5. **Travailler sur l’évaluation des modèles et leur fiabilité**
6. **Lister toutes les dépendances dans un Google Doc**
