# HDJ Agent — Guide de configuration

## CHU Guyane · Endocrinologie-Diabétologie · Cas pilote

---

## Deux modes d'utilisation

HDJ Agent peut être utilisé de deux façons, selon le besoin.

### A. Depuis Streamlit — simulation en session (rapide)

Streamlit permet de configurer une simulation en session, mais ne modifie pas la configuration métier permanente.

**Ce que vous pouvez faire directement depuis l'interface :**

1. Déposer un fichier Excel ou CSV pseudonymisé
2. Mapper les colonnes (automatique ou manuel via menus déroulants)
3. Ajuster les hypothèses de ressources (fauteuils, rétinographe, créneaux) via sliders
4. Lancer l'analyse et consulter les résultats actifs de la session
5. Télécharger la note de décision

**Ce que Streamlit ne fait pas :**
- Le fichier uploadé n'est jamais écrit sur disque — il reste en mémoire de session.
- Le YAML métier (`core/config/hdj_metier.yaml`) n'est jamais modifié depuis l'interface.
- Les fichiers sources ne sont pas modifiés.
- Certaines pages avancées (scénarios, capacité/saturation, impact médico-économique) peuvent afficher les outputs de démonstration si les outputs globaux n'ont pas été régénérés — un bandeau l'indique explicitement.

### B. Par fichiers et YAML — intégration durable

Pour une intégration pérenne dans un autre service ou établissement :

1. Déposer les données pseudonymisées dans `data/`
2. Renseigner les paramètres locaux dans `core/config/hdj_metier.yaml`
3. Régénérer les outputs :
   ```bash
   python export_dashboard_outputs.py
   ```
4. Relancer l'application :
   ```bash
   streamlit run streamlit_app.py
   ```

> **Résumé :** Streamlit = simulation en session. YAML = configuration métier durable.

---

## 1. Architecture de configuration

HDJ Agent repose sur une séparation stricte entre données et règles métier :

| Fichier | Rôle | Modifier ? |
|---------|------|------------|
| `core/config/hdj_metier.yaml` | **Source de vérité métier** : ressources, rôles, parcours, règles PMSI | Oui — c'est ici que tout se configure |
| `HDJ_Agent_modele_donnees.xlsx` | **Contrat de données** : colonnes attendues dans l'export hospitalier | Non — documentaire uniquement |
| `data/Données_Externes_*.xlsx` | Données hospitalières pseudonymisées | Non — données sources |
| `streamlit_app.py` | Interface de visualisation et simulation | Non — ne modifie pas le YAML |

**Règle fondamentale :** L'Excel modèle documente le schéma d'entrée. Le YAML contient toutes les règles métier. Streamlit lit et simule en session ; il ne reconfigure pas.

---

## 2. Prérequis techniques

```bash
# Python 3.10+
pip install -r requirements.txt

# Dépendances principales :
# mesa, networkx, pandas, openpyxl, pyyaml, streamlit, matplotlib
```

**Note sur les ressources :** L'analyse principale, les exports, les scénarios et la note de décision fonctionnent sur CPU standard. Le GPU n'est pas requis pour l'analyse principale. Il peut être utile uniquement pour la génération et l'affichage de la modélisation visuelle du parcours patient selon l'environnement.

---

## 3. Structure du fichier YAML métier

Le fichier `core/config/hdj_metier.yaml` est organisé en sections :

```
roles_soignants          → Définition des rôles (endocrinologue, IDE, ophtalmologue…)
actes_et_taches          → Actes CCAM, durées, ressources requises
ressources_hdj           → Inventaire physique (fauteuils, rétinographes, salles)
contraintes_interactions → Règles d'interaction entre agents (patient, soignant, salle)
contraintes_systeme      → Horaires, durée journée, slots par jour
candidate_pathways       → Parcours HDJ candidats (bilan annuel, ETP, test dynamique…)
codes_diagnostics        → Codes CIM-10 et CCAM par catégorie
configuration_simulation → Paramètres par défaut de la simulation
```

---

## 4. Adapter les ressources HDJ

Dans `ressources_hdj > mvp_ressources_goulot` :

```yaml
ressources_hdj:
  mvp_ressources_goulot:
    fauteuil_medicalise:
      quantite: 2              # ← Modifier selon l'unité
      duree_occupation_min: 30
    retinographe:
      quantite: 1              # ← Modifier selon le plateau technique
      duree_occupation_min: 20
```

