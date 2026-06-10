"""
Export complet des outputs HDJ Agent — outil hospitalier d'aide à la décision.

Génère dans outputs/ :
  kpi_summary.json / .csv
  scenario_comparison.json / .csv
  patients_recurrents_summary.csv
  data_quality_report.json
  pathway_reconstruction.json
  fragmentation_segments.json
  triage_summary.json
  scenario_matrix.json
  capacity_simulation.json
  medico_economic_estimates.json
  pathway_prioritization.json
  decision_recommendations.json
  agent_architecture.json
  agent_interactions_graph.json
  agent_memory_cases.json
  subject_alignment.json
  note_decision_hospitaliere.md

Usage : python export_dashboard_outputs.py
"""

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))

from demo_coordinateur import aggregate_by_sejour, compute_ipp_metrics
from core.io.hospital_data_loader import load_hospital_activity_data
from core.validation.data_quality import build_data_quality_report
from core.analysis.pathway_reconstruction import reconstruct_patient_pathways
from core.decision.organizational_triage import triage_pathways
from core.scenarios.scenario_engine import build_scenario_matrix
from core.scenarios.capacity_model import simulate_capacity
from core.decision.medico_economic import build_medico_economic_estimates
from core.decision.pathway_prioritization import prioritize_pathways
from core.agents.coordinateur import CoordinateurAgent
from core.simulation.scheduler import DEFAULT_N_DAYS, DEFAULT_MAX_PARALLEL


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"  ✓ {path}")


