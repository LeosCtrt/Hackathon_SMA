# HDJ Agent — Aide à la décision pour la gouvernance des hôpitaux de jour

## Résumé

HDJ Agent est un outil hospitalier d'aide à la décision capacitaire et organisationnelle pour les hôpitaux de jour.
Il modélise les parcours patients, les soignants, les salles, les ressources critiques et les contraintes pour simuler des scénarios d'organisation : c'est un **jumeau numérique organisationnel** de l'hôpital de jour.

Cas pilote : HDJ endocrinologie-diabétologie au CHU Guyane — mais le projet est conçu pour être adapté à d'autres services et établissements.

L'outil identifie un **potentiel organisationnel** à instruire et à valider avec l'équipe médicale, le DIM et la gouvernance hospitalière. Il ne remplace pas le DIM/PMSI ni la décision médicale.

Deux interfaces ont été développées : une restitution exécutive (Lovable) et un moteur détaillé (Streamlit).

---

## Deux interfaces développées

### 1. Interface Lovable — restitution exécutive

URL : [https://hdj-equipe5.lovable.app](https://hdj-equipe5.lovable.app)

Rôle :
- vision produit et positionnement de l'outil ;
- restitution claire pour les décideurs ;
- présentation des grands scénarios organisationnels ;
- impact organisationnel et synthèse décisionnelle.

### 2. Interface Streamlit — moteur détaillé

```bash
streamlit run streamlit_app.py
```

Rôle :
- démonstration complète du moteur de simulation ;
- exploration des données et des résultats ;
- pages disponibles : synthèse exécutive, qualité des données, fragmentation des parcours, scénarios HDJ, simulateur what-if, capacité/saturation, priorisation HDJ, impact médico-économique, note de décision téléchargeable, paramétrage hospitalier, modélisation visuelle du parcours patient.

---

## Installation

```bash
pip install -r requirements.txt
```

---

## Lancer l'analyse

```bash
python demo_coordinateur.py
python export_dashboard_outputs.py
```

- `demo_coordinateur.py` : lance la simulation scénarios A/B et calcule les métriques patients et parcours.
- `export_dashboard_outputs.py` : génère les fichiers JSON/CSV/MD dans `outputs/` pour l'interface et la restitution.

---

## Lancer l'application Streamlit

```bash
streamlit run streamlit_app.py
```

---

## Fonctionnalités principales

- Analyse de qualité des données d'entrée.
- Détection de la fragmentation des parcours patients.
- Comparaison scénario A (organisation prudente) vs scénario B (réorganisation cible simulée).
- Simulation capacité/saturation de l'HDJ.
- Priorisation des parcours HDJ par profil patient.
- Estimation médico-économique indicative (à valider avec DIM/PMSI).
- Note de décision téléchargeable.
- Paramétrage hospitalier configurable.
- Modélisation visuelle du parcours patient dans l'HDJ.

---

## Architecture multi-agent

HDJ Agent repose sur un système multi-agents (SMA) :

- **Agents patients** : chaque patient est modélisé avec son profil, ses venues et son parcours de soins.
- **Agents soignants** : médecins et paramédicaux, affectés à des salles, gérant leur propre charge et leurs horaires.
- **Salles et environnement** : graphe topologique de l'HDJ permettant de simuler les déplacements réels et de détecter les goulots d'étranglement.
- **Ressources critiques** : fauteuils, rétinographe — dimensionnement et saturation modélisés.
- **Agent coordinateur** : orchestration de l'affectation des ressources et arbitrage des conflits.
- **Règles métier** : éligibilité HDJ, scénarios organisationnels, garde-fous réglementaires.

---

## Sources et fichiers importants

| Fichier / Répertoire | Rôle |
|---|---|
| `streamlit_app.py` | Application hospitalière Streamlit |
| `export_dashboard_outputs.py` | Génération des fichiers de restitution |
| `demo_coordinateur.py` | Démonstration coordinateur / scénarios A et B |
| `core/config/hdj_metier.yaml` | Paramètres métier de l'hôpital (ressources, rôles, parcours, règles) |
| `HDJ_Agent_modele_donnees.xlsx` | Modèle de données : colonnes attendues et mapping |
| `outputs/` | Fichiers JSON/CSV/MD générés pour la restitution |
| `demo_package/` | Package de démonstration autonome |
| `docs/CONFIGURATION_GUIDE.md` | Guide complet de configuration |

---

## Adaptation à un autre hôpital

Chaque hôpital a ses propres fichiers et sa propre organisation. HDJ Agent peut prendre des données Excel ou CSV, les remettre dans un format commun, puis utiliser les paramètres locaux de l'hôpital. Le moteur reste le même ; seule la configuration change.

Trois niveaux de configuration :

1. **Excel modèle** (`HDJ_Agent_modele_donnees.xlsx`) — contrat de données : colonnes attendues (NUM SEJOUR, CODE DIAG, TYPE SEJOUR, actes CCAM, etc.). Détail dans les onglets `Colonnes_Attendues` et `Mapping_Colonnes`.

2. **Mapping** — correspondance entre les noms de colonnes de l'hôpital source et le format attendu par le moteur. Configurable dans la page Paramétrage hospitalier de Streamlit.

3. **YAML métier** (`core/config/hdj_metier.yaml`) — paramètres locaux : nombre de salles et fauteuils, équipements disponibles, composition de l'équipe soignante, horaires, durées des étapes, codes diagnostics concernés.

Guide complet : [`docs/CONFIGURATION_GUIDE.md`](docs/CONFIGURATION_GUIDE.md)

---

## Limites et garde-fous

- Le scénario B est une **simulation organisationnelle**, pas une décision automatique.
- Toute mise en œuvre nécessite une **validation médicale** et une **validation DIM/PMSI**.
- L'impact médico-économique affiché est **indicatif** ; il doit être instruit et validé avec le DIM et la gouvernance.
- L'outil **ne remplace pas** le DIM/PMSI ni la décision médicale.
- Les données utilisées doivent être **pseudonymisées ou anonymisées** avant tout traitement.
- La qualité des résultats dépend directement de la qualité des données d'entrée.
