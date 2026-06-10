"""
Triage organisationnel des séjours — classification décisionnelle HDJ.

Ce module classe chaque séjour/parcours dans une catégorie décisionnelle
en utilisant les règles métier du YAML et les résultats de l'éligibilité.

Important : ce n'est pas du diagnostic médical. C'est un triage
organisationnel de parcours, à valider par le DIM/PMSI avant mise en œuvre.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from core.rules.hdj_eligibility import is_hdj_eligible


# Catégories de triage organisationnel
TRIAGE_CATEGORIES = {
    "already_hdj": "Séjour déjà structuré en HDJ ou assimilé",
    "pmsi_guardrail_candidate": "Candidat HDJ avec référence PMSI solide",
    "target_reorganization_candidate": "Candidat à la réorganisation HDJ — validation PMSI requise",
    "recurrent_patient_grouping_candidate": "Patient récurrent — potentiel de regroupement",
    "requires_pmsi_validation": "Signal HDJ identifié mais validation PMSI obligatoire",
    "out_of_scope": "Hors périmètre endocrino-diabéto HDJ",
    "insufficient_signal": "Signal insuffisant pour classification HDJ",
}


def _map_eligibility_to_triage(el, row_data: dict) -> str:
    """Mappe le résultat d'éligibilité vers une catégorie de triage organisationnel."""
    pot = el.hdj_potential
    reorg = el.reorganization_potential

    if pot == "not_hdj_relevant":
        return "out_of_scope"
    if pot == "already_hdj":
        return "already_hdj"
    if pot == "convertible_to_hdj":
        return "pmsi_guardrail_candidate"
    if pot == "convertible_to_hdj_requires_review":
        return "requires_pmsi_validation"
    if pot in ("candidate_hdj_requires_pmsi_validation",):
        if reorg in ("high", "medium"):
            return "target_reorganization_candidate"
        return "requires_pmsi_validation"
    if pot == "uncertain_requires_human_review":
        return "insufficient_signal"
    return "insufficient_signal"


def triage_pathways(
    df: pd.DataFrame,
    output_path: str | Path = "outputs/triage_summary.json",
) -> Dict[str, Any]:
    """
    Classe chaque séjour dans une catégorie de triage organisationnel.

    Args:
        df          : DataFrame agrégé par séjour.
        output_path : chemin de sortie.

    Returns:
        dict du rapport de triage.
    """
    counts: Dict[str, int] = defaultdict(int)
    pathways_by_category: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    resources_by_category: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    rules_used: List[str] = []

    for _, row in df.iterrows():
        row_dict = row.to_dict()
        el = is_hdj_eligible(row_dict)
        category = _map_eligibility_to_triage(el, row_dict)
        counts[category] += 1
        pathways_by_category[category][el.candidate_pathway] += 1
        for res in el.required_resources:
            resources_by_category[category][res] += 1
        for rule in el.matched_rules:
            if rule not in rules_used:
                rules_used.append(rule)

    total = sum(counts.values())

    categories_detail: List[Dict[str, Any]] = []
    for cat, description in TRIAGE_CATEGORIES.items():
        n = counts.get(cat, 0)
        categories_detail.append({
            "categorie": cat,
            "description": description,
            "volume": n,
            "pct_total": round(n / total * 100, 1) if total else 0.0,
            "pathways_detectes": dict(pathways_by_category.get(cat, {})),
            "ressources_necessaires": dict(resources_by_category.get(cat, {})),
        })

    # Compter candidats HDJ actionnables
    actionnable = (
        counts.get("already_hdj", 0)
        + counts.get("pmsi_guardrail_candidate", 0)
        + counts.get("target_reorganization_candidate", 0)
    )

    report: Dict[str, Any] = {
        "analyse": "Triage organisationnel HDJ — règles YAML endocrino-diabétologie",
        "total_sejours_analyses": total,
        "candidats_hdj_actionnables": actionnable,
        "pct_actionnables": round(actionnable / total * 100, 1) if total else 0.0,
        "categories": categories_detail,
        "regles_utilisees": rules_used[:20],
        "limites": [
            "Classification basée sur actes CCAM et diagnostics disponibles — "
            "absence de données = signal faible, pas forcément hors périmètre",
            "Instruction Gradation DGOS/R1/DSS/1A/2020/52 non encodée — "
            "tous les cas B portent requires_pmsi_validation",
            "Triage organisationnel uniquement — validation médicale et PMSI requise",
        ],
        "note": (
            "Ce triage est un outil d'aide à la décision organisationnelle. "
            "Il ne constitue pas une reclassification PMSI ni un acte médical."
        ),
    }

    out = Path(output_path)
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    return report
