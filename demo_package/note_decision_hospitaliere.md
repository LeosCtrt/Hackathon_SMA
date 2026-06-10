# Note de décision hospitalière — HDJ Agent
## CHU Guyane · Endocrinologie-Diabétologie

**Date d'analyse :** 09 juin 2026 · **Version :** 2.0
**Outil :** HDJ Agent — Système multi-agents d'aide à la décision capacitaire et organisationnelle
**Statut :** Prototype d'aide à la décision — validation médicale, DIM/PMSI et gouvernance hospitalière requises

---

## 1. Résumé exécutif (5 lignes)

L'activité endocrino-diabétologique du CHU Guyane (2020–2026, 409 séjours, 249 patients identifiés) révèle **46.2% de patients récurrents** avec en moyenne 2.5 venues par patient. L'analyse multi-agents identifie **5 séjours PMSI-validables immédiatement** (scénario prudent) et **33 séjours structurables** après validation DIM (scénario réorganisation), soit un gain potentiel de +28. La simulation what-if confirme que la capacité matérielle actuelle (fauteuil ×2, rétinographe ×1) absorbe ce volume en 5 jours — **le goulot est exclusivement organisationnel et réglementaire**. L'action immédiate recommandée est de mandater le DIM pour valider les cas scénario A et lancer un pilote HDJ bilan annuel diabète.

---

## 2. Décision recommandée

> **Lancer un pilote HDJ Bilan annuel diabète, puis instruire l'élargissement endocrino-métabolique avec le DIM/PMSI.**

**Pourquoi ce parcours en priorité :**
- Volume le plus large identifié (12 cas scénario B)
- Faisabilité opérationnelle maximale (85%) — actes CCAM documentés, durée 60 min
- Aucun investissement matériel requis
- Validation DIM estimable en 4–6 semaines

**Prochaines étapes immédiates :**
1. Présenter ce tableau de bord au CME / COPIL HDJ
2. Mandater le DIM pour croiser les NUM_SEJOUR scénario A avec la facturation réelle
3. Définir le protocole HDJ bilan annuel avec le chef de service
4. Paramétrer le tarif GHS réel CHU Guyane dans l'outil

---

## 3. Données et qualité

| Donnée | Valeur |
|--------|--------|
| Période | 2020–2026 |
| Lignes brutes | 627 |
| Séjours uniques analysés | 409 |
| IPP patients uniques | 249 |
| Patients récurrents | 115 (46.2%) |
| Qualité données | **usable_with_warnings** |

- Colonnes PMSI essentielles présentes (NUM_SEJOUR, CODE_DIAG, LISTE_ACTES_CCAM)
- IPP disponible sur deux périodes — analyse récurrence activée
- Données TYPE_SEJOUR=EXT → simulation organisationnelle à valider DIM/PMSI
- Couverture CCAM partielle (~39%) → les volumes sont volontairement sous-estimés

*Données pseudonymisées — aucun IPP individuel exposé.*

---

## 4. Fragmentation observée

| Indicateur | Valeur |
|-----------|--------|
| Patients uniques (IPP) | 249 |
| Patients récurrents (> 1 venue) | 115 (46.2%) |
| Venues moyennes / patient | 2.52 |
| Maximum venues / patient | 59 |
| Lignes issues de patients récurrents | 493 |

Près d'1 patient sur 2 revient plusieurs fois. Ces retours fragmentés représentent le principal levier de regroupement HDJ.

---

## 5. Scénarios comparés

| Scénario | Volume | Statut |
|----------|--------|--------|
| Prudent — scénario A | 5 séjours | PMSI-validable immédiatement |
| Réorganisation cible — B | 33 séjours | +28 après validation DIM |
| Regroupement récurrents | 115 patients | Potentiel transformation, protocoles à définir |

**Architecture multi-agents :** 5 agents Mesa (Patient, Soignant, Salle, Environnement, Coordinateur) + graphe NetworkX + ordonnancement greedy. Règles CCAM/CIM-10/durées centralisées dans `hdj_metier.yaml`.

---

## 6. Résultats what-if capacité

