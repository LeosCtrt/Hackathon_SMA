# HDJ Agent — Jumeau numérique organisationnel pour les hôpitaux de jour

> **HDJ Agent transforme des données hospitalières pseudonymisées en scénarios de décision pour aider à structurer les hôpitaux de jour.**

---

## Positionnement

HDJ Agent n'est pas un dashboard. C'est un **outil de gouvernance hospitalière** et un **jumeau numérique organisationnel** de l'hôpital de jour.

Il croise six dimensions en même temps :

| Dimension | Ce que HDJ Agent modélise |
|---|---|
| Parcours patient | Venues, actes, profil diagnostique (CIM-10 / CCAM) |
| Médical & paramédical | Agents soignants, rôles, charges, horaires |
| Ressources physiques | Fauteuils, rétinographe, salles, créneaux |
| Capacité & saturation | Simulation goulots, taux d'occupation, flux |
| Contraintes DIM / PMSI | Éligibilité HDJ, valorisation indicative |
| Aide à la décision | Comparaison scénarios, priorisation, note téléchargeable |

**Cas pilote :** HDJ endocrinologie-diabétologie au CHU Guyane.
L'outil est conçu pour être adapté à d'autres services et établissements.

L'outil identifie un **potentiel organisationnel** à instruire et valider avec l'équipe médicale, le DIM et la gouvernance hospitalière. Il ne remplace pas le DIM/PMSI ni la décision médicale.

---

## Ce que nous avons développé

- **Moteur de simulation multi-agent (SMA)** : agents patients, agents soignants, agent coordinateur / ordonnanceur, environnement topologique.
- **Règles d'éligibilité HDJ** : critères diagnostics (CIM-10), actes (CCAM), profils patients.
- **Analyse de qualité des données** : complétude, cohérence, couverture des champs critiques.
- **Analyse de fragmentation des parcours patients** : détection des parcours éclatés et des profils récurrents.
- **Simulation capacité / saturation** : modélisation des goulots, taux d'occupation ressources.
- **Comparaison scénarios A / B** : organisation prudente vs réorganisation cible simulée.
- **Priorisation des parcours HDJ** : classement par profil, complexité et faisabilité.
- **Estimation médico-économique indicative** : potentiel de valorisation à valider avec DIM/PMSI.
- **Note de décision téléchargeable** : synthèse de la simulation, prête pour présentation.
- **Interface Streamlit complète** : 11 pages, usage direct depuis l'interface sans ligne de commande.
- **Interface Lovable** : restitution exécutive pour jury / décideurs.
- **Modélisation visuelle du parcours patient** : animation des déplacements dans l'HDJ.

---

## Deux interfaces complémentaires

### Interface Lovable — restitution exécutive