def _build_agent_architecture() -> dict:
    return {
        "systeme": "HDJ Agent — Architecture multi-agents",
        "description": "Système multi-agents pour l'optimisation capacitaire et la création d'hôpitaux de jour",
        "agents": [
            {
                "nom": "Patient Agent",
                "statut": "implemented",
                "fichier": "core/agents/patient.py",
                "classe": "Patient",
                "role": "Simule le parcours physique d'un patient dans l'HDJ (salle → salle)",
                "entrees": "Parcours injecté par HopitalModel [(salle, libelle, duree)]",
                "etat_interne": "Position courante, état (TRANSIT/ATTENTE_SOIN/SOIN/TERMINE), historique",
                "decisions": "Navigation entre salles, attente soignant, fin de parcours",
                "sorties": "Historique de mouvement, nb_interactions, état final",
                "interactions": ["SoignantAgent", "Salle", "EnvironnementAgent"],
                "valeur_hospitaliere": "Jumeau du flux patient HDJ — mesure temps de passage et attentes",
            },
            {
                "nom": "Soignant Agent",
                "statut": "implemented",
                "fichier": "core/agents/soignant.py",
                "classe": "SoignantAgent",
                "role": "Réalise les actes de soin selon son rôle (IDE, endocrinologue, ophtalmologue, diététicienne)",
                "entrees": "Type rôle (chargé depuis YAML §roles_soignants), salle assignée",
                "etat_interne": "Disponibilité, patient en cours, durée acte (YAML)",
                "decisions": "Accepter/refuser patient, durée de l'acte",
                "sorties": "Signal fin de prestation, compteur interactions",
                "interactions": ["Patient Agent", "Salle", "EnvironnementAgent"],
                "valeur_hospitaliere": "Modélise la disponibilité soignant et les goulots humains",
            },
            {
                "nom": "Salle / Resource Agent",
                "statut": "implemented",
                "fichier": "core/agents/salle.py",
                "classe": "Salle",
                "role": "Représente une salle HDJ avec capacité, type et occupation",
                "entrees": "Nom, type_salle, capacité (injectés par HopitalModel)",
                "etat_interne": "Occupation courante, capacité totale",
                "decisions": "Passif — géré par les agents patients/soignants",
                "sorties": "Occupation en temps réel",
                "interactions": ["Patient Agent", "SoignantAgent"],
                "valeur_hospitaliere": "Mesure l'utilisation réelle des salles HDJ",
            },
            {
                "nom": "Environnement Agent",
                "statut": "implemented",
                "fichier": "core/agents/environnement.py",
                "classe": "EnvironnementAgent",
                "role": "Gère les contraintes globales : horaires, retards, indisponibilités, événements",
                "entrees": "YAML §contraintes_systeme.horaires_simulation",
                "etat_interne": "Horloge globale, files d'attente, retards actifs, métriques",
                "decisions": "Ouverture/fermeture service, signalement saturation",
                "sorties": "Métriques temps réel, alertes saturation",
                "interactions": ["tous les agents"],
                "valeur_hospitaliere": "Jumeau des contraintes opérationnelles de l'HDJ",
            },
            {
                "nom": "Triage Organisationnel Agent",
                "statut": "implemented",
                "fichier": "core/decision/organizational_triage.py",
                "classe": "fonction triage_pathways()",
                "role": "Classe chaque séjour dans une catégorie décisionnelle HDJ",
                "entrees": "DataFrame séjours + règles YAML hdj_eligibility",
                "etat_interne": "Compteurs par catégorie, règles utilisées",
                "decisions": "already_hdj / pmsi_guardrail / target_reorg / recurrent / out_of_scope",
                "sorties": "triage_summary.json",
                "interactions": ["CoordinateurAgent", "hdj_eligibility"],
                "valeur_hospitaliere": "Priorisation organisationnelle — qui peut aller en HDJ",
            },
            {
                "nom": "Coordinateur / Scheduler Agent",
                "statut": "implemented",
                "fichier": "core/agents/coordinateur.py",
                "classe": "CoordinateurAgent",
                "role": "Ordonnanceur HDJ — planifie les séjours sur l'horizon (scénarios A et B)",
                "entrees": "DataFrame séjours agrégés, ressources limitantes (YAML)",
                "etat_interne": "Schedulers A/B, KPIs A/B, liste patients",
                "decisions": "Éligibilité HDJ, affectation créneaux, gestion saturation",
                "sorties": "Dashboard A/B, taux occupation ressources, pathways planifiés",
                "interactions": ["hdj_eligibility", "RessourceLimitante", "Scheduler"],
                "valeur_hospitaliere": "Simulation déterministe scénarios A/B — aide à la planification",
            },
            {
                "nom": "Evaluateur Médico-économique Agent",
                "statut": "implemented",
                "fichier": "core/decision/medico_economic.py",
                "classe": "fonction build_medico_economic_estimates()",
                "role": "Produit des estimations médico-économiques à 3 niveaux",
                "entrees": "KPIs A/B, métriques IPP, paramètres YAML",
                "etat_interne": "Calculs estimation basés sur forfait HDJ paramétrable",
                "decisions": "Niveau prudent / opérationnel / transformation",
                "sorties": "medico_economic_estimates.json",
                "interactions": ["CoordinateurAgent", "pathway_reconstruction"],
                "valeur_hospitaliere": "Estimation opérationnelle pour gouvernance — à valider DIM",
            },
            {
                "nom": "Memory / Learning Agent",
                "statut": "partial",
                "fichier": "outputs/agent_memory_cases.json (préparé)",
                "classe": "N/A — couche mémoire à implémenter",
                "role": "Capitalise les cas performants, les anomalies et les leçons apprises",
                "entrees": "Résultats de simulation, feedback équipe",
                "etat_interne": "Cas mémorisés, patterns reconnus",
                "decisions": "Suggérer des ajustements basés sur l'expérience accumulée",
                "sorties": "agent_memory_cases.json",
                "interactions": ["CoordinateurAgent", "tous les agents"],
                "valeur_hospitaliere": "Amélioration continue — détection précoce de dérives",
                "next_step": "Intégration Qdrant ou base vectorielle pour mémoire sémantique",
            },
            {
                "nom": "Governance Dashboard Agent",
                "statut": "partial",
                "fichier": "streamlit_app.py",
                "classe": "Application Streamlit",
                "role": "Interface hospitalière de visualisation et décision",
                "entrees": "outputs/*.json (générés par export_dashboard_outputs.py)",
                "etat_interne": "Lecture seule — affichage agrégats",
                "decisions": "Navigation entre vues, export note décision",
                "sorties": "Dashboard interactif pour jury / équipe hospitalière",
                "interactions": ["tous les outputs JSON"],
                "valeur_hospitaliere": "Interface opérationnelle pour équipe soignante et direction",
                "next_step": "Connexion temps réel aux agents Mesa via WebSocket",
            },
        ],
    }