| Configuration | Planifiés | Non planifiés | Attente moy. | Fauteuil occ. | Goulot |
|--------------|-----------|---------------|-------------|--------------|--------|
| B — 5 jours (baseline) | 33 | 0 | 1.0 j | 73% | Validation organisationnelle / PMSI |
| B — stress 2 jours | 22 | 11 | 0.4 j | 96% | Horizon de planification trop court |
| B — horizon 10 jours | 33 | 0 | 1.0 j | 37% | Validation organisationnelle / PMSI |
| Récurrents — 5 jours | 56 | 59 | 1.9 j | 98% | Fauteuil médicalisé |
| Récurrents — 10 jours | 96 | 19 | 4.0 j | 99% | Fauteuil médicalisé |
| Récurrents — 10j +1 fauteuil | 115 | 0 | 3.2 j | 82% | Validation organisationnelle / PMSI |

**Lecture :** Sur 33 cas B, la capacité absorbe tout en 5 jours. La saturation apparaît avec les 115 patients récurrents — résorbée avec 10 jours d'horizon et +1 fauteuil.

---

## 7. Priorités HDJ recommandées

| Rang | Parcours | Volume | Faisabilité | Prochaine action |
|------|----------|--------|-------------|-----------------|
| 1 | Bilan annuel diabète | 12 cas B | 85% | Pilote immédiat |
| 2 | Bilan endocrino-métabolique | 9 cas B | 70% | Après validation scénario A |
| 3 | ETP diabète / obésité | 4 cas B | 75% | Groupe de travail |
| 4 | Dépistage rétinopathie | 1 cas B | 80% | Couplé au bilan annuel |
| T | Regroupement récurrents | 115 patients | 55% | Levier transversal post-validation |

---

## 8. Impact médico-économique (paramètre indicatif : 420 €/journée)

*Ce tarif est paramétrable — à remplacer par le GHS HDJ validé DIM/PMSI CHU Guyane.*

| Niveau | Volume | Valorisation indicative | Statut |
|--------|--------|------------------------|--------|
| Prudent (A) | 5 journées | ~2,100 € | À valider DIM |
| Opérationnel (B) | 33 journées | ~13,860 € | Validation PMSI requise |
| Transformation | 115 patients | À calculer | Protocoles à définir |

**Valeur non financière :** réduction des déplacements, meilleure coordination, libération créneaux, amélioration expérience patient chronique.

*Ces montants servent à prioriser l'instruction DIM/PMSI, pas à facturer directement.*

---

## 9. Plan d'action par owner

| Action | Owner | Priorité | Délai |
|--------|-------|----------|-------|
| Valider cas scénario A | DIM/PMSI | 1 — Immédiat | 0–4 semaines |
| Lancer pilote bilan annuel diabète | Chef de service + Cadre HDJ | 1 — Immédiat | 4–8 semaines |
| Paramétrer tarif GHS réel | DIM/PMSI | 1 — Immédiat | 1–2 semaines |
| Présenter CME / COPIL HDJ | Direction opérations | 1 — Immédiat | 1–2 semaines |
| Instruire validation 33 cas B | DIM/PMSI | 2 — Court terme | 2–3 mois |
| Constituer groupe travail récurrents | Cadre HDJ + Chef de service | 2 — Court terme | 3–6 mois |
| Module DSI détection récurrences | DSI/Data | 3 — Moyen terme | 6–12 mois |
| Déploiement intranet Streamlit | DSI/Data | 3 — Moyen terme | 6–9 mois |

---

## 10. Limites réglementaires et PMSI

- **TYPE_SEJOUR=EXT** : toutes les données sources sont des consultations externes — aucun GHS HDJ n'est codé dans les données analysées
- **Instruction Gradation DGOS/R1/DSS/1A/2020/52** : règles GHS sans nuitée non implémentées automatiquement → chaque cas B porte le flag `pmsi_validation_required=True`
- **Durées estimées** : issues du YAML métier — chronométrage réel requis avant déploiement
- **Couverture CCAM partielle** : 39% des lignes ont des actes renseignés → sous-estimation volontaire
- **Cet outil n'est pas un logiciel médical certifié** — aide à la décision organisationnelle uniquement

---

## 11. Commandes de reproduction

```bash
pip install -r requirements.txt          # Installation
python demo_coordinateur.py              # Simulation A/B + IPP
python export_dashboard_outputs.py       # Génération 24 outputs
python make_demo_package.py              # Package jury
streamlit run streamlit_app.py           # Interface interactive
```

---

*Généré automatiquement par HDJ Agent v2.0 — CHU Guyane Endocrino-Diabétologie.*
*Outil d'aide à la décision organisationnelle. Validation DIM/PMSI, médicale et gouvernance requises.*
