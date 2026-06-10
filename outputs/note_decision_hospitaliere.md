# Note de décision hospitalière — HDJ Agent
## CHU Guyane — Endocrinologie-Diabétologie

**Date d'analyse :** 09 juin 2026
**Outil :** HDJ Agent — Système multi-agents d'aide à la décision capacitaire
**Statut :** Prototype opérationnel d'aide à la décision — validation médicale et PMSI requise avant mise en œuvre

---

## 1. Résumé exécutif

L'analyse de l'activité endocrino-diabétologique du CHU Guyane (période 2020–2026) révèle
**46.2% de patients récurrents** (115/249 patients uniques), avec en moyenne
2.5 venues par patient et un maximum de 59 venues pour un même patient.

La simulation multi-agents identifie :
- **5 séjours planifiables** dans un scénario PMSI conservateur (scénario A)
- **33 séjours simulables** dans un scénario de réorganisation cible (scénario B)
- **Gain potentiel : +28 séjours** supplémentaires structurables en HDJ

---

## 2. Problème identifié

L'activité endocrino-diabétologique est actuellement dispersée en consultations externes
(TYPE_SEJOUR=EXT). Les données montrent :

- **Fragmentation des parcours** : 493 lignes de données concernent des patients
  déjà venus plusieurs fois, sans structure HDJ pour les regrouper
- **Ressources critiques sous-utilisées** : rétinographe et fauteuil médicalisé
  mobilisés au cas par cas, sans planification coordonnée
- **Coordination insuffisante** : bilans annuels, ETP, tests dynamiques réalisés
  lors de consultations séparées au lieu d'une journée structurée

---

## 3. Données analysées

| Donnée | Valeur |
|--------|--------|
| Période | 2020–2026 |
| Lignes brutes | 627 |
| Séjours uniques analysés | 409 |
| IPP patients uniques | 249 |
| Qualité données | usable_with_warnings |

*Données pseudonymisées — aucun IPP individuel exposé dans cette note.*

---

## 4. Qualité des données

- **Verdict :** `usable_with_warnings`
- Colonnes PMSI essentielles présentes (NUM_SEJOUR, CODE_DIAG, LISTE_ACTES_CCAM)
- IPP disponible sur les deux périodes — analyse récurrence activée
- Données TYPE_SEJOUR=EXT uniquement → simulation organisationnelle à valider DIM/PMSI

---

## 5. Fragmentation observée

| Indicateur | Valeur |
|-----------|--------|
| Patients uniques (IPP) | 249 |
| Patients récurrents (> 1 venue) | 115 (46.2%) |
| Venues moyennes / patient | 2.52 |
| Maximum venues / patient | 59 |
| Lignes issues de patients récurrents | 493 |

**Interprétation :** Près d'1 patient sur 2 revient plusieurs fois. Ces retours répétés
représentent un potentiel de regroupement en HDJ, réduisant les déplacements,
améliorant la coordination soignants et instruisant le potentiel de valorisation avec le DIM/PMSI.

---

## 6. Architecture multi-agents

Le système HDJ Agent simule 5 agents Mesa interconnectés :

1. **Patient Agent** — parcours physique salle à salle
2. **Soignant Agent** — disponibilité et durée d'actes (paramètres YAML)
3. **Salle Agent** — capacité et occupation
4. **Environnement Agent** — horaires, retards, contraintes globales
5. **Coordinateur Agent** — triage organisationnel + ordonnancement scénarios A/B

Les règles métier (codes CCAM, CIM-10, durées, pathways) sont centralisées dans
`core/config/hdj_metier.yaml` — source unique validée par l'équipe médicale.

---

## 7. Scénarios testés

### Scénario A — Garde-fou PMSI (conservateur)
- **5 séjours planifiés** avec référence PMSI solide
- Risque réglementaire minimal
- Applicable immédiatement après validation DIM

### Scénario B — Réorganisation cible
- **33 séjours simulés** (candidats organisationnels)
- **+28 séjours** supplémentaires vs scénario A
- Validation Instruction Gradation DGOS requise

### Scénario Récurrence patients
- **115 patients** avec multiple venues regroupables
- Potentiel de transformation ambulatoire fort

---

## 8. Résultats opérationnels

| Métrique | Scénario A | Scénario B |
|---------|-----------|-----------|
| Séjours planifiés/simulés | 5 | 33 |
| Gain vs référence | — | +28 |
| Rétinographe occupation | 3.3% | 3.3% |
| Fauteuil occupation | 0.0% | 10.0% |
| Délai attente moyen | 0.0 j | 0.0 j |

---

## 9. Priorités HDJ recommandées

1. **Bilan annuel diabète** — fort volume, faible ressource critique, faisabilité élevée
2. **Bilan endocrino-métabolique** — coordination multi-soignants à structurer
3. **ETP diabète/obésité** — valeur patient élevée, groupe de travail à constituer
4. **Regroupement patients récurrents** — impact fragmentation fort, protocole à définir
5. **Dépistage rétinopathie** — volume faible mais ressource critique (rétinographe ×1)

---

## 10. Estimation médico-économique opérationnelle

*Paramètre de référence : forfait journalier HDJ ~420€ — à valider avec DIM/PMSI CHU Guyane.*

| Niveau | Volume | Valorisation estimée | Statut |
|--------|--------|---------------------|--------|
| Prudent (scénario A) | 5 journées | ~2,100€ | À valider DIM |
| Opérationnel (scénario B) | 33 journées | ~13,860€ | Validation PMSI requise |
| Transformation (récurrents) | 115 patients | À calculer | Protocoles à définir |

**Valeur non financière :** moins de déplacements patients, meilleure coordination,
libération créneaux consultation, amélioration expérience chroniques.

---

## 11. Risques et validations nécessaires

| Risque | Action requise | Owner |
|--------|---------------|-------|
| Validation PMSI cas B | Instruction Gradation DGOS | DIM/PMSI |
| Actes CCAM manquants | Vérification données source | DIM |
| Durées estimées | Chronométrage réel | Cadre HDJ |
| Type séjour EXT → HDJ | Protocole de reclassification | DIM + Chef service |
| Ressources soignants | Plan de charge | Direction opérations |

---

## 12. Plan de passage à l'échelle

**Phase 1 (0–3 mois) :** Validation DIM du scénario A, pilote bilan annuel diabète
**Phase 2 (3–9 mois) :** Extension scénario B après validation, protocoles récurrents
**Phase 3 (9–18 mois) :** Déploiement complet, interface temps réel, apprentissage

---

## 13. Commandes pour reproduire l'analyse

```bash
# Installation
pip install -r requirements.txt

# Analyse complète
python demo_coordinateur.py

# Export outputs complets
python export_dashboard_outputs.py

# Interface hospitalière interactive
streamlit run streamlit_app.py
```

---

*Ce document est généré automatiquement par HDJ Agent v1.0.*
*Il constitue un outil d'aide à la décision organisationnelle et capacitaire.*
*Toute décision médicale, PMSI ou réglementaire reste sous la responsabilité des équipes compétentes.*