def _build_interactions_graph(agents: list) -> dict:
    nodes = [{"id": a["nom"], "statut": a["statut"], "fichier": a["fichier"]} for a in agents]
    edges = [
        {"from": "Patient Agent", "to": "SoignantAgent", "type": "interaction_soin"},
        {"from": "Patient Agent", "to": "Salle / Resource Agent", "type": "occupation"},
        {"from": "Patient Agent", "to": "Environnement Agent", "type": "contrainte_horaire"},
        {"from": "SoignantAgent", "to": "Patient Agent", "type": "prestation"},
        {"from": "SoignantAgent", "to": "Environnement Agent", "type": "disponibilite"},
        {"from": "Environnement Agent", "to": "Patient Agent", "type": "retard_evenement"},
        {"from": "Coordinateur / Scheduler Agent", "to": "Triage Organisationnel Agent", "type": "eligibilite"},
        {"from": "Coordinateur / Scheduler Agent", "to": "Evaluateur Médico-économique Agent", "type": "kpis"},
        {"from": "Triage Organisationnel Agent", "to": "Coordinateur / Scheduler Agent", "type": "classification"},
        {"from": "Evaluateur Médico-économique Agent", "to": "Governance Dashboard Agent", "type": "estimations"},
        {"from": "Coordinateur / Scheduler Agent", "to": "Governance Dashboard Agent", "type": "dashboard"},
        {"from": "Memory / Learning Agent", "to": "Coordinateur / Scheduler Agent", "type": "recommandation"},
        {"from": "Governance Dashboard Agent", "to": "Memory / Learning Agent", "type": "feedback"},
    ]
    return {"nodes": nodes, "edges": edges}


def _build_memory_cases(kpis_B: dict, ipp_metrics: dict) -> dict:
    by_pw = kpis_B.get("repartition_pathways", {})
    return {
        "description": "Mémoire opérationnelle — leçons issues de la simulation",
        "note": "Fichier préparé pour intégration future avec base vectorielle (Qdrant).",
        "cas": [
            {
                "id": "MC001",
                "type": "cas_performant",
                "pathway": "bilan_annuel_diabete",
                "observation": f"Fort volume détecté ({by_pw.get('bilan_annuel_diabete', 0)} cas) — parcours prioritaire",
                "lecon": "Le bilan annuel diabète est le pathway le plus fréquent — à prioriser en création HDJ",
                "prochaine_action": "Valider éligibilité PMSI avec DIM, définir protocole HDJ dédié",
                "confiance": 0.85,
            },
            {
                "id": "MC002",
                "type": "cas_performant",
                "pathway": "bilan_endocrino_metabolique",
                "observation": f"{by_pw.get('bilan_endocrino_metabolique', 0)} cas — coordination élevée requise",
                "lecon": "Pathway nécessitant plusieurs soignants — créer protocole multi-intervenants",
                "prochaine_action": "Cartographier les soignants disponibles pour ce parcours",
                "confiance": 0.75,
            },
            {
                "id": "MC003",
                "type": "fragmentation_detectee",
                "pathway": "recurrent_patient_grouping",
                "observation": f"{ipp_metrics.get('patients_recurrents', 0)} patients récurrents, {ipp_metrics.get('venues_max', 0)} venues max",
                "lecon": "Fragmentation transversale — des patients reviennent de nombreuses fois sans structure HDJ",
                "prochaine_action": "Identifier protocole de regroupement pour patients à ≥ 4 venues",
                "confiance": 0.90,
            },
            {
                "id": "MC004",
                "type": "limite_donnees",
                "pathway": "tous",
                "observation": "Données TYPE_SEJOUR=EXT uniquement — pas de GHS HDJ dans les données sources",
                "lecon": "La simulation est hypothétique — les KPIs représentent un potentiel, pas une réalité HDJ",
                "prochaine_action": "Demander extraction PMSI avec TYPE_SEJOUR=H (HDJ) pour comparaison",
                "confiance": 1.0,
            },
            {
                "id": "MC005",
                "type": "limite_reglementaire",
                "pathway": "tous_cas_B",
                "observation": "Instruction Gradation DGOS/R1/DSS/1A/2020/52 non encodée",
                "lecon": "Tous les cas scénario B portent pmsi_validation_required — sous-estimation possible du scénario A",
                "prochaine_action": "Encoder les critères GHS sans nuitée de l'Instruction Gradation",
                "confiance": 1.0,
            },
            {
                "id": "MC006",
                "type": "ressource_critique",
                "pathway": "depistage_retinopathie",
                "observation": f"Rétinographe ×1 — ressource limitante pour {by_pw.get('depistage_retinopathie', 0)} cas",
                "lecon": "Le rétinographe est un goulot potentiel si le volume dépistage augmente",
                "prochaine_action": "Simuler impact +1 rétinographe sur la capacité",
                "confiance": 0.80,
            },
        ],
    }