Dans `contraintes_systeme > horaires_simulation` :

```yaml
contraintes_systeme:
  horaires_simulation:
    slots_par_jour: 6          # ← Créneaux par jour et par fauteuil
    debut_journee: "08:00"
    fin_journee: "14:00"
```

---

## 5. Adapter les rôles soignants

```yaml
roles_soignants:
  endocrinologue:
    nom_affichage: "Endocrinologue"
    description: "Médecin référent HDJ"
    nombre: 1
  ide:
    nom_affichage: "IDE"
    description: "Infirmier·ère diplômé·e d'état"
    nombre: 2
  # Ajouter un nouveau rôle :
  infirmier_coordination:
    nom_affichage: "Infirmier·ère de coordination"
    description: "Coordination des parcours multi-actes"
    nombre: 1
```

---

## 6. Ajouter un parcours HDJ

Dans la section `candidate_pathways` :

```yaml
candidate_pathways:
  - id: bilan_thyroide          # Identifiant unique (snake_case)
    nom: "Bilan thyroïde"
    duree_minutes: 180           # Durée totale estimée du séjour
    actes_principaux:
      - "JZQH010"               # Codes CCAM principaux
    ressource_critique: fauteuil_medicalise
    eligible_hdj: true
    codes_diag_compatibles:
      - "E00"                   # Codes CIM-10 compatibles
      - "E01"
      - "E02"
      - "E03"
      - "E04"
      - "E05"
      - "E06"
      - "E07"
```

---

## 7. Configurer les codes diagnostics

Dans la section `codes_diagnostics` :

```yaml
codes_diagnostics:
  diabete:
    cim10: ["E10", "E11", "E12", "E13", "E14"]
    label: "Diabète (toutes formes)"
  endocrino:
    cim10: ["E00", "E01", "E02", "E03", "E04", "E05", "E06", "E07",
            "E20", "E21", "E22", "E23", "E24", "E25", "E26", "E27",
            "E65", "E66", "E67", "E68"]
    label: "Pathologies endocriniennes"
```

---

## 8. Schéma de données attendu (contrat d'entrée)

Pour fournir un export hospitalier à analyser, les colonnes suivantes sont attendues :

