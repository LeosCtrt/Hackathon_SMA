## HDJ Agent — Outil hospitalier d'aide à la décision capacitaire et organisationnelle

## Installation
```bash
pip install -r requirements.txt
```

## Lancer l'analyse
```bash
python demo_coordinateur.py           # simulation scénarios A/B + métriques IPP
python export_dashboard_outputs.py    # génère tous les outputs dans outputs/
```

## Lancer l'application hospitalière
```bash
streamlit run streamlit_app.py
```

## Sources
- **Données IPP** : analyse de fragmentation parcours patients (2020–2026)
- **YAML** : règles métier endocrino (CCAM, CIM-10, durées, pathways, ressources)
- **Excel** : modèle de structure hospitalière paramétrable (intégration future)
- **Outputs** : 17 fichiers JSON/CSV + note de décision dans `outputs/`

## Positionnement
Outil opérationnel d'aide à la décision organisationnelle et capacitaire.
Validation médicale, DIM/PMSI et gouvernance hospitalière requises avant mise en œuvre.

---

## HDJ-Agent — Jumeau Numérique pour l'Hôpital de Jour (Endocrinologie)
HDJ-Agent est un prototype de simulateur à base de Systèmes Multi-Agents (SMA) conçu pour modéliser, optimiser et restructurer les flux de patients au sein de l'Hôpital de Jour (HDJ) en Diabétologie et Endocrinologie du CHU de Guyane.

En transformant des données de consultations externes traditionnelles (TYPE_SEJOUR=EXT) en parcours coordonnés, l'application démontre comment une réorganisation logistique appuyée par l'IA peut maximiser l'efficience des ressources hospitalières (fauteuils, examens spécialisés) tout en réduisant les délais d'attente des patients.

#🎯 Enjeux et Vision du Projet
Le système de santé actuel fait face à une saturation des structures d'accueil. L'Hôpital de Jour est une solution d'avenir, mais son pilotage à flux tendus est un défi logistique complexe.

HDJ-Agent résout ce problème à travers deux axes majeurs :

L'Ordonnancement Intelligent : Un agent coordinateur analyse l'historique des données patients (codes CIM-10, actes CCAM) et planifie des parcours optimisés (Scénario B) en rupture avec la rigidité réglementaire actuelle (Scénario A).

La Simulation Spatiale Réelle : Contrairement à un simple outil de planification sur tableur, le projet intègre la topologie physique de l'hôpital sous forme de graphes. Les patients et les soignants se déplacent réellement dans les couloirs et les salles, permettant de détecter les goulots d'étranglement physiques du service.

#🧱 Concepts Clés du Système Multi-Agents (SMA)
L'architecture du projet repose sur la granularité et l'autonomie offertes par le paradigme multi-agents :

Les Agents Patients : Instanciés à partir des données réelles. Chaque patient possède sa propre pathologie (priorisation des profils : Endocrino rare > Diabète T1/T2 > Thyroïde > Obésité) et son propre parcours de soins à accomplir.

Les Agents Soignants (Médecins / Paramédicaux) : Attribués physiquement à des salles lors de l'initialisation du modèle. Ils gèrent leur propre charge de travail, leurs horaires de service et interagissent directement avec les patients arrivant dans leur zone.

L'Agent Coordinateur : Le cerveau organisationnel du modèle. Il orchestre l'affectation des ressources (Fauteuils, Rétinographes) pour fluidifier les entrées et éviter les congestions.

L'Environnement : Un graphe topologique complet de l'HDJ (salles de consultation, hôpital de jour, circulations) où chaque déplacement d'agent est calculé via des algorithmes de plus court chemin.
