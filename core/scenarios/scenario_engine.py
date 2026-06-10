"""
Moteur de scénarios HDJ — construit la matrice de scénarios
à partir des résultats du CoordinateurAgent.

6 scénarios organisationnels, tous déterministes et reproductibles.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from core.agents.coordinateur import CoordinateurAgent


def build_scenario_matrix(
    agent: CoordinateurAgent,
    ipp_metrics: Dict[str, Any] | None = None,
    output_path: str | Path = "outputs/scenario_matrix.json",
) -> Dict[str, Any]:
    """
    Construit la matrice de 6 scénarios HDJ à partir des KPIs du CoordinateurAgent.

    Args:
        agent       : CoordinateurAgent après run().
        ipp_metrics : métriques IPP (optionnel) pour le scénario récurrence.
        output_path : chemin de sortie JSON.

    Returns:
        dict scenario_matrix.
    """
    kA = agent.kpis_A
    kB = agent.kpis_B
    total = agent.total

    by_pw: Dict[str, int] = dict(kB.by_pathway)

    def _pw(key: str) -> int:
        return by_pw.get(key, 0)

    scenarios: List[Dict[str, Any]] = [
        {
            "id": "current_fragmented_care",
            "nom": "Activité actuelle fragmentée",
            "description": (
                "Représente l'organisation actuelle : consultations externes et actes isolés, "
                "sans structuration HDJ. Sert de référence pour mesurer le gain des autres scénarios."
            ),
            "population_cible": "Tous séjours analysés (TYPE_SEJOUR=EXT)",
            "volume": total,
            "dont_hors_perimetre": kA.not_applicable,
            "signal_fragmentation": ipp_metrics.get("lignes_patients_recurrents", 0) if ipp_metrics else None,
            "patients_recurrents": ipp_metrics.get("patients_recurrents", 0) if ipp_metrics else None,
            "pct_recurrents": ipp_metrics.get("pct_recurrents", 0) if ipp_metrics else None,
            "ressources_necessaires": "Organisation actuelle — consultations dispersées",
            "statut_pmsi": "TYPE_SEJOUR=EXT uniquement — pas de GHS HDJ",
            "validation_requise": "N/A — état de référence",
            "score_confiance": 1.0,
            "valeur_hospitaliere": "Référence organisationnelle — point de départ de la transformation",
        },
        {
            "id": "pmsi_guardrail_hdj",
            "nom": "Scénario A — Garde-fou PMSI",
            "description": (
                "Planifie uniquement les séjours avec une référence PMSI solide disponible "
                "(unité HDJ existante ou acte CCAM documenté dans le référentiel YAML + MCO). "
                "Approche conservatrice pour ne pas surestimer la facturation GHS réelle."
            ),
            "population_cible": "Séjours already_hdj + convertible_to_hdj",
            "volume": kA.scheduled,
            "deja_structures_hdj": kA.already_hdj,
            "convertibles_pmsi": kA.convertible,
            "requires_review": kA.requires_review,
            "non_planifies_uncertain": kA.uncertain,
            "delai_attente_moyen_j": round(kA.avg_wait_days, 1),
            "ressources_necessaires": "Retinographe + Fauteuil selon actes",
            "statut_pmsi": "Validation PMSI forte — GHS HDJ applicable",
            "validation_requise": "Confirmation actes CCAM par DIM",
            "score_confiance": 0.85,
            "valeur_hospitaliere": (
                "Sécurité réglementaire maximale — démarrage HDJ sans risque de rejet PMSI"
            ),
        },
        {
            "id": "target_reorganization_hdj",
            "nom": "Scénario B — Réorganisation cible",
            "description": (
                "Simule la réorganisation complète en HDJ pour tous les candidats identifiés "
                "(high + medium potential), avec validation PMSI explicite requise. "
                "Représente le potentiel maximal de structuration ambulatoire."
            ),
            "population_cible": "Candidats high + medium reorganization_potential",
            "volume": kB.scheduled,
            "dont_pmsi_validation_required": kB.pmsi_validation_required,
            "uncertain_non_simules": kB.requires_human_review,
            "low_candidates": kB.low_candidate,
            "gain_vs_A": kB.gain_vs_a,
            "delai_attente_moyen_j": round(kB.avg_wait_days, 1),
            "ressources_necessaires": "Retinographe + Fauteuil — saturation possible",
            "statut_pmsi": "Validation PMSI requise avant facturation GHS",
            "validation_requise": "DIM + Chef de service + Direction des opérations",
            "score_confiance": 0.65,
            "valeur_hospitaliere": (
                f"+{kB.gain_vs_a} séjours organisables en HDJ vs scénario A — "
                "potentiel de structuration ambulatoire identifié"
            ),
        },
        {
            "id": "annual_diabetes_hdj",
            "nom": "HDJ Bilan annuel diabète",
            "description": (
                "Scénario spécialisé centré sur le parcours bilan annuel diabète : "
                "regroupement en une journée de toutes les consultations annuelles "
                "(bilan biologique, consultation endocrino, ETP si besoin)."
            ),
            "population_cible": "Pathway bilan_annuel_diabete",
            "volume": _pw("bilan_annuel_diabete"),
            "duree_estimee_min": 60,
            "estimation_method": "duration_from_yaml §actes_ccam_hdj_endocrino.bilan_annuel_diabete",
            "ressources_necessaires": "Consultation endocrinologue + biologiste",
            "statut_pmsi": "Validation Instruction Gradation requise",
            "validation_requise": "DIM + Chef de service endocrinologie",
            "score_confiance": 0.72,
            "valeur_hospitaliere": (
                "Fort volume, faible ressource critique — parcours prioritaire à créer"
            ),
        },
        {
            "id": "endocrino_metabolic_hdj",
            "nom": "HDJ Bilan endocrino-métabolique",
            "description": (
                "Regroupement des bilans métaboliques complexes nécessitant plusieurs "
                "spécialistes en une même journée (endocrinologue, diététicienne, IDE)."
            ),
            "population_cible": "Pathway bilan_endocrino_metabolique",
            "volume": _pw("bilan_endocrino_metabolique"),
            "duree_estimee_min": 60,
            "estimation_method": "duration_from_yaml",
            "ressources_necessaires": "Multi-soignants : endocrinologue + diététicienne + IDE",
            "statut_pmsi": "Validation PMSI requise",
            "validation_requise": "DIM + Direction des opérations",
            "score_confiance": 0.68,
            "valeur_hospitaliere": "Coordination élevée — réduction fragmentation multi-intervenants",
        },
        {
            "id": "recurrent_patient_grouping",
            "nom": "Regroupement patients récurrents",
            "description": (
                "Scénario transversal ciblant les patients avec plusieurs venues sur la période. "
                "Objectif : réduire la fragmentation en regroupant les actes répétés "
                "en séances HDJ planifiées."
            ),
            "population_cible": "Patients IPP avec > 1 venue",
            "volume": ipp_metrics.get("patients_recurrents", 0) if ipp_metrics else None,
            "lignes_concernees": ipp_metrics.get("lignes_patients_recurrents", 0) if ipp_metrics else None,
            "venues_moy": ipp_metrics.get("venues_moy", 0) if ipp_metrics else None,
            "venues_max": ipp_metrics.get("venues_max", 0) if ipp_metrics else None,
            "duree_estimee_min": "variable selon actes groupés",
            "estimation_method": "IPP recurrence analysis",
            "ressources_necessaires": "À définir selon actes groupés",
            "statut_pmsi": "Nécessite protocole HDJ dédié + validation DIM",
            "validation_requise": "Chef de service + DIM + cadre HDJ",
            "score_confiance": 0.55,
            "valeur_hospitaliere": (
                "Impact direct sur fragmentation parcours — moins de déplacements patients, "
                "meilleure coordination soignants, optimisation occupation ressources"
            ),
        },
    ]

    matrix: Dict[str, Any] = {
        "analyse": "Matrice de scénarios HDJ — CHU Guyane Endocrino-Diabétologie",
        "n_scenarios": len(scenarios),
        "base_reference": "Scénario current_fragmented_care",
        "scenarios": scenarios,
        "synthese_comparative": {
            "volume_reference": total,
            "volume_pmsi_guardrail": kA.scheduled,
            "volume_reorganisation_cible": kB.scheduled,
            "gain_reorganisation_vs_guardrail": kB.gain_vs_a,
            "pct_gain": round(kB.gain_vs_a / total * 100, 1) if total else 0,
        },
        "recommandation": (
            "Commencer par le scénario A (garde-fou PMSI) pour une mise en œuvre "
            "sécurisée, puis élargir vers le scénario B après validation DIM/PMSI."
        ),
        "note": (
            "Tous les volumes sont des estimations opérationnelles basées sur les données "
            "historiques. Validation médicale et PMSI requise avant mise en œuvre."
        ),
    }

    out = Path(output_path)
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(matrix, ensure_ascii=False, indent=2), encoding="utf-8")

    return matrix