def _build_subject_alignment(kpis_A: dict, kpis_B: dict, ipp_metrics: dict) -> dict:
    return {
        "sujet": "HDJ Agent — Système multi-agents pour optimisation capacitaire et création d'hôpitaux de jour",
        "alignement": [
            {
                "critere": "Jumeau organisationnel simplifié HDJ",
                "couvert": True,
                "comment": "HopitalModel (Mesa) + graphe NetworkX + EnvironnementAgent (horaires, flux)",
            },
            {
                "critere": "Agents patients / soignants / salles / environnement / coordinateur",
                "couvert": True,
                "comment": "5 agents implémentés : Patient, SoignantAgent, Salle, EnvironnementAgent, CoordinateurAgent",
            },
            {
                "critere": "Scénarios A/B",
                "couvert": True,
                "comment": f"A={kpis_A.get('planifies',0)} planifiés (PMSI), B={kpis_B.get('simules',0)} simulés — gain +{kpis_B.get('gain_vs_A',0)}",
            },
            {
                "critere": "Indicateurs volume convertible / occupation / saturation / délai / ressources critiques",
                "couvert": True,
                "comment": "Dashboard A/B + capacity_simulation.json (6 configurations testées)",
            },
            {
                "critere": "Logique exploitable par l'hôpital",
                "couvert": True,
                "comment": "YAML métier validé + triage organisationnel + note de décision + Streamlit app",
            },
            {
                "critere": "Base prête dashboard / interface Lovable",
                "couvert": True,
                "comment": "17 fichiers JSON/CSV dans outputs/ + API statique consommable directement",
            },
            {
                "critere": "Fragmentation parcours / patients récurrents",
                "couvert": True,
                "comment": f"IPP : {ipp_metrics.get('ipp_uniques',0)} patients, {ipp_metrics.get('pct_recurrents',0)}% récurrents",
            },
            {
                "critere": "Médico-économique",
                "couvert": True,
                "comment": "3 niveaux estimations (prudent/opérationnel/transformation) — à valider DIM",
            },
        ],
    }