**URL :** [https://hdj-equipe5.lovable.app](https://hdj-equipe5.lovable.app)

Vitrine exécutive du projet : vision produit, grands scénarios organisationnels, impacts et messages clés.
Conçue pour la restitution au jury, aux décideurs et à la direction hospitalière.

### Interface Streamlit — moteur détaillé

```bash
streamlit run streamlit_app.py
```

Démonstration complète du moteur. Deux usages possibles :

**A. Utilisation directe depuis l'interface (sans ligne de commande)**

Streamlit permet d'utiliser HDJ Agent directement depuis l'interface pour tester un fichier, mapper les colonnes, ajuster des hypothèses et lancer une analyse en session.

1. Déposer un fichier Excel/CSV pseudonymisé
2. Mapper les colonnes (reconnaissance automatique + menu déroulant)
3. Ajuster les hypothèses de ressources via sliders
4. Lancer l'analyse — résultats actifs dans la session
5. Télécharger la note de décision

> Le fichier uploadé reste en mémoire de session. Il n'est jamais écrit sur disque. Le YAML métier n'est pas modifié.

**B. Exploitation des outputs de démonstration**

Les pages avancées (scénarios, capacité/saturation, impact médico-économique) affichent les outputs générés par `export_dashboard_outputs.py`. Si ces outputs n'ont pas été régénérés, les données de démonstration sont utilisées avec un bandeau explicite.

**Pages disponibles :** synthèse exécutive · qualité des données · fragmentation des parcours · scénarios HDJ · simulateur what-if · capacité / saturation · priorisation HDJ · impact médico-économique · note de décision · paramétrage hospitalier · modélisation visuelle du parcours patient.

---

## Installation et lancement

### 1. Installer les dépendances

```bash
pip install -r requirements.txt
```

### 2. Lancer le moteur de simulation

```bash
python demo_coordinateur.py
```

Lance le moteur coordinateur : simulation scénarios A et B, métriques patients et parcours.

### 3. Générer les outputs

```bash
python export_dashboard_outputs.py
```

Génère les fichiers JSON/CSV/MD dans `outputs/` — utilisés par Streamlit pour les pages avancées.

### 4. Lancer l'interface Streamlit

```bash
streamlit run streamlit_app.py
```

### 5. Interface Lovable

Accessible directement via URL : [https://hdj-equipe5.lovable.app](https://hdj-equipe5.lovable.app) — aucune installation requise.

---

## Architecture multi-agent

HDJ Agent repose sur un système multi-agents (SMA) qui simule le fonctionnement réel de l'HDJ :

- **Agents patients** : profil diagnostique, venues, parcours de soins individuel, priorisation.
- **Agents soignants** : médecins et paramédicaux, affectés à des salles, gérant charge et horaires.
- **Environnement topologique** : graphe de l'HDJ (salles, couloirs, circulations) — les agents se déplacent réellement, les goulots physiques sont détectés.
- **Ressources critiques** : fauteuils médicalisés, rétinographe — dimensionnement et saturation modélisés.
- **Agent coordinateur** : orchestration de l'affectation des ressources, arbitrage des conflits, ordonnancement.
- **Règles métier** : éligibilité HDJ, scénarios organisationnels, garde-fous réglementaires.

---

## Fichiers importants

| Fichier / Répertoire | Rôle |
|---|---|
| `streamlit_app.py` | Application Streamlit — interface hospitalière complète |
| `demo_coordinateur.py` | Moteur coordinateur — scénarios A et B |
| `export_dashboard_outputs.py` | Génération des outputs JSON/CSV/MD |
| `core/config/hdj_metier.yaml` | Source de vérité métier (ressources, rôles, parcours, règles) |
| `HDJ_Agent_modele_donnees.xlsx` | Contrat de données : colonnes attendues et mapping |
| `outputs/` | Fichiers de restitution générés |
| `demo_package/` | Package de démonstration autonome |
| `docs/CONFIGURATION_GUIDE.md` | Guide complet de configuration |

---

## Adaptation à un autre hôpital

Le moteur HDJ Agent reste le même ; seule la configuration change.

**Mode session (rapide) :** charger un fichier, mapper les colonnes et ajuster les hypothèses directement dans la page Paramétrage hospitalier de Streamlit. Aucune modification des fichiers sources.

**Mode intégration durable :**

1. **Données** — fournir un export pseudonymisé conforme au contrat de données (`HDJ_Agent_modele_donnees.xlsx`). Colonnes obligatoires : `NUM SEJOUR`, `CODE DIAG`, `TYPE SEJOUR`. Mapping disponible dans l'onglet `Mapping_Colonnes`.

2. **YAML métier** (`core/config/hdj_metier.yaml`) — renseigner les paramètres locaux : nombre de fauteuils, équipements, rôles soignants, horaires, durées, codes diagnostics.

3. **Régénérer et relancer** :
   ```bash
   python export_dashboard_outputs.py
   streamlit run streamlit_app.py
   ```

> Streamlit permet la simulation en session ; le YAML sert à fixer la configuration métier durable.

Guide complet : [`docs/CONFIGURATION_GUIDE.md`](docs/CONFIGURATION_GUIDE.md)

---

## Note sur les ressources système

L'analyse principale, les exports, les scénarios, la simulation et la note de décision fonctionnent sur CPU standard.

Le GPU n'est pas requis pour l'analyse principale. Il peut être utile uniquement pour la génération et l'affichage de la modélisation visuelle du parcours patient selon l'environnement.

---

## Limites et garde-fous

- Le scénario B est une **simulation organisationnelle**, pas une décision automatique.
- Toute mise en œuvre nécessite une **validation médicale** et une **validation DIM/PMSI**.
- L'impact médico-économique affiché est **indicatif** ; il doit être instruit et validé avec le DIM et la gouvernance.
- L'outil **ne remplace pas** le DIM/PMSI ni la décision médicale. Ce n'est pas un logiciel médical certifié.
- Les données utilisées doivent être **pseudonymisées ou anonymisées** avant tout traitement.
- La qualité des résultats dépend directement de la qualité des données d'entrée.
