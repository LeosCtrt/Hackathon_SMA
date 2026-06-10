"""
Priorisation des parcours HDJ — score multicritère et recommandations.

Produit un classement des parcours HDJ à créer ou renforcer, basé sur
les données réelles, les règles YAML et les KPIs de simulation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


PATHWAY_PROFILES = {
    "bilan_annuel_diabete": {
        "label": "Bilan annuel diabète",
        "besoin_coordination": 0.5,
        "ressources_critiques": ["aucune"],
        "faisabilite_operationnelle": 0.85,
        "valeur_strategique": 0.90,
        "difficulte_implementation": 0.25,
    },
    "bilan_endocrino_metabolique": {
        "label": "Bilan endocrino-métabolique",
        "besoin_coordination": 0.80,
        "ressources_critiques": ["multi-soignants"],
        "faisabilite_operationnelle": 0.70,
        "valeur_strategique": 0.80,
        "difficulte_implementation": 0.45,
    },
    "etp_diabete_obesite": {
        "label": "ETP diabète / obésité",
        "besoin_coordination": 0.70,
        "ressources_critiques": ["salle_etp", "dieteticienne"],
        "faisabilite_operationnelle": 0.75,
        "valeur_strategique": 0.75,
        "difficulte_implementation": 0.40,
    },
    "test_dynamique_endocrinien": {
        "label": "Test dynamique endocrinien",
        "besoin_coordination": 0.60,
        "ressources_critiques": ["fauteuil_medicalise"],
        "faisabilite_operationnelle": 0.65,
        "valeur_strategique": 0.70,
        "difficulte_implementation": 0.55,
    },
    "depistage_retinopathie": {
        "label": "Dépistage rétinopathie",
        "besoin_coordination": 0.40,
        "ressources_critiques": ["retinographe"],
        "faisabilite_operationnelle": 0.80,
        "valeur_strategique": 0.65,
        "difficulte_implementation": 0.30,
    },
    "already_hdj": {
        "label": "Séjours déjà HDJ",
        "besoin_coordination": 0.30,
        "ressources_critiques": ["existants"],
        "faisabilite_operationnelle": 0.95,
        "valeur_strategique": 0.60,
        "difficulte_implementation": 0.10,
    },
}

OWNERS = {
    "bilan_annuel_diabete": ["Chef de service endocrinologie", "Cadre HDJ", "DIM/PMSI"],
    "bilan_endocrino_metabolique": ["Chef de service", "Direction des opérations", "DIM/PMSI"],
    "etp_diabete_obesite": ["Diététicienne référente", "Cadre HDJ", "Chef de service"],
    "test_dynamique_endocrinien": ["Chef de service endocrinologie", "IDE référent", "DIM/PMSI"],
    "depistage_retinopathie": ["Chef de service ophtalmologie", "Cadre HDJ"],
    "already_hdj": ["Cadre HDJ", "DIM/PMSI"],
}


def _compute_score(profile: Dict, volume: int, total: int, reorg_potential: float = 0.5) -> float:
    """Score de priorité [0–1] basé sur critères pondérés."""
    vol_score = min(volume / max(total * 0.10, 1), 1.0)  # cap at 10% du total
    score = (
        vol_score * 0.30
        + reorg_potential * 0.20
        + profile["valeur_strategique"] * 0.20
        + profile["faisabilite_operationnelle"] * 0.15
        + (1 - profile["difficulte_implementation"]) * 0.10
        + (1 - profile["besoin_coordination"]) * 0.05
    )
    return round(score, 3)


def prioritize_pathways(
    by_pathway: Dict[str, int],
    total_sejours: int,
    ipp_metrics: Dict[str, Any] | None = None,
    output_prioritization: str | Path = "outputs/pathway_prioritization.json",
    output_recommendations: str | Path = "outputs/decision_recommendations.json",
) -> Dict[str, Any]:
    """
    Produit le classement des parcours HDJ et les recommandations décisionnelles.

    Args:
        by_pathway            : dict pathway → volume (depuis kpis_B.by_pathway).
        total_sejours         : total séjours analysés.
        ipp_metrics           : métriques IPP (optionnel).
        output_prioritization : chemin JSON prioritization.
        output_recommendations: chemin JSON recommendations.

    Returns:
        dict contenant prioritization et recommendations.
    """
    scored: List[Dict[str, Any]] = []

    for pw, profile in PATHWAY_PROFILES.items():
        volume = by_pathway.get(pw, 0)
        pct = round(volume / total_sejours * 100, 1) if total_sejours else 0.0
        reorg = 0.9 if pw in ("bilan_annuel_diabete", "bilan_endocrino_metabolique") else 0.6
        score = _compute_score(profile, volume, total_sejours, reorg)

        scored.append({
            "pathway": pw,
            "label": profile["label"],
            "volume": volume,
            "pct_total": pct,
            "score_priorite": score,
            "ressources_critiques": profile["ressources_critiques"],
            "faisabilite": profile["faisabilite_operationnelle"],
            "valeur_strategique": profile["valeur_strategique"],
            "difficulte": profile["difficulte_implementation"],
            "owners_suggeres": OWNERS.get(pw, ["Chef de service", "DIM/PMSI"]),
        })

    scored.sort(key=lambda x: x["score_priorite"], reverse=True)
    for rank, item in enumerate(scored, 1):
        item["rang"] = rank

    # Levier transversal : regroupement récurrents (hors classement de parcours)
    transversal_levers: List[Dict[str, Any]] = []
    if ipp_metrics and ipp_metrics.get("has_ipp"):
        rec = ipp_metrics["patients_recurrents"]
        transversal_levers.append({
            "levier": "recurrent_patient_grouping",
            "label": "Regroupement patients récurrents (levier transversal)",
            "description": (
                "Les patients multi-venues (> 1 consultation sur la période) représentent "
                "un potentiel de regroupement en HDJ quelle que soit la pathologie. "
                "Ce levier s'applique à tous les parcours ranked_hdj_pathways."
            ),
            "volume": rec,
            "pct_total": ipp_metrics.get("pct_recurrents", 0),
            "valeur_strategique": 0.85,
            "difficulte": 0.65,
            "owners_suggeres": ["Chef de service", "DIM/PMSI", "Cadre HDJ", "DSI/Data"],
            "note": (
                "À activer après validation DIM/PMSI des parcours prioritaires. "
                "Nécessite un module DSI de détection automatique des récurrences."
            ),
        })

    prioritization: Dict[str, Any] = {
        "analyse": "Priorisation des parcours HDJ — score multicritère",
        "methodologie": (
            "Score pondéré : volume (30%), potentiel réorganisation (20%), "
            "valeur stratégique (20%), faisabilité (15%), facilité (10%), coordination (5%)"
        ),
        "total_sejours_reference": total_sejours,
        "ranked_hdj_pathways": scored,
        "transversal_levers": transversal_levers,
        "classement": scored,  # backward compat
        "note": (
            "Le classement est une aide à la priorisation organisationnelle. "
            "La décision finale appartient aux équipes médicales et à la direction."
        ),
    }

    # ── Recommandations décisionnelles ────────────────────────────────────
    top3 = scored[:3]
    recs: List[Dict[str, Any]] = []
    for item in top3:
        recs.append({
            "recommandation": f"Créer ou renforcer le parcours HDJ : {item['label']}",
            "preuve_donnees": f"{item['volume']} séjours identifiés ({item['pct_total']}% du total)",
            "score_priorite": item["score_priorite"],
            "etapes_mise_en_oeuvre": [
                "Valider l'éligibilité PMSI avec le DIM",
                "Définir le protocole HDJ avec le chef de service",
                "Vérifier la disponibilité des ressources critiques",
                "Former les soignants au parcours",
                "Lancer un pilote sur 3 mois",
                "Évaluer et ajuster",
            ],
            "risques": [
                "Validation PMSI requise avant facturation",
                "Disponibilité soignants à confirmer",
                "Données actuelles TYPE_SEJOUR=EXT — réel HDJ à mesurer",
            ],
            "validation_requise": {
                "DIM_PMSI": True,
                "chef_de_service": True,
                "direction_operations": item["score_priorite"] > 0.6,
                "gouvernance": item["score_priorite"] > 0.7,
            },
            "owners": item["owners_suggeres"],
        })

    recommendations: Dict[str, Any] = {
        "analyse": "Recommandations décisionnelles HDJ — aide à la gouvernance",
        "recommandations": recs,
        "avertissement": (
            "Ces recommandations sont des propositions basées sur l'analyse des données. "
            "Elles ne constituent pas une prescription médicale ni une décision PMSI."
        ),
        "prochaines_etapes_globales": [
            "Présenter les résultats au comité de direction médicale",
            "Mandater le DIM pour valider les cas les plus fréquents",
            "Définir un plan de transformation HDJ sur 12 mois",
            "Mettre en place un suivi des KPIs d'occupation HDJ",
        ],
    }

    out1 = Path(output_prioritization)
    out2 = Path(output_recommendations)
    out1.parent.mkdir(exist_ok=True)
    out2.parent.mkdir(exist_ok=True)
    out1.write_text(json.dumps(prioritization, ensure_ascii=False, indent=2), encoding="utf-8")
    out2.write_text(json.dumps(recommendations, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"prioritization": prioritization, "recommendations": recommendations}