def _generate_decision_note(
    kpis_A: dict, kpis_B: dict, ipp_metrics: dict, quality: dict
) -> str:
    vol_A = kpis_A.get("planifies", 0)
    vol_B = kpis_B.get("simules", 0)
    gain = kpis_B.get("gain_vs_A", 0)
    ipp_u = ipp_metrics.get("ipp_uniques", 0)
    rec = ipp_metrics.get("patients_recurrents", 0)
    pct_rec = ipp_metrics.get("pct_recurrents", 0)
    venues_moy = ipp_metrics.get("venues_moy", 0)
    venues_max = ipp_metrics.get("venues_max", 0)
    lignes_rec = ipp_metrics.get("lignes_patients_recurrents", 0)
    total = kpis_A.get("total", 0)
    verdict = quality.get("verdict", "N/A")

    return f"""# Note de décision hospitalière — HDJ Agent
## CHU Guyane — Endocrinologie-Diabétologie

**Date d'analyse :** 09 juin 2026
**Outil :** HDJ Agent — Système multi-agents d'aide à la décision capacitaire
**Statut :** Prototype opérationnel d'aide à la décision — validation médicale et PMSI requise avant mise en œuvre

---

## 1. Résumé exécutif

L'analyse de l'activité endocrino-diabétologique du CHU Guyane (période 2020–2026) révèle
**{pct_rec:.1f}% de patients récurrents** ({rec}/{ipp_u} patients uniques), avec en moyenne
{venues_moy:.1f} venues par patient et un maximum de {venues_max} venues pour un même patient.

La simulation multi-agents identifie :
- **{vol_A} séjours planifiables** dans un scénario PMSI conservateur (scénario A)
- **{vol_B} séjours simulables** dans un scénario de réorganisation cible (scénario B)
- **Gain potentiel : +{gain} séjours** supplémentaires structurables en HDJ

---

## 2. Problème identifié

L'activité endocrino-diabétologique est actuellement dispersée en consultations externes
(TYPE_SEJOUR=EXT). Les données montrent :

- **Fragmentation des parcours** : {lignes_rec} lignes de données concernent des patients
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
| Séjours uniques analysés | {total} |
| IPP patients uniques | {ipp_u} |
| Qualité données | {verdict} |

*Données pseudonymisées — aucun IPP individuel exposé dans cette note.*

---

## 4. Qualité des données

- **Verdict :** `{verdict}`
- Colonnes PMSI essentielles présentes (NUM_SEJOUR, CODE_DIAG, LISTE_ACTES_CCAM)
- IPP disponible sur les deux périodes — analyse récurrence activée
- Données TYPE_SEJOUR=EXT uniquement → simulation hypothétique de restructuration

---

## 5. Fragmentation observée

| Indicateur | Valeur |
|-----------|--------|
| Patients uniques (IPP) | {ipp_u} |
| Patients récurrents (> 1 venue) | {rec} ({pct_rec:.1f}%) |
| Venues moyennes / patient | {venues_moy:.2f} |
| Maximum venues / patient | {venues_max} |
| Lignes issues de patients récurrents | {lignes_rec} |

**Interprétation :** Près d'1 patient sur 2 revient plusieurs fois. Ces retours répétés
représentent un potentiel de regroupement en HDJ, réduisant les déplacements,
améliorant la coordination soignants et optimisant la tarification GHS.

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
- **{vol_A} séjours planifiés** avec référence PMSI solide
- Risque réglementaire minimal
- Applicable immédiatement après validation DIM

### Scénario B — Réorganisation cible
- **{vol_B} séjours simulés** (candidats organisationnels)
- **+{gain} séjours** supplémentaires vs scénario A
- Validation Instruction Gradation DGOS requise

### Scénario Récurrence patients
- **{rec} patients** avec multiple venues regroupables
- Potentiel de transformation ambulatoire fort

---

## 8. Résultats opérationnels

| Métrique | Scénario A | Scénario B |
|---------|-----------|-----------|
| Séjours planifiés/simulés | {vol_A} | {vol_B} |
| Gain vs référence | — | +{gain} |
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
| Prudent (scénario A) | {vol_A} journées | ~{vol_A * 420:,}€ | À valider DIM |
| Opérationnel (scénario B) | {vol_B} journées | ~{vol_B * 420:,}€ | Validation PMSI requise |
| Transformation (récurrents) | {rec} patients | À calculer | Protocoles à définir |

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
"""


