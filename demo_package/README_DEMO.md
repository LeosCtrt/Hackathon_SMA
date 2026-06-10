# HDJ Agent — Package de démonstration
## CHU Guyane · Endocrinologie-Diabétologie

**Outil :** Système multi-agents d'aide à la décision pour la création d'Hôpitaux de Jour.
**Statut :** Prototype opérationnel — validation DIM/PMSI requise avant mise en œuvre.

---

## Comment lancer l'application

```bash
# 1. Installation
pip install -r requirements.txt

# 2. Générer les outputs (déjà inclus dans ce package)
python export_dashboard_outputs.py

# 3. Lancer l'interface interactive
streamlit run streamlit_app.py
```

---

## Fichiers clés à ouvrir

| Fichier | Description |
|---------|-------------|
| `note_decision_hospitaliere.md` | Note direction complète — résumé exécutif, what-if, plan d'action |
| `kpi_summary.json` | KPIs scénarios A/B + IPP récurrents |
| `what_if_capacity_results.json` | 8 configurations what-if — saturation, attente, occupation |
| `daily_schedule_example.json` | Planning journalier agrégé (sans IPP) |
| `pathway_prioritization.json` | 6 parcours HDJ prioritaires + levier transversal |
| `operational_action_plan.json` | Plan d'action par owner (DIM, Chef service, Cadre HDJ…) |
| `decision_explainability.json` | Explicabilité décisionnelle par parcours |
| `subject_alignment.json` | Couverture 18 objectifs PDF — 17/18 complets |
| `medico_economic_estimates.json` | Estimation médico-éco 3 niveaux (paramétrable) |

---

## Scénario de démonstration 3 minutes

### Minute 1 — Données et fragmentation
1. Ouvrir **Streamlit → Qualité des données** : verdict `usable_with_warnings`, 4 avertissements pros
2. Aller sur **Fragmentation IPP** : 46.2% patients récurrents, 493 lignes fragmentées
3. Message : *"Près d'1 patient sur 2 revient plusieurs fois — sans HDJ pour les regrouper."*

### Minute 2 — Simulation et capacité
1. Aller sur **Scénarios HDJ** : scénario A=5 (statu quo), B=33 (réorganisation), +28
2. Aller sur **Simulateur what-if** : déplacer le slider horizon → 2 jours → saturation visible
3. Augmenter les patients (récurrents, 115) → fauteuil sature
4. Message : *"Sur 33 cas, tout rentre. Sur 115 récurrents, on voit le vrai goulot matériel."*

### Minute 3 — Décision et impact
1. Aller sur **Priorisation HDJ** : 6 parcours + levier récurrents
2. Aller sur **Impact médico-économique** : paramétrer le tarif → recalcul dynamique
3. Ouvrir **Note de décision** → télécharger
4. Message : *"La décision recommandée : pilote HDJ bilan annuel diabète. Validation DIM en 4–6 semaines."*

---

## Limites

- Données TYPE_SEJOUR=EXT — aucun GHS HDJ codé dans les sources
- Durées issues du YAML métier — à valider avec l'équipe soignante
- Outil d'aide à la décision organisationnelle — pas un logiciel médical certifié
- Validation DIM/PMSI, médicale et gouvernance requises avant toute mise en œuvre