| Colonne | Obligatoire | Description |
|---------|-------------|-------------|
| `NUM SEJOUR` | Oui | Identifiant unique du séjour |
| `NUM IPP PATIENT` | Recommandé | Identifiant patient pseudonymisé (permet l'analyse de récurrence) |
| `CODE DIAG` | Oui | Diagnostic principal CIM-10 |
| `LISTE ACTES CCAM MVT` | Recommandé | Actes CCAM séparés par ';' |
| `TYPE SEJOUR` | Oui | Type de séjour (EXT, HDJ, MCO…) |
| `DATE ENTREE SEJ` | Recommandé | Date d'entrée (AAAA-MM-JJ) |
| `HEURE ENTREE SEJ` | Optionnel | Heure d'entrée (HH:MM) |
| `HEURE SORTIE SEJ` | Optionnel | Heure de sortie (HH:MM) |
| `CODE ACTE` | Optionnel | Code CCAM principal |
| `SPECIALITE OPERATEUR` | Optionnel | Spécialité médicale |

Les données doivent être pseudonymisées avant tout export. Le fichier `HDJ_Agent_modele_donnees.xlsx` contient le détail complet et un mapping de colonnes pour adapter des en-têtes non standard.

---

## 9. Utiliser Streamlit directement — parcours complet

L'interface Streamlit intègre un parcours utilisateur complet dans la page **Paramétrage hospitalier** :

1. **Ouvrir l'application** :
   ```bash
   streamlit run streamlit_app.py
   ```

2. **Aller dans "Paramétrage hospitalier"** (dernière entrée de la navigation).

3. **Déposer le fichier Excel/CSV pseudonymisé** (section 1) :
   - Format accepté : `.xlsx`, `.xls`, `.csv`
   - Le fichier est lu en mémoire — il n'est jamais écrit sur le disque du serveur.
   - Aperçu des 5 premières lignes affiché automatiquement.

4. **Vérifier ou compléter le mapping** (section 2) :
   - Les colonnes reconnues automatiquement sont listées.
   - Pour les colonnes manquantes, un menu déroulant permet d'associer une colonne locale à chaque champ standard HDJ Agent.
   - Un tableau récapitulatif indique le statut de chaque champ (reconnu / mappé / manquant).

5. **Ajuster les ressources en simulation** (section 3) :
   - Sliders pour fauteuils, rétinographes, créneaux par jour, horizon.
   - Ces valeurs ne modifient jamais le YAML — elles restent en session.

6. **Cliquer sur "Lancer l'analyse HDJ Agent"** (section 4) :
   - L'application vérifie que les colonnes obligatoires sont disponibles.
   - Elle construit un dataframe standardisé en mémoire à partir du mapping.
   - Elle calcule : nombre de séjours, patients, diagnostics, taux CCAM, durée moyenne, top diagnostics.
   - Le résumé est stocké en session et affiché en section 5.

7. **Générer les exports globaux** (optionnel) :
   - Le bouton "Générer / actualiser les exports de démonstration" relance `export_dashboard_outputs.py`.
   - Les fichiers JSON/MD sont mis à jour dans `outputs/`.

8. **Consulter les résultats** (section 5) :
   - Métriques clés de l'analyse session.
   - Tableau des exports disponibles dans `outputs/`.
   - Téléchargement de la note de décision en un clic.

> **Rappel :** l'analyse du fichier uploadé reste locale à la session. Les exports dans `outputs/` sont générés indépendamment à partir des données sources et du YAML.

---

## 10. Adapter à un autre établissement

1. **Préparer les données** : exporter depuis le DIM un fichier pseudonymisé conforme au schéma ci-dessus. Utiliser l'onglet `Mapping_Colonnes` de l'Excel modèle pour adapter les noms de colonnes si nécessaire.

2. **Configurer le YAML** : adapter les sections `roles_soignants`, `ressources_hdj`, et `candidate_pathways` à l'organisation de votre unité HDJ.

3. **Vérifier les codes** : mettre à jour `codes_diagnostics` avec les codes CIM-10 de la spécialité concernée.

4. **Générer les outputs** :
   ```bash
   python export_dashboard_outputs.py
   ```

5. **Lancer l'interface** :
   ```bash
   streamlit run streamlit_app.py
   ```

6. **Valider avec le DIM/PMSI** : toute décision de création ou de valorisation d'activité HDJ requiert une validation DIM, médicale et de gouvernance.

---

## 11. Données actives dans l'application

Après upload, mapping et lancement de l'analyse dans la page **Paramétrage hospitalier**, les résultats du fichier uploadé deviennent les **résultats actifs de la session Streamlit** :

- Les pages **Synthèse exécutive**, **Qualité des données** et **Fragmentation** affichent les métriques calculées sur le fichier uploadé.
- Les pages **Scénarios HDJ**, **Capacité / Saturation**, **Priorisation HDJ**, **Impact médico-économique** et **Note de décision** continuent d'afficher les outputs de démonstration, avec un bandeau explicite.
- Un bouton **"Revenir aux données de démonstration"** apparaît dans la sidebar pour réinitialiser la session.
- Les fichiers originaux ne sont pas modifiés.
- Le YAML (`core/config/hdj_metier.yaml`) n'est jamais modifié depuis l'interface.
- Le fichier uploadé reste en mémoire de session — il n'est jamais écrit sur disque.

---

## 12. Limites et précautions

- **Données sources** : les analyses portent sur des données pseudonymisées. Aucun GHS HDJ n'est codé dans les sources — le potentiel de valorisation est une estimation à instruire avec le DIM.
- **Durées des parcours** : issues du YAML métier. À valider avec l'équipe soignante avant toute planification.
- **Outil d'aide à la décision** : HDJ Agent est un outil de simulation organisationnelle. Il n'est pas un logiciel médical certifié (MDR/CE). Il ne remplace pas le DIM/PMSI ni la décision médicale.
- **Validation requise** : validation DIM/PMSI, médicale et de gouvernance avant toute mise en œuvre.
- **Référentiel réglementaire** : Instruction DGOS/R1/DSS/1A/2020/52 et référentiel PMSI MCO 2026 (en vigueur au 01/03/2026).