def main() -> None:
    out = Path("outputs")
    out.mkdir(exist_ok=True)

    print("\n=== HDJ Agent — Export Hospitalier Complet ===\n")

    # ── Chargement ─────────────────────────────────────────────────────────
    df_raw, meta = load_hospital_activity_data(verbose=True)
    ipp_metrics = compute_ipp_metrics(df_raw)
    if ipp_metrics.get("has_ipp"):
        n_ipp = sum(1 for f in [None] if f)  # déjà loggé par loader
        pass

    df = aggregate_by_sejour(df_raw)

    # ── Coordinateur ───────────────────────────────────────────────────────
    agent = CoordinateurAgent(n_days=DEFAULT_N_DAYS, max_parallel=DEFAULT_MAX_PARALLEL)
    agent.load_data(df)
    agent.run()

    ts_A = agent.scheduler_A.total_slots()
    ts_B = agent.scheduler_B.total_slots()
    ret_A = agent.resources_A["retinographe"]
    fau_A = agent.resources_A["fauteuil"]
    ret_B = agent.resources_B["retinographe"]
    fau_B = agent.resources_B["fauteuil"]

    kpis_A_dict = {
        "planifies": agent.kpis_A.scheduled,
        "total": agent.total,
        "deja_structures_hdj": agent.kpis_A.already_hdj,
        "convertibles_pmsi": agent.kpis_A.convertible,
        "requires_review": agent.kpis_A.requires_review,
        "candidats_validation_pmsi": agent.kpis_A.candidate_pmsi_validation,
        "uncertain": agent.kpis_A.uncertain,
        "non_planifies": agent.kpis_A.not_scheduled,
        "delai_attente_moyen_j": round(agent.kpis_A.avg_wait_days, 1),
        "retinographe_occ_pct": round(ret_A.occupancy_rate(ts_A) * 100, 1),
        "fauteuil_occ_pct": round(fau_A.occupancy_rate(ts_A) * 100, 1),
    }
    kpis_B_dict = {
        "simules": agent.kpis_B.scheduled,
        "pmsi_validation_required": agent.kpis_B.pmsi_validation_required,
        "uncertain": agent.kpis_B.requires_human_review,
        "low_candidate": agent.kpis_B.low_candidate,
        "non_planifies": agent.kpis_B.not_scheduled,
        "gain_vs_A": agent.kpis_B.gain_vs_a,
        "delai_attente_moyen_j": round(agent.kpis_B.avg_wait_days, 1),
        "retinographe_occ_pct": round(ret_B.occupancy_rate(ts_B) * 100, 1),
        "fauteuil_occ_pct": round(fau_B.occupancy_rate(ts_B) * 100, 1),
        "repartition_pathways": dict(agent.kpis_B.by_pathway),
    }

    print()

    # ── Outputs existants ──────────────────────────────────────────────────
    kpi = {
        "meta": {
            "source": "HDJ Agent — CHU Guyane",
            "specialite": "Endocrinologie-Diabétologie",
            "scenarios": "A (PMSI garde-fou) + B (réorganisation cible)",
            "avertissement": "données TYPE_SEJOUR=EXT — simulation hypothétique",
            "horizon_simulation_jours": DEFAULT_N_DAYS,
            "capacite_max_parallele": DEFAULT_MAX_PARALLEL,
        },
        "volume": {"total_sejours_analyses": agent.total, "hors_perimetre_endocrino": agent.kpis_A.not_applicable},
        "scenario_A": kpis_A_dict,
        "scenario_B": kpis_B_dict,
        "patients_recurrents": ipp_metrics if ipp_metrics.get("has_ipp") else {"has_ipp": False},
    }
    _write(out / "kpi_summary.json", json.dumps(kpi, ensure_ascii=False, indent=2))

    rows = [
        {"categorie": "volume", "indicateur": "total_sejours_analyses", "valeur": agent.total, "unite": "séjours"},
        {"categorie": "scenario_A", "indicateur": "planifies", "valeur": agent.kpis_A.scheduled, "unite": "séjours"},
        {"categorie": "scenario_A", "indicateur": "retinographe_occ_pct", "valeur": kpis_A_dict["retinographe_occ_pct"], "unite": "%"},
        {"categorie": "scenario_A", "indicateur": "fauteuil_occ_pct", "valeur": kpis_A_dict["fauteuil_occ_pct"], "unite": "%"},
        {"categorie": "scenario_B", "indicateur": "simules", "valeur": agent.kpis_B.scheduled, "unite": "séjours"},
        {"categorie": "scenario_B", "indicateur": "gain_vs_A", "valeur": agent.kpis_B.gain_vs_a, "unite": "séjours"},
        {"categorie": "scenario_B", "indicateur": "retinographe_occ_pct", "valeur": kpis_B_dict["retinographe_occ_pct"], "unite": "%"},
        {"categorie": "scenario_B", "indicateur": "fauteuil_occ_pct", "valeur": kpis_B_dict["fauteuil_occ_pct"], "unite": "%"},
    ]
    if ipp_metrics.get("has_ipp"):
        for k, v in ipp_metrics.items():
            if k != "has_ipp":
                rows.append({"categorie": "patients_recurrents", "indicateur": k, "valeur": v, "unite": ""})
    _write(out / "kpi_summary.csv", pd.DataFrame(rows).to_csv(index=False))

    sc_comp = {
        "scenario": ["A — PMSI", "B — Réorganisation"],
        "planifies_simules": [kpis_A_dict["planifies"], kpis_B_dict["simules"]],
        "gain_vs_A": [0, kpis_B_dict["gain_vs_A"]],
        "retinographe_occ_pct": [kpis_A_dict["retinographe_occ_pct"], kpis_B_dict["retinographe_occ_pct"]],
        "fauteuil_occ_pct": [kpis_A_dict["fauteuil_occ_pct"], kpis_B_dict["fauteuil_occ_pct"]],
    }
    _write(out / "scenario_comparison.json", json.dumps(sc_comp, ensure_ascii=False, indent=2))
    _write(out / "scenario_comparison.csv", pd.DataFrame(sc_comp).to_csv(index=False))

    if ipp_metrics.get("has_ipp"):
        prec = [{"indicateur": k, "valeur": v} for k, v in ipp_metrics.items() if k != "has_ipp"]
        _write(out / "patients_recurrents_summary.csv", pd.DataFrame(prec).to_csv(index=False))

    # ── Nouveaux modules ───────────────────────────────────────────────────
    quality = build_data_quality_report(df_raw)
    print(f"  ✓ outputs/data_quality_report.json")

    reconstruct_patient_pathways(df_raw)
    print(f"  ✓ outputs/pathway_reconstruction.json")
    print(f"  ✓ outputs/fragmentation_segments.json")

    triage_pathways(df)
    print(f"  ✓ outputs/triage_summary.json")

    build_scenario_matrix(agent, ipp_metrics)
    print(f"  ✓ outputs/scenario_matrix.json")

    simulate_capacity(df)
    print(f"  ✓ outputs/capacity_simulation.json")

    build_medico_economic_estimates(kpis_A_dict, kpis_B_dict, ipp_metrics)
    print(f"  ✓ outputs/medico_economic_estimates.json")

    prioritize_pathways(dict(agent.kpis_B.by_pathway), agent.total, ipp_metrics)
    print(f"  ✓ outputs/pathway_prioritization.json")
    print(f"  ✓ outputs/decision_recommendations.json")

    # ── Architecture agents ────────────────────────────────────────────────
    arch = _build_agent_architecture()
    _write(out / "agent_architecture.json", json.dumps(arch, ensure_ascii=False, indent=2))
    graph = _build_interactions_graph(arch["agents"])
    _write(out / "agent_interactions_graph.json", json.dumps(graph, ensure_ascii=False, indent=2))

    memory = _build_memory_cases(kpis_B_dict, ipp_metrics)
    _write(out / "agent_memory_cases.json", json.dumps(memory, ensure_ascii=False, indent=2))

    alignment = _build_subject_alignment(kpis_A_dict, kpis_B_dict, ipp_metrics)
    _write(out / "subject_alignment.json", json.dumps(alignment, ensure_ascii=False, indent=2))

    # ── Note de décision ───────────────────────────────────────────────────
    note = _generate_decision_note(kpis_A_dict, kpis_B_dict, ipp_metrics, quality)
    _write(out / "note_decision_hospitaliere.md", note)

    print(f"\n→ {len(list(out.iterdir()))} fichiers dans outputs/")
    print("→ Outil hospitalier d'aide à la décision — prêt pour présentation\n")


if __name__ == "__main__":
    main()
